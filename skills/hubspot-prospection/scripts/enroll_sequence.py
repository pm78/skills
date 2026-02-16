#!/usr/bin/env python3
"""
HubSpot Sequence Enrollment Script

Enrolls contacts into HubSpot sequences via the Sequences API v4.
This fills the gap left by MCP tools which don't expose sequence enrollment.

Usage:
    # List available sequences
    python enroll_sequence.py --token TOKEN --list-sequences

    # Enroll contacts in a sequence
    python enroll_sequence.py --token TOKEN --sequence-id SEQ_ID \
        --sender-email sender@company.com --contact-ids 101,102,103

    # Dry run (validate without enrolling)
    python enroll_sequence.py --token TOKEN --sequence-id SEQ_ID \
        --sender-email sender@company.com --contact-ids 101,102,103 --dry-run

Requirements:
    pip install requests
"""

import argparse
import json
import sys
import time

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Install with: pip install requests")
    sys.exit(1)

BASE_URL = "https://api.hubapi.com"
ENROLLMENT_DAILY_LIMIT = 1000
BATCH_SIZE = 50  # Max contacts per enrollment request
RATE_LIMIT_DELAY = 0.12  # ~8 req/s to stay under HubSpot 10/s limit


def get_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def list_sequences(token: str) -> list:
    """List all sequences in the portal."""
    url = f"{BASE_URL}/automation/v4/sequences"
    headers = get_headers(token)
    all_sequences = []
    after = None

    while True:
        params = {"limit": 100}
        if after:
            params["after"] = after

        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            print(f"ERROR: Failed to list sequences (HTTP {resp.status_code})")
            print(f"  Response: {resp.text[:500]}")
            sys.exit(1)

        data = resp.json()
        results = data.get("results", [])
        all_sequences.extend(results)

        paging = data.get("paging", {})
        next_page = paging.get("next", {})
        after = next_page.get("after")
        if not after:
            break

    return all_sequences


def get_sequence_details(token: str, sequence_id: str) -> dict:
    """Get details of a specific sequence."""
    url = f"{BASE_URL}/automation/v4/sequences/{sequence_id}"
    resp = requests.get(url, headers=get_headers(token))
    if resp.status_code != 200:
        print(f"ERROR: Failed to get sequence {sequence_id} (HTTP {resp.status_code})")
        print(f"  Response: {resp.text[:500]}")
        sys.exit(1)
    return resp.json()


def validate_sender_email(token: str, sender_email: str) -> bool:
    """Validate that the sender email is a connected email in the portal."""
    # The enrollment endpoint will reject invalid sender emails;
    # we do a lightweight check here.
    if not sender_email or "@" not in sender_email:
        print(f"ERROR: Invalid sender email: {sender_email}")
        return False
    return True


def probe_sequences_access(token: str) -> dict:
    """Probe Sequences API access and detect missing-scope permission blocks."""
    url = f"{BASE_URL}/automation/v4/sequences"

    try:
        resp = requests.get(url, headers=get_headers(token), params={"limit": 1})
    except requests.RequestException as exc:
        return {
            "ok": False,
            "status_code": None,
            "category": "NETWORK_ERROR",
            "message": str(exc),
            "missing_scopes": [],
            "correlation_id": None,
        }

    if resp.status_code == 200:
        return {
            "ok": True,
            "status_code": 200,
            "category": None,
            "message": None,
            "missing_scopes": [],
            "correlation_id": None,
        }

    payload = {}
    try:
        payload = resp.json()
    except Exception:
        payload = {}

    missing_scopes = []
    for err in payload.get("errors", []):
        ctx = err.get("context", {})
        missing_scopes.extend(ctx.get("requiredGranularScopes", []) or [])

    return {
        "ok": False,
        "status_code": resp.status_code,
        "category": payload.get("category"),
        "message": payload.get("message", resp.text[:500]),
        "missing_scopes": sorted(set(missing_scopes)),
        "correlation_id": payload.get("correlationId"),
    }


def is_permission_limited_sequences(probe: dict) -> bool:
    """Return True when Sequences is unavailable due to account/app permissions."""
    if probe.get("status_code") == 403:
        return True
    if probe.get("category") == "MISSING_SCOPES":
        return True
    if probe.get("missing_scopes"):
        return True
    return False


def enroll_contact(token: str, sequence_id: str, sender_email: str,
                   contact_id: str) -> dict:
    """Enroll a single contact into a sequence."""
    url = f"{BASE_URL}/automation/v4/sequences/{sequence_id}/enrollments"
    payload = {
        "contactId": contact_id,
        "senderEmail": sender_email,
        "startingStepOrder": 0,
    }
    resp = requests.post(url, headers=get_headers(token), json=payload)
    return {
        "contact_id": contact_id,
        "status_code": resp.status_code,
        "success": resp.status_code in (200, 201),
        "response": resp.json() if resp.text else {},
    }


def enroll_contacts_batch(token: str, sequence_id: str, sender_email: str,
                          contact_ids: list, dry_run: bool = False) -> dict:
    """Enroll multiple contacts with rate limiting and error handling."""
    results = {"enrolled": [], "failed": [], "skipped": []}

    if len(contact_ids) > ENROLLMENT_DAILY_LIMIT:
        print(f"WARNING: {len(contact_ids)} contacts exceeds daily limit of "
              f"{ENROLLMENT_DAILY_LIMIT}. Only first {ENROLLMENT_DAILY_LIMIT} "
              f"will be processed.")
        contact_ids = contact_ids[:ENROLLMENT_DAILY_LIMIT]

    total = len(contact_ids)
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Enrolling {total} contacts "
          f"in sequence {sequence_id}...")

    for i, contact_id in enumerate(contact_ids, 1):
        contact_id = str(contact_id).strip()
        if not contact_id:
            continue

        if dry_run:
            print(f"  [{i}/{total}] Would enroll contact {contact_id}")
            results["skipped"].append({"contact_id": contact_id, "reason": "dry_run"})
            continue

        result = enroll_contact(token, sequence_id, sender_email, contact_id)

        if result["success"]:
            print(f"  [{i}/{total}] Enrolled contact {contact_id}")
            results["enrolled"].append(contact_id)
        else:
            error_msg = result["response"].get("message", "Unknown error")
            status = result["status_code"]
            print(f"  [{i}/{total}] FAILED contact {contact_id}: "
                  f"HTTP {status} - {error_msg}")
            results["failed"].append({
                "contact_id": contact_id,
                "status": status,
                "error": error_msg,
            })

            # Handle rate limiting (429)
            if status == 429:
                retry_after = int(result["response"].get("retry-after", 10))
                print(f"  Rate limited. Waiting {retry_after}s...")
                time.sleep(retry_after)

        # Respect rate limits
        time.sleep(RATE_LIMIT_DELAY)

    return results


def print_summary(results: dict):
    """Print enrollment summary."""
    print("\n--- Enrollment Summary ---")
    print(f"  Enrolled:  {len(results['enrolled'])}")
    print(f"  Failed:    {len(results['failed'])}")
    print(f"  Skipped:   {len(results['skipped'])}")

    if results["failed"]:
        print("\n  Failed contacts:")
        for f in results["failed"]:
            print(f"    - {f['contact_id']}: {f['error']}")


def main():
    parser = argparse.ArgumentParser(
        description="Enroll contacts into HubSpot sequences via API v4"
    )
    parser.add_argument("--token", required=True,
                        help="HubSpot private app access token")
    parser.add_argument("--sequence-id",
                        help="ID of the sequence to enroll contacts in")
    parser.add_argument("--sender-email",
                        help="Email address of the sender (must be connected in HubSpot)")
    parser.add_argument("--contact-ids",
                        help="Comma-separated list of contact IDs to enroll")
    parser.add_argument("--contact-ids-file",
                        help="Path to file with one contact ID per line")
    parser.add_argument("--list-sequences", action="store_true",
                        help="List all available sequences and exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate and show what would happen without enrolling")
    parser.add_argument("--output-json",
                        help="Path to write results as JSON")

    args = parser.parse_args()

    # List sequences mode
    if args.list_sequences:
        probe = probe_sequences_access(args.token)

        if not probe["ok"]:
            if is_permission_limited_sequences(probe):
                print("SEQUENCES_UNAVAILABLE: permission-limited account/app.")
                if probe.get("missing_scopes"):
                    print("  Missing scopes: " + ", ".join(probe["missing_scopes"]))
                if probe.get("correlation_id"):
                    print(f"  Correlation ID: {probe['correlation_id']}")
                print("  Fallback: skip sequence enrollment and continue manual outreach.")
                if args.output_json:
                    with open(args.output_json, "w") as f:
                        json.dump({"status": "sequences_unavailable", "probe": probe}, f, indent=2)
                    print(f"Results saved to {args.output_json}")
                return

            print(f"ERROR: Could not reach Sequences API ({probe.get('category')}).")
            print(f"  Message: {probe.get('message')}")
            sys.exit(1)

        sequences = list_sequences(args.token)
        if not sequences:
            print("No sequences found in this portal.")
            return

        print(f"\nFound {len(sequences)} sequence(s):\n")
        for seq in sequences:
            seq_id = seq.get("id", "?")
            name = seq.get("name", "Unnamed")
            steps = seq.get("steps", [])
            print(f"  ID: {seq_id}")
            print(f"  Name: {name}")
            print(f"  Steps: {len(steps)}")
            print()
        return

    # Enrollment mode - validate required args
    if not args.sequence_id:
        parser.error("--sequence-id is required for enrollment")
    if not args.sender_email:
        parser.error("--sender-email is required for enrollment")
    if not args.contact_ids and not args.contact_ids_file:
        parser.error("--contact-ids or --contact-ids-file is required")

    # Probe access first so permission-limited accounts can skip cleanly
    probe = probe_sequences_access(args.token)
    if not probe["ok"]:
        if is_permission_limited_sequences(probe):
            print("SEQUENCES_UNAVAILABLE: permission-limited account/app.")
            if probe.get("missing_scopes"):
                print("  Missing scopes: " + ", ".join(probe["missing_scopes"]))
            if probe.get("correlation_id"):
                print(f"  Correlation ID: {probe['correlation_id']}")
            print("  Enrollment skipped. Continue with manual outreach fallback.")
            if args.output_json:
                with open(args.output_json, "w") as f:
                    json.dump(
                        {
                            "status": "sequences_unavailable",
                            "probe": probe,
                            "enrolled": [],
                            "failed": [],
                            "skipped": [],
                        },
                        f,
                        indent=2,
                    )
                print(f"Results saved to {args.output_json}")
            return

        print(f"ERROR: Could not reach Sequences API ({probe.get('category')}).")
        print(f"  Message: {probe.get('message')}")
        sys.exit(1)

    # Validate sender email
    if not validate_sender_email(args.token, args.sender_email):
        sys.exit(1)

    # Collect contact IDs
    contact_ids = []
    if args.contact_ids:
        contact_ids.extend([cid.strip() for cid in args.contact_ids.split(",")
                           if cid.strip()])
    if args.contact_ids_file:
        try:
            with open(args.contact_ids_file) as f:
                file_ids = [line.strip() for line in f if line.strip()]
                contact_ids.extend(file_ids)
        except FileNotFoundError:
            print(f"ERROR: File not found: {args.contact_ids_file}")
            sys.exit(1)

    if not contact_ids:
        print("ERROR: No contact IDs provided.")
        sys.exit(1)

    # Remove duplicates preserving order
    seen = set()
    unique_ids = []
    for cid in contact_ids:
        if cid not in seen:
            seen.add(cid)
            unique_ids.append(cid)
    contact_ids = unique_ids

    # Verify sequence exists
    print(f"Verifying sequence {args.sequence_id}...")
    seq_info = get_sequence_details(args.token, args.sequence_id)
    print(f"Sequence: {seq_info.get('name', 'Unknown')} "
          f"({len(seq_info.get('steps', []))} steps)")

    # Execute enrollment
    results = enroll_contacts_batch(
        token=args.token,
        sequence_id=args.sequence_id,
        sender_email=args.sender_email,
        contact_ids=contact_ids,
        dry_run=args.dry_run,
    )

    print_summary(results)

    # Save results if requested
    if args.output_json:
        with open(args.output_json, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {args.output_json}")

    # Exit with error code if any failures
    if results["failed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()

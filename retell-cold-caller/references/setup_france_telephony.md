# France-to-France Calling Setup Guide

Retell only sells US/Canada phone numbers directly. To call from a French number (+33) to French numbers, you must **import** a number from a BYO telephony provider (Twilio or Telnyx) via SIP trunking.

## Option A: Quick Testing (No Phone Number Needed)

Use the `web-call` subcommand to test your agent in a browser:

```bash
python scripts/retell_campaign.py web-call \
  --agent-id agent_xxx \
  --execute
```

This creates a browser-based call session — no phone number, SIP trunk, or telephony provider required. Use this to validate your agent's conversation flow before investing in telephony setup.

## Option B: Production Setup with Twilio

### Step 1: Buy a French number on Twilio

1. Log in to your Twilio Console: https://console.twilio.com/
2. Go to **Phone Numbers > Manage > Buy a Number**
3. Search for country **France (+33)**
4. Purchase a number with **Voice** capability
5. Note the number in E.164 format (e.g. `+33140000000`)

> Twilio France numbers may require identity verification (address + ID document). Allow 1-2 business days for approval.

### Step 2: Create an Elastic SIP Trunk in Twilio

1. Go to **Elastic SIP Trunking > Trunks > Create new SIP Trunk**
2. Name it (e.g. "retell-france")
3. Under **Termination** tab:
   - Add a **Termination SIP URI** (e.g. `retell-france.pstn.twilio.com`)
   - Choose authentication method:
     - **Credential list** (recommended): Create a username/password pair
     - **IP access control list**: Add Retell's IPs (not recommended — Retell has no static IP)
4. Under **Origination** tab (for inbound, optional):
   - Add origination URI: `sip:sip.retellai.com`
5. Under **Numbers** tab:
   - Associate your French number with this SIP trunk

### Step 3: Import the number into Retell

```bash
python scripts/retell_campaign.py import-number \
  --phone-number "+33140000000" \
  --termination-uri "retell-france.pstn.twilio.com" \
  --sip-username "your_sip_username" \
  --sip-password "your_sip_password" \
  --outbound-agent-id "agent_xxx" \
  --nickname "FR-outbound" \
  --execute
```

### Step 4: Verify the number is imported

```bash
python scripts/retell_campaign.py list-numbers --execute
```

You should see your +33 number in the output.

### Step 5: Make a test call

```bash
python scripts/retell_campaign.py call-one \
  --agent-id agent_xxx \
  --from-number "+33140000000" \
  --to-number "+33600000000" \
  --execute
```

## Option C: Production Setup with Telnyx

Same flow as Twilio, but:

1. Buy a French number on Telnyx: https://portal.telnyx.com/
2. Create a SIP trunk / Outbound Voice Profile
3. Get the termination URI from Telnyx (format varies)
4. Import into Retell using `import-number` as above

## Costs

| Item | Cost |
|------|------|
| Retell outbound to France (via Twilio) | $0.06/min |
| Retell outbound to France (via Telnyx) | Check Telnyx rates |
| Retell web call (testing) | No telephony charge |
| Twilio French number (monthly) | ~$1-3/month |

## Troubleshooting

- **"from_number not found"**: The number hasn't been imported into Retell yet. Run `import-number` first.
- **"SIP auth failure"**: Double-check your `--sip-username` and `--sip-password` match the Twilio credential list.
- **"E.164 validation error"**: Ensure your number starts with `+33` and has the right number of digits.
- **Calls not connecting**: Verify the termination URI matches exactly what's in your Twilio SIP trunk (no trailing slash, no spaces).

## References

- Retell import number API: https://docs.retellai.com/api-references/import-phone-number
- Retell custom telephony: https://docs.retellai.com/deploy/custom-telephony
- Retell + Twilio setup: https://docs.retellai.com/deploy/twilio
- Retell international rates: https://docs.retellai.com/deploy/international-call
- Twilio France voice guidelines: https://www.twilio.com/en-us/guidelines/fr/voice
- Twilio SIP trunking docs: https://www.twilio.com/docs/sip-trunking

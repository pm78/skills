#!/usr/bin/env python3
"""Build a normalized brand profile from web pages, PPTX files, and DOCX files."""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

HEX_RE = re.compile(r"#([0-9a-fA-F]{6})\b")
FONT_DECL_RE = re.compile(r"font-family\s*:\s*([^;}{]+)", re.IGNORECASE)
OG_IMAGE_RE = re.compile(
    r"<meta[^>]+property=[\"']og:image[\"'][^>]+content=[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
A_TAG_RE = re.compile(
    r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
IMG_TAG_RE = re.compile(
    r"<img[^>]+src=[\"']([^\"']+)[\"'][^>]*>",
    re.IGNORECASE | re.DOTALL,
)
XML_HEX_RE = re.compile(r"(?:srgbClr|rgb|color)[^>]*\bval=[\"']([0-9A-Fa-f]{6})[\"']")
XML_FONT_RE = re.compile(r"(?:typeface|ascii|hAnsi|cs|eastAsia)=[\"']([^\"']+)[\"']")

GENERIC_FONTS = {
    "serif",
    "sans-serif",
    "monospace",
    "cursive",
    "fantasy",
    "system-ui",
    "emoji",
    "math",
    "fangsong",
    "ui-serif",
    "ui-sans-serif",
    "ui-monospace",
}

GUIDELINE_KEYWORDS = {
    "brand",
    "guideline",
    "style guide",
    "identity",
    "press kit",
    "media kit",
    "logo",
}

POLICY_KEYWORDS = {
    "policy",
    "trademark",
    "legal",
    "terms",
    "usage",
}


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "brand"


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return " ".join(text.split()).strip()


def normalize_hex(value: str) -> str:
    return f"#{value.upper()}"


def counter_to_ranked_list(counter: Counter, key: str, limit: int) -> list[dict]:
    items = []
    for value, count in counter.most_common(limit):
        items.append({key: value, "count": count})
    return items


def normalize_font(raw: str) -> str | None:
    value = raw.strip().strip("\"'")
    if not value:
        return None
    if ":" in value and not value.lower().startswith("http"):
        return None
    low = value.lower()
    if low in GENERIC_FONTS:
        return None
    if value.startswith("var("):
        return None
    return value


def fetch_html(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (brand-profile-builder)"})
    with urlopen(req, timeout=25) as resp:
        payload = resp.read()
        content_type = resp.headers.get("Content-Type", "")
        charset = "utf-8"
        if "charset=" in content_type:
            charset = content_type.split("charset=")[-1].split(";")[0].strip()
        try:
            return payload.decode(charset, errors="ignore")
        except LookupError:
            return payload.decode("utf-8", errors="ignore")


def extract_web_profile(url: str) -> dict:
    html = fetch_html(url)

    colors = Counter(normalize_hex(match.group(1)) for match in HEX_RE.finditer(html))

    fonts = Counter()
    for match in FONT_DECL_RE.finditer(html):
        family_decl = match.group(1)
        for font in family_decl.split(","):
            normalized = normalize_font(font)
            if normalized:
                fonts[normalized] += 1

    logos = []
    logo_seen = set()

    for match in OG_IMAGE_RE.finditer(html):
        src = urljoin(url, match.group(1).strip())
        if src not in logo_seen:
            logos.append({"url": src, "source": "meta:og:image"})
            logo_seen.add(src)

    for match in IMG_TAG_RE.finditer(html):
        src = urljoin(url, match.group(1).strip())
        tag = match.group(0).lower()
        if "logo" in tag and src not in logo_seen:
            logos.append({"url": src, "source": "img:logo-hint"})
            logo_seen.add(src)

    guidelines = []
    policies = []
    link_seen = set()
    for href, label in A_TAG_RE.findall(html):
        href_abs = urljoin(url, href.strip())
        if href_abs in link_seen:
            continue
        label_txt = clean_text(label)
        joined = f"{label_txt} {href_abs}".lower()

        if any(key in joined for key in GUIDELINE_KEYWORDS):
            guidelines.append({"title": label_txt or href_abs, "url": href_abs})
            link_seen.add(href_abs)
            continue

        if any(key in joined for key in POLICY_KEYWORDS):
            policies.append({"title": label_txt or href_abs, "url": href_abs})
            link_seen.add(href_abs)

    title_match = TITLE_RE.search(html)
    page_title = clean_text(title_match.group(1)) if title_match else ""

    domain = urlparse(url).netloc
    style_notes = [
        f"Extracted from website {url}",
        f"Detected domain: {domain}",
    ]

    return {
        "brand_name_hint": page_title or domain,
        "colors": colors,
        "fonts": fonts,
        "logos": logos,
        "guidelines": guidelines,
        "policies": policies,
        "style_notes": style_notes,
    }


def read_zip_text(path: Path, internal_path: str) -> str:
    with zipfile.ZipFile(path) as zf:
        with zf.open(internal_path) as handle:
            return handle.read().decode("utf-8", errors="ignore")


def extract_xml_signals(xml_text: str) -> tuple[Counter, Counter]:
    colors = Counter(normalize_hex(v) for v in XML_HEX_RE.findall(xml_text))

    fonts = Counter()
    for raw in XML_FONT_RE.findall(xml_text):
        normalized = normalize_font(raw)
        if normalized:
            fonts[normalized] += 1
    return colors, fonts


def extract_pptx_profile(path: Path) -> dict:
    colors = Counter()
    fonts = Counter()
    logos = []

    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()

    for name in names:
        if not name.endswith(".xml"):
            continue
        if not name.startswith("ppt/"):
            continue
        try:
            xml = read_zip_text(path, name)
        except KeyError:
            continue
        c, f = extract_xml_signals(xml)
        colors.update(c)
        fonts.update(f)

    for name in names:
        if not name.startswith("ppt/media/"):
            continue
        if name.endswith("/"):
            continue
        lower = name.lower()
        if "logo" in lower:
            logos.append({"path": name, "source": "pptx-media:logo-hint"})

    if not logos:
        for name in names:
            if name.startswith("ppt/media/") and not name.endswith("/"):
                logos.append({"path": name, "source": "pptx-media:first-image"})
                break

    return {
        "brand_name_hint": path.stem,
        "colors": colors,
        "fonts": fonts,
        "logos": logos,
        "guidelines": [],
        "policies": [],
        "style_notes": [f"Extracted from PPTX {path}"],
    }


def extract_docx_profile(path: Path) -> dict:
    colors = Counter()
    fonts = Counter()
    logos = []

    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()

    for name in names:
        if not name.endswith(".xml"):
            continue
        if not name.startswith("word/"):
            continue
        try:
            xml = read_zip_text(path, name)
        except KeyError:
            continue
        c, f = extract_xml_signals(xml)
        colors.update(c)
        fonts.update(f)

    for name in names:
        if not name.startswith("word/media/"):
            continue
        if name.endswith("/"):
            continue
        lower = name.lower()
        if "logo" in lower:
            logos.append({"path": name, "source": "docx-media:logo-hint"})

    if not logos:
        for name in names:
            if name.startswith("word/media/") and not name.endswith("/"):
                logos.append({"path": name, "source": "docx-media:first-image"})
                break

    return {
        "brand_name_hint": path.stem,
        "colors": colors,
        "fonts": fonts,
        "logos": logos,
        "guidelines": [],
        "policies": [],
        "style_notes": [f"Extracted from DOCX {path}"],
    }


def merge_profiles(parts: list[dict], brand_name: str | None, max_colors: int, max_fonts: int) -> dict:
    color_counter = Counter()
    font_counter = Counter()
    logos = []
    guidelines = []
    policies = []
    style_notes = []
    sources = []
    seen_logo = set()
    seen_guideline = set()
    seen_policy = set()

    brand_hint = brand_name

    for part in parts:
        color_counter.update(part["colors"])
        font_counter.update(part["fonts"])

        hint = part.get("brand_name_hint")
        if hint and not brand_hint:
            brand_hint = hint

        for logo in part.get("logos", []):
            key = logo.get("url") or logo.get("path")
            if key and key not in seen_logo:
                logos.append(logo)
                seen_logo.add(key)

        for guideline in part.get("guidelines", []):
            key = guideline.get("url")
            if key and key not in seen_guideline:
                guidelines.append(guideline)
                seen_guideline.add(key)

        for policy in part.get("policies", []):
            key = policy.get("url")
            if key and key not in seen_policy:
                policies.append(policy)
                seen_policy.add(key)

        style_notes.extend(part.get("style_notes", []))

        source = part.get("source")
        if source:
            sources.append(source)

    if not brand_hint:
        brand_hint = "Custom Brand"

    return {
        "schema_version": "1.0",
        "brand_id": slugify(brand_hint),
        "brand_name": brand_hint,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "logos": logos,
        "colors": counter_to_ranked_list(color_counter, "hex", max_colors),
        "fonts": counter_to_ranked_list(font_counter, "name", max_fonts),
        "guidelines": guidelines,
        "policies": policies,
        "style_notes": style_notes,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brand-name", help="Force brand name for output profile")
    parser.add_argument("--web-url", action="append", default=[], help="Brand website URL")
    parser.add_argument("--pptx", action="append", default=[], help="Path to PPTX file")
    parser.add_argument("--docx", action="append", default=[], help="Path to DOCX file")
    parser.add_argument("--max-colors", type=int, default=12)
    parser.add_argument("--max-fonts", type=int, default=8)
    parser.add_argument("--out", required=True, help="Path to write profile JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not (args.web_url or args.pptx or args.docx):
        print("Provide at least one source: --web-url, --pptx, or --docx", file=sys.stderr)
        return 2

    parts = []

    for url in args.web_url:
        try:
            part = extract_web_profile(url)
            part["source"] = {"type": "web", "value": url}
            parts.append(part)
        except Exception as exc:  # pragma: no cover
            print(f"Warning: failed to parse {url}: {exc}", file=sys.stderr)

    for pptx_path in args.pptx:
        path = Path(pptx_path)
        if not path.exists():
            print(f"Warning: missing PPTX {path}", file=sys.stderr)
            continue
        try:
            part = extract_pptx_profile(path)
            part["source"] = {"type": "pptx", "value": str(path)}
            parts.append(part)
        except Exception as exc:  # pragma: no cover
            print(f"Warning: failed to parse {path}: {exc}", file=sys.stderr)

    for docx_path in args.docx:
        path = Path(docx_path)
        if not path.exists():
            print(f"Warning: missing DOCX {path}", file=sys.stderr)
            continue
        try:
            part = extract_docx_profile(path)
            part["source"] = {"type": "docx", "value": str(path)}
            parts.append(part)
        except Exception as exc:  # pragma: no cover
            print(f"Warning: failed to parse {path}: {exc}", file=sys.stderr)

    if not parts:
        print("No valid sources were parsed", file=sys.stderr)
        return 1

    profile = merge_profiles(
        parts=parts,
        brand_name=args.brand_name,
        max_colors=max(1, args.max_colors),
        max_fonts=max(1, args.max_fonts),
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(profile, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Wrote profile: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

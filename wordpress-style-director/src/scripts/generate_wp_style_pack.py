#!/usr/bin/env python3
"""Generate a WordPress CSS style pack from a reference site, brand file, or creative brief."""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
FONT_FAMILY_RE = re.compile(r"font-family\s*:\s*([^;{}]+);", re.IGNORECASE)
URL_IN_CSS_RE = re.compile(r"url\(([^)]+)\)", re.IGNORECASE)
STYLESHEET_LINK_RE = re.compile(
    r"<link[^>]+rel=[\"'][^\"']*stylesheet[^\"']*[\"'][^>]+href=[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)

GENERIC_FONTS = {
    "serif",
    "sans-serif",
    "monospace",
    "system-ui",
    "ui-sans-serif",
    "ui-serif",
    "ui-monospace",
    "cursive",
    "fantasy",
    "emoji",
    "math",
    "fangsong",
    "inherit",
    "initial",
    "unset",
    "revert",
    "-apple-system",
    "blinkmacsystemfont",
    "segoe ui",
    "arial",
    "helvetica",
    "helvetica neue",
    "roboto",
}

CREATIVE_PROFILES = {
    "tech": {
        "colors": ["#0B132B", "#1C2541", "#3A506B", "#5BC0BE", "#E0FBFC", "#00D1FF"],
        "heading_font": "Space Grotesk",
        "body_font": "Inter",
    },
    "wellness": {
        "colors": ["#F7F7F2", "#E3EFE6", "#7CA982", "#2F4858", "#1E2A33", "#D8B26E"],
        "heading_font": "DM Serif Display",
        "body_font": "Source Sans 3",
    },
    "luxury": {
        "colors": ["#0F0F10", "#1B1B1E", "#6C5C3D", "#CBA135", "#E8E6E3", "#9F8A5A"],
        "heading_font": "Playfair Display",
        "body_font": "Manrope",
    },
    "vibrant": {
        "colors": ["#FFFFFF", "#F5F7FF", "#3A0CA3", "#7209B7", "#F72585", "#4CC9F0"],
        "heading_font": "Sora",
        "body_font": "Nunito Sans",
    },
    "minimal": {
        "colors": ["#FFFFFF", "#F4F4F5", "#D4D4D8", "#18181B", "#27272A", "#3F3F46"],
        "heading_font": "Outfit",
        "body_font": "Inter",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a WordPress CSS pack from style reference, brand guidelines, or a creative brief"
    )
    parser.add_argument("--mode", choices=["style-reference", "brand-guided", "creative"], required=True)
    parser.add_argument("--site-url", default="", help="Reference site URL for style-reference mode")
    parser.add_argument("--brand-file", default="", help="Path to brand guideline file (json/md/txt)")
    parser.add_argument("--brief", default="", help="Creative brief for creative mode")
    parser.add_argument("--site-name", default="", help="Site/brand name for output labeling")
    parser.add_argument("--max-css-files", type=int, default=8)
    parser.add_argument("--out-dir", default="output/wordpress-style-director")
    parser.add_argument("--run-name", default="", help="Optional fixed output folder name")
    parser.add_argument("--font-heading", default="", help="Override heading font")
    parser.add_argument("--font-body", default="", help="Override body font")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--deploy", action="store_true",
                        help="Auto-deploy the generated CSS to WordPress via REST API")
    parser.add_argument("--wp-url", default="",
                        help="WordPress site URL for deployment (e.g. https://example.com)")
    parser.add_argument("--env-file", default="",
                        help="Path to .env file with WP_APP_USERNAME and WP_APP_PASSWORD")
    parser.add_argument("--skip-verify", action="store_true",
                        help="Skip front-end verification after deployment")
    parser.add_argument(
        "--footer-credit-text",
        default="",
        help="Optional footer credit line injected in .site-info (for example: © 2026 | Proudly Powered by Thrivethroughtime)",
    )
    parser.add_argument(
        "--favicon-file",
        default="",
        help="Optional local favicon file (.png/.ico/.jpg) to upload and set as WordPress Site Icon during deploy",
    )
    return parser.parse_args()


def normalize_hex(value: str) -> str:
    raw = (value or "").strip().lower()
    if len(raw) == 4 and raw.startswith("#"):
        return "#" + "".join(ch * 2 for ch in raw[1:])
    return raw


def unique_preserve_order(items: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def color_luminance(hex_color: str) -> float:
    hex_color = normalize_hex(hex_color)
    if not re.match(r"^#[0-9a-f]{6}$", hex_color):
        return 0.0
    r = int(hex_color[1:3], 16) / 255.0
    g = int(hex_color[3:5], 16) / 255.0
    b = int(hex_color[5:7], 16) / 255.0

    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def color_saturation(hex_color: str) -> float:
    hex_color = normalize_hex(hex_color)
    if not re.match(r"^#[0-9a-f]{6}$", hex_color):
        return 0.0
    r = int(hex_color[1:3], 16) / 255.0
    g = int(hex_color[3:5], 16) / 255.0
    b = int(hex_color[5:7], 16) / 255.0
    return max(r, g, b) - min(r, g, b)


def sort_palette_for_roles(colors: List[str]) -> List[str]:
    return sorted(colors, key=color_luminance)


def fetch_text(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; wordpress-style-director/1.0)",
            "Accept": "text/html,text/css,*/*",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = "utf-8"
        ctype = resp.headers.get("Content-Type", "")
        m = re.search(r"charset=([a-zA-Z0-9_-]+)", ctype)
        if m:
            charset = m.group(1)
        return resp.read().decode(charset, errors="replace")


def extract_hex_colors(text: str) -> List[str]:
    return [normalize_hex(x) for x in HEX_RE.findall(text or "") if x]


def extract_fonts(text: str) -> List[str]:
    fonts: List[str] = []
    for block in FONT_FAMILY_RE.findall(text or ""):
        for raw in block.split(","):
            clean = raw.strip().strip("\"'")
            low = clean.lower()
            if not clean or low in GENERIC_FONTS:
                continue
            if clean.startswith("var("):
                continue
            if len(clean) > 80:
                continue
            fonts.append(clean)
    return fonts


def same_host(a: str, b: str) -> bool:
    return urllib.parse.urlparse(a).netloc.lower() == urllib.parse.urlparse(b).netloc.lower()


def extract_stylesheet_urls(html_text: str, base_url: str, max_css_files: int) -> List[str]:
    urls = [urllib.parse.urljoin(base_url, u) for u in STYLESHEET_LINK_RE.findall(html_text or "")]
    urls = [u for u in urls if u.lower().startswith(("http://", "https://"))]
    urls = [u for u in urls if same_host(base_url, u)]
    return unique_preserve_order(urls)[:max(0, max_css_files)]


def crawl_style_reference(site_url: str, max_css_files: int) -> Tuple[collections.Counter, collections.Counter, Dict[str, Any]]:
    html_text = fetch_text(site_url)
    css_urls = extract_stylesheet_urls(html_text, site_url, max_css_files)

    color_counter = collections.Counter(extract_hex_colors(html_text))
    font_counter = collections.Counter(extract_fonts(html_text))
    fetched_css: List[str] = []

    for css_url in css_urls:
        try:
            css = fetch_text(css_url)
        except Exception:
            continue
        fetched_css.append(css_url)
        color_counter.update(extract_hex_colors(css))
        font_counter.update(extract_fonts(css))

        # Also include nested CSS url() imports if same host and .css suffix.
        for candidate in URL_IN_CSS_RE.findall(css):
            ref = candidate.strip().strip("\"'")
            nested = urllib.parse.urljoin(css_url, ref)
            if not nested.lower().endswith(".css"):
                continue
            if not same_host(site_url, nested):
                continue
            if nested in fetched_css:
                continue
            if len(fetched_css) >= max_css_files:
                break
            try:
                nested_css = fetch_text(nested)
            except Exception:
                continue
            fetched_css.append(nested)
            color_counter.update(extract_hex_colors(nested_css))
            font_counter.update(extract_fonts(nested_css))

    meta = {
        "site_url": site_url,
        "stylesheets_found": len(css_urls),
        "stylesheets_fetched": fetched_css,
    }
    return color_counter, font_counter, meta


def collect_strings(value: Any) -> List[str]:
    out: List[str] = []
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            out.extend(collect_strings(v))
    elif isinstance(value, list):
        for v in value:
            out.extend(collect_strings(v))
    return out


def parse_brand_guidelines(path: Path) -> Tuple[collections.Counter, collections.Counter, Dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    payload: Any = None
    strings: List[str] = []
    color_counter = collections.Counter()
    font_counter = collections.Counter()

    try:
        payload = json.loads(text)
    except Exception:
        payload = None

    if payload is not None:
        strings = collect_strings(payload)
        # Prioritize explicit typography fields in structured files.
        if isinstance(payload, dict):
            queue: List[Tuple[List[str], Any]] = [([], payload)]
            while queue:
                key_path, node = queue.pop(0)
                if isinstance(node, dict):
                    for k, v in node.items():
                        queue.append((key_path + [str(k)], v))
                elif isinstance(node, list):
                    for idx, v in enumerate(node):
                        queue.append((key_path + [str(idx)], v))
                elif isinstance(node, str):
                    path_text = " ".join(key_path).lower()
                    candidate = node.strip().strip("\"'")
                    if re.match(r"^#[0-9a-fA-F]{3,6}$", candidate):
                        continue
                    if "http://" in candidate.lower() or "https://" in candidate.lower():
                        continue
                    if any(token in path_text for token in ["font", "type", "typography", "heading", "body"]):
                        if re.match(r"^[A-Za-z0-9 /-]{2,50}$", candidate):
                            low = candidate.lower()
                            if low not in GENERIC_FONTS:
                                font_counter.update([candidate])
    else:
        strings = [text]

    for chunk in strings:
        color_counter.update(extract_hex_colors(chunk))
        font_counter.update(extract_fonts(chunk))

        # Also catch common pattern: "Primary font: Inter"
        for m in re.findall(r"(?:font|typeface|typography)[:\s-]+([A-Za-z0-9 \-/]{2,50})", chunk, re.IGNORECASE):
            clean = m.strip().strip("\"'")
            if clean and clean.lower() not in GENERIC_FONTS:
                font_counter.update([clean])

    return color_counter, font_counter, {"brand_file": str(path)}


def choose_creative_profile(brief: str) -> str:
    text = (brief or "").lower()
    keywords = {
        "tech": ["ai", "tech", "future", "saas", "fintech", "digital"],
        "wellness": ["health", "wellness", "nature", "calm", "mindful", "longevity"],
        "luxury": ["luxury", "premium", "high-end", "elegant", "editorial"],
        "vibrant": ["bold", "playful", "vibrant", "colorful", "creative"],
        "minimal": ["minimal", "clean", "simple", "neutral", "modern"],
    }
    best = "tech"
    best_score = -1
    for name, words in keywords.items():
        score = sum(1 for w in words if w in text)
        if score > best_score:
            best = name
            best_score = score
    return best


def ensure_palette(colors: List[str], fallback: List[str], min_size: int = 6) -> List[str]:
    merged = unique_preserve_order(colors + fallback)
    valid = [c for c in merged if re.match(r"^#[0-9a-f]{6}$", normalize_hex(c))]
    if len(valid) < min_size:
        valid.extend([c for c in fallback if c not in valid])
    return valid[:max(min_size, len(valid))]


def decide_dark_mode(brief: str, colors: List[str]) -> bool:
    text = (brief or "").lower()
    if any(word in text for word in ["dark", "night", "charcoal", "black"]):
        return True
    if any(word in text for word in ["light", "white", "airy", "bright"]):
        return False
    if not colors:
        return False
    sorted_by_lum = sort_palette_for_roles(colors)
    median = color_luminance(sorted_by_lum[len(sorted_by_lum) // 2])
    return median < 0.42


def is_usable_font_name(name: str) -> bool:
    low = (name or "").strip().lower()
    if not low:
        return False
    if low in GENERIC_FONTS:
        return False
    if low.startswith("var("):
        return False
    bad_tokens = ["fontawesome", "glyphicons", "icon", "icons", "fa-"]
    if any(token in low for token in bad_tokens):
        return False
    return True


def choose_fonts(font_counter: collections.Counter, fallback_heading: str, fallback_body: str) -> Tuple[str, str]:
    ranked = []
    for name, _ in font_counter.most_common(10):
        if not is_usable_font_name(name):
            continue
        ranked.append(name)
    heading = ranked[0] if ranked else fallback_heading
    body = ranked[1] if len(ranked) > 1 else (ranked[0] if ranked else fallback_body)
    return heading, body


def assign_roles(colors: List[str], dark_mode: bool) -> Dict[str, str]:
    sorted_colors = sort_palette_for_roles(colors)
    if len(sorted_colors) < 6:
        sorted_colors = ensure_palette(sorted_colors, CREATIVE_PROFILES["minimal"]["colors"], min_size=6)

    darkest = sorted_colors[0]
    second_darkest = sorted_colors[1]
    lightest = sorted_colors[-1]
    second_lightest = sorted_colors[-2]

    accent_candidates = [c for c in colors if c not in {darkest, second_darkest, lightest, second_lightest}]
    if not accent_candidates:
        accent_candidates = colors

    accent_candidates = sorted(
        accent_candidates,
        key=lambda c: (color_saturation(c), -abs(color_luminance(c) - 0.52)),
        reverse=True,
    )
    primary = accent_candidates[0]
    accent = accent_candidates[1] if len(accent_candidates) > 1 else colors[-1]

    if dark_mode:
        background = darkest
        surface = second_darkest
        text = lightest
        muted = second_lightest
    else:
        background = lightest
        surface = second_lightest
        text = darkest
        muted = second_darkest

    border = second_darkest if not dark_mode else second_lightest

    return {
        "background": background,
        "surface": surface,
        "text": text,
        "muted": muted,
        "primary": primary,
        "accent": accent,
        "link": primary,
        "link_hover": accent,
        "border": border,
    }


def font_stack(font_name: str, fallback: str) -> str:
    clean = font_name.strip().strip("\"'")
    if " " in clean:
        clean = f"'{clean}'"
    return f"{clean}, {fallback}"


def build_tokens_css(site_name: str, roles: Dict[str, str], heading_font: str, body_font: str) -> str:
    return f"""/* Auto-generated by wordpress-style-director */
/* Site: {site_name or 'WordPress site'} */
:root {{
  --wsd-bg: {roles['background']};
  --wsd-surface: {roles['surface']};
  --wsd-text: {roles['text']};
  --wsd-muted: {roles['muted']};
  --wsd-primary: {roles['primary']};
  --wsd-accent: {roles['accent']};
  --wsd-link: {roles['link']};
  --wsd-link-hover: {roles['link_hover']};
  --wsd-border: {roles['border']};
  --wsd-font-heading: {font_stack(heading_font, 'system-ui, sans-serif')};
  --wsd-font-body: {font_stack(body_font, 'system-ui, sans-serif')};
  --wsd-radius: 12px;
  --wsd-shadow: 0 10px 30px rgba(0, 0, 0, 0.12);
  --wsd-content-max: 760px;
  --wsd-line: 1.75;
}}
"""


def build_wordpress_overrides_css() -> str:
    return """/* WordPress presentation overrides */

/* --- Global base --- */
body {
  background: var(--wsd-bg) !important;
  color: var(--wsd-text) !important;
  font-family: var(--wsd-font-body) !important;
  font-size: 18px;
  line-height: var(--wsd-line);
}

.site-content,
#content,
#primary {
  background-color: var(--wsd-bg);
  color: var(--wsd-text);
}

/* --- Headings (exclude .site-title — handled separately) --- */
h1, h2, h3, h4, h5, h6,
.entry-title,
.page-title,
.wp-block-heading {
  font-family: var(--wsd-font-heading) !important;
  color: var(--wsd-text);
  letter-spacing: -0.01em;
}

/* --- Header — preserve theme header image --- */
.site-header,
header#masthead {
  /* Do NOT override background — themes often use header images */
}

.site-title,
.site-title a {
  font-family: var(--wsd-font-heading) !important;
  color: #FFFFFF !important;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.5);
  text-decoration: none !important;
}

.site-description {
  color: rgba(255, 255, 255, 0.85) !important;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
}

/* --- Body content with readable sizes --- */
.entry-content,
.entry-content p,
.entry-content li,
.widget,
.widget p,
.widget li {
  text-align: left !important;
  line-height: var(--wsd-line);
  color: var(--wsd-text) !important;
  font-size: 1.2rem !important;
}

.entry-content {
  max-width: var(--wsd-content-max);
}

.entry-content p {
  font-size: 1.2rem !important;
}

/* Article excerpt / summary on homepage */
.entry-summary,
.entry-summary p,
.post-card p,
article .entry-summary {
  font-size: 1.15rem !important;
  line-height: var(--wsd-line);
  color: var(--wsd-text) !important;
}

.entry-content a,
.widget a {
  color: var(--wsd-link) !important;
  text-decoration-thickness: 1.5px;
  text-underline-offset: 2px;
}

.entry-content a:hover,
.widget a:hover {
  color: var(--wsd-link-hover) !important;
}

/* --- Navigation --- */
.main-navigation a,
.primary-menu a,
.site-header .menu a {
  color: var(--wsd-text) !important;
  text-decoration: none !important;
}

.main-navigation a:hover,
.primary-menu a:hover,
.site-header .menu a:hover {
  color: var(--wsd-link) !important;
}

blockquote {
  margin: 1.4rem 0;
  padding: 0.9rem 1rem;
  border-left: 4px solid var(--wsd-primary);
  background: color-mix(in srgb, var(--wsd-surface) 88%, transparent);
}

pre,
code {
  background: color-mix(in srgb, var(--wsd-surface) 92%, transparent);
  border: 1px solid color-mix(in srgb, var(--wsd-border) 30%, transparent);
}

pre {
  border-radius: 8px;
  padding: 0.8rem 0.9rem;
  overflow-x: auto;
}

img,
.wp-post-image {
  border-radius: var(--wsd-radius);
}

.entry-content .sources-block,
.entry-content .sources-list,
.entry-content .sources-list li {
  text-align: left !important;
  word-spacing: normal !important;
  letter-spacing: normal !important;
}

.entry-content .sources-list {
  padding-left: 1.2rem;
}

.entry-content .citation {
  text-decoration: none;
  font-weight: 600;
}

/* --- Sidebar — high-specificity to override theme dark styles --- */
#secondary,
aside.sidebar,
.sidebar {
  background: var(--wsd-bg) !important;
}

#secondary .widget,
aside.sidebar .widget,
.sidebar .widget,
body .widget {
  background: var(--wsd-surface) !important;
  border: 1px solid var(--wsd-border) !important;
  border-radius: var(--wsd-radius);
  padding: 1rem !important;
  color: var(--wsd-text) !important;
}

#secondary .widget *,
aside.sidebar .widget *,
.sidebar .widget * {
  color: var(--wsd-text);
}

#secondary .widget a,
aside.sidebar .widget a,
.sidebar .widget a {
  color: var(--wsd-link) !important;
}

#secondary .widget a:hover,
aside.sidebar .widget a:hover,
.sidebar .widget a:hover {
  color: var(--wsd-link-hover) !important;
}

.widget-title {
  font-family: var(--wsd-font-heading) !important;
  color: var(--wsd-text) !important;
  background: transparent !important;
}

button,
input[type='submit'],
.wp-block-button__link {
  background: var(--wsd-primary) !important;
  color: #FFFFFF !important;
  border: none !important;
  border-radius: 999px;
  padding: 0.55rem 1rem;
}

button:hover,
input[type='submit']:hover,
.wp-block-button__link:hover {
  background: var(--wsd-accent) !important;
}

/* Read More / Continue Reading (Nisarg + Bootstrap variants) */
p.read-more a.btn.btn-default,
p.read-more a.btn.btn-default:link,
p.read-more a.btn.btn-default:visited,
p.read-more a.btn.btn-default:active,
p.read-more a.btn.btn-default:focus,
.entry-summary a.btn.btn-default,
.entry-summary a.btn.btn-default:link,
.entry-summary a.btn.btn-default:visited,
a.more-link,
a.more-link:link,
a.more-link:visited,
.more-link,
.more-link:link,
.more-link:visited {
  background: var(--wsd-primary) !important;
  color: #FFFFFF !important;
  border: 1px solid var(--wsd-primary) !important;
  text-decoration: none !important;
  text-shadow: none !important;
  font-size: 0.84rem !important;
  font-weight: 700 !important;
  letter-spacing: 0.06em !important;
  line-height: 1.15 !important;
  text-indent: 0 !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  min-height: 2.2rem !important;
  padding: 0.55rem 1.1rem !important;
}

p.read-more a.btn.btn-default *,
.entry-summary a.btn.btn-default *,
a.more-link *,
.more-link * {
  color: #FFFFFF !important;
}

p.read-more a.btn.btn-default:hover,
p.read-more a.btn.btn-default:focus,
.entry-summary a.btn.btn-default:hover,
.entry-summary a.btn.btn-default:focus,
a.more-link:hover,
a.more-link:focus,
.more-link:hover,
.more-link:focus {
  background: var(--wsd-accent) !important;
  border-color: var(--wsd-accent) !important;
  color: #FFFFFF !important;
}

p.read-more a.btn.btn-default::before,
p.read-more a.btn.btn-default::after,
.entry-summary a.btn.btn-default::before,
.entry-summary a.btn.btn-default::after,
a.more-link::before,
a.more-link::after,
.more-link::before,
.more-link::after {
  content: none !important;
}
"""


def build_dark_mode_neutralization_css() -> str:
    """Override common WordPress theme dark mode rules.

    Many themes (e.g. Nisarg) add a ``body.dark`` class that sets dark
    backgrounds (#121212/#212121) and light text (rgba(255,255,255,0.87)).
    This section neutralizes those rules to enforce our palette.
    """
    return """
/* =========================================================
   DARK MODE NEUTRALIZATION
   Override body.dark rules from themes like Nisarg, flavor, etc.
   ========================================================= */
body.dark {
  background-color: var(--wsd-bg) !important;
  color: var(--wsd-text) !important;
}

.dark .main-navigation {
  background-color: var(--wsd-bg) !important;
}

.dark .post-content,
.dark .single-post-content,
.dark .post-comments,
.dark .comments-area,
.dark .posts-navigation .nav-links,
.dark .post-navigation .nav-links,
.dark .nav-previous,
.dark .nav-next,
.dark .next-post,
.dark .prev-post,
.dark .pagination .page-numbers,
.dark .author-bio,
.dark blockquote,
.dark input,
.dark select,
.dark textarea,
.dark thead {
  background: var(--wsd-surface) !important;
}

.dark #secondary .widget {
  background: var(--wsd-surface) !important;
  color: var(--wsd-text) !important;
}

.dark .main-navigation .primary-menu > li > .sub-menu,
.dark .sub-menu {
  background-color: var(--wsd-surface) !important;
  border-color: var(--wsd-border) !important;
}

/* Dark mode text colors — force to our palette */
body.dark,
.dark .entry-summary,
.dark .entry-content,
.dark #secondary .widget,
.dark #secondary .widget a,
.dark .main-navigation .primary-menu > li > a,
.dark .main-navigation .primary-menu > li > .sub-menu > li > a,
.dark .main-navigation ul ul a,
.dark .next-post a,
.dark .prev-post a,
.dark input[type=text],
.dark input[type=email],
.dark select {
  color: var(--wsd-text) !important;
}

.dark h1,
.dark h2,
.dark h3,
.dark h4,
.dark h5,
.dark h6,
.dark .entry-header .entry-title a,
.dark #secondary .widget .widget-title,
.dark blockquote,
.dark .pagination .page-numbers {
  color: var(--wsd-text) !important;
}

.dark .entry-meta,
.dark .entry-meta a,
.dark .cat-links a,
.dark .tags-links a {
  color: var(--wsd-muted) !important;
}

.dark .entry-content a,
.dark .entry-summary a,
.dark #secondary .widget a {
  color: var(--wsd-link) !important;
}

.dark .entry-content a:hover,
.dark .entry-summary a:hover,
.dark #secondary .widget a:hover {
  color: var(--wsd-link-hover) !important;
}

.dark input,
.dark textarea,
.dark #secondary .widget li {
  border-color: var(--wsd-border) !important;
}

/* Keep header text white in dark mode (over dark header image) */
.dark .site-title,
.dark .site-title a,
.dark .site-description {
  color: #FFFFFF !important;
}

.dark #secondary .widget .widget-title {
  background: transparent !important;
}

.dark .main-navigation .menu-toggle .icon-bar {
  background-color: var(--wsd-text) !important;
}
"""


def css_string_literal(value: str) -> str:
    value = (value or "").replace("\\", "\\\\").replace('"', '\\"')
    return value


def should_apply_ttt_footer(site_name: str, wp_url: str, site_url: str) -> bool:
    haystack = " ".join([site_name or "", wp_url or "", site_url or ""]).lower()
    return ("thrivethroughtime" in haystack) or ("timeless wisdom" in haystack)


def build_footer_credit_css(footer_text: str) -> str:
    escaped = css_string_literal(footer_text.strip())
    if not escaped:
        return ""
    return f"""
/* =========================================================
   HOTFIX: Footer Credits Text
   ========================================================= */
footer#colophon .site-info,
.site-footer .site-info {{
  text-align: center !important;
  font-size: 0 !important;
  line-height: 1.5 !important;
  padding: 0.4rem 1rem !important;
}}

footer#colophon .site-info *,
.site-footer .site-info * {{
  display: none !important;
}}

footer#colophon .site-info::before,
.site-footer .site-info::before {{
  content: "{escaped}";
  display: inline-block;
  font-family: var(--wsd-font-body, "Source Sans 3", sans-serif);
  font-size: clamp(1.15rem, 1.55vw, 1.45rem) !important;
  font-weight: 700 !important;
  line-height: 1.65 !important;
  color: var(--wsd-bg-alt, #FFFFFF) !important;
  letter-spacing: 0.025em !important;
}}

@media (max-width: 600px) {{
  footer#colophon .site-info::before,
  .site-footer .site-info::before {{
    font-size: 1.05rem !important;
  }}
}}
"""


def choose_mode_inputs(args: argparse.Namespace) -> Tuple[List[str], collections.Counter, str, str, Dict[str, Any]]:
    if args.mode == "style-reference":
        site_url = (args.site_url or "").strip()
        if not site_url:
            raise SystemExit("--site-url is required in style-reference mode")
        color_counter, font_counter, meta = crawl_style_reference(site_url, args.max_css_files)
        colors = [c for c, _ in color_counter.most_common(12)]
        if not colors:
            colors = CREATIVE_PROFILES["tech"]["colors"]
        heading, body = choose_fonts(
            font_counter,
            fallback_heading=CREATIVE_PROFILES["tech"]["heading_font"],
            fallback_body=CREATIVE_PROFILES["tech"]["body_font"],
        )
        return colors, font_counter, heading, body, meta

    if args.mode == "brand-guided":
        brand_file = Path((args.brand_file or "").strip())
        if not brand_file.exists():
            raise SystemExit("--brand-file is required in brand-guided mode and must exist")
        color_counter, font_counter, meta = parse_brand_guidelines(brand_file)
        colors = [c for c, _ in color_counter.most_common(12)]
        fallback = CREATIVE_PROFILES["minimal"]
        heading, body = choose_fonts(
            font_counter,
            fallback_heading=fallback["heading_font"],
            fallback_body=fallback["body_font"],
        )
        return colors, font_counter, heading, body, meta

    brief = (args.brief or "").strip()
    if not brief:
        raise SystemExit("--brief is required in creative mode")
    profile_name = choose_creative_profile(brief)
    profile = CREATIVE_PROFILES[profile_name]
    colors = profile["colors"]
    font_counter = collections.Counter({profile["heading_font"]: 2, profile["body_font"]: 1})
    meta = {"creative_profile": profile_name, "brief": brief}
    return colors, font_counter, profile["heading_font"], profile["body_font"], meta


def run_output_dir(base: str, run_name: str, mode: str) -> Path:
    root = Path(base)
    if run_name:
        folder = run_name
    else:
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        folder = f"{stamp}-{mode}"
    out = root / folder
    out.mkdir(parents=True, exist_ok=True)
    return out


def main() -> None:
    args = parse_args()

    colors, font_counter, heading_font, body_font, mode_meta = choose_mode_inputs(args)

    fallback_profile = CREATIVE_PROFILES["minimal"]
    palette = ensure_palette(colors, fallback_profile["colors"], min_size=6)

    context_text = f"{args.brief} {args.site_name}"
    dark_mode = decide_dark_mode(context_text, palette)
    roles = assign_roles(palette, dark_mode=dark_mode)

    heading_font = (args.font_heading or heading_font or fallback_profile["heading_font"]).strip()
    body_font = (args.font_body or body_font or fallback_profile["body_font"]).strip()

    out = run_output_dir(args.out_dir, args.run_name, args.mode)

    tokens_css = build_tokens_css(args.site_name, roles, heading_font, body_font)
    overrides_css = build_wordpress_overrides_css()
    dark_mode_css = build_dark_mode_neutralization_css()
    combined_css = tokens_css + "\n" + dark_mode_css + "\n" + overrides_css

    footer_credit_text = (args.footer_credit_text or "").strip()
    if not footer_credit_text and should_apply_ttt_footer(
        args.site_name, args.wp_url, args.site_url
    ):
        footer_credit_text = (
            f"© {dt.datetime.now().year} | Proudly Powered by Thrivethroughtime"
        )
    if footer_credit_text:
        combined_css += "\n" + build_footer_credit_css(footer_credit_text)

    summary = {
        "mode": args.mode,
        "site_name": args.site_name,
        "dark_mode": dark_mode,
        "palette": palette,
        "roles": roles,
        "fonts": {
            "heading": heading_font,
            "body": body_font,
            "candidates": [name for name, _ in font_counter.most_common(12) if is_usable_font_name(name)][:8],
        },
        "mode_meta": mode_meta,
        "outputs": {
            "tokens_css": str(out / "tokens.css"),
            "wordpress_overrides_css": str(out / "wordpress-overrides.css"),
            "combined_css": str(out / "additional-css-combined.css"),
        },
        "guardrails": {
            "style_reference_policy": "Inspired-by styling only; avoid pixel-perfect cloning or trademarked branding reuse.",
        },
        "footer_credit_text": footer_credit_text,
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
    }

    if args.dry_run:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    (out / "tokens.css").write_text(tokens_css, encoding="utf-8")
    (out / "wordpress-overrides.css").write_text(overrides_css, encoding="utf-8")
    (out / "additional-css-combined.css").write_text(combined_css, encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote style pack to: {out}")
    print(f"- {out / 'tokens.css'}")
    print(f"- {out / 'wordpress-overrides.css'}")
    print(f"- {out / 'additional-css-combined.css'}")
    print(f"- {out / 'summary.json'}")

    # --- Auto-deploy to WordPress if requested ---
    if args.deploy:
        wp_url = (args.wp_url or args.site_url or "").strip()
        if not wp_url:
            print("\n[deploy] ERROR: --wp-url is required for deployment")
            raise SystemExit(1)

        from deploy_to_wordpress import deploy as wp_deploy

        print(f"\n{'=' * 50}")
        print("DEPLOYING TO WORDPRESS")
        print(f"{'=' * 50}")
        css_file = str(out / "additional-css-combined.css")
        result = wp_deploy(
            css_file=css_file,
            wp_url=wp_url,
            site_name=args.site_name,
            env_file=args.env_file or None,
            skip_verify=args.skip_verify,
            favicon_file=args.favicon_file or None,
        )
        # Append deployment info to summary
        summary["deployment"] = result
        (out / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n[deploy] Deployment complete. Summary updated.")


if __name__ == "__main__":
    main()

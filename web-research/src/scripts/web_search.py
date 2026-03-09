#!/usr/bin/env python3
"""Domain-aware web search helper.

This script fetches *candidate sources* for a topic and prints them in JSON or
markdown. It is designed to support an agent that will still curate and cite
the final sources.

Supported modes:
- news: recent reporting (via GDELT) + optional targeted web results
- health: recent studies (via PubMed)
- ai: recent papers (via arXiv) + optional community signal (Reddit/Substack/X)
- finance: recent finance news (via GDELT) + optional primary sources (SEC/macros)
- general: broad web results (via DuckDuckGo HTML)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
import urllib.parse
from dataclasses import dataclass, asdict
from typing import Any, Iterable, Literal

import requests
from dateutil import parser as date_parser
from lxml import etree, html


Mode = Literal["auto", "news", "health", "ai", "finance", "general"]
OutputFormat = Literal["json", "markdown"]


USER_AGENT = "web-research-skill/0.1 (https://example.invalid)"

NEWS_TIER_C_DOMAINS = {
    "reuters.com",
    "apnews.com",
    "bbc.co.uk",
    "npr.org",
    "theguardian.com",
    "ft.com",
    "wsj.com",
    "bloomberg.com",
    "technologyreview.com",
    "wired.com",
    "arstechnica.com",
    "theverge.com",
    "techcrunch.com",
}

HEALTH_TIER_A_DOMAINS = {
    "who.int",
    "cdc.gov",
    "nih.gov",
    "nlm.nih.gov",
    "fda.gov",
    "ema.europa.eu",
    "nice.org.uk",
    "clinicaltrials.gov",
    "pubmed.ncbi.nlm.nih.gov",
}

AI_TIER_B_DOMAINS = {
    "arxiv.org",
    "openreview.net",
    "aclanthology.org",
    "papers.nips.cc",
}

AI_TIER_C_DOMAINS = {
    "hai.stanford.edu",
    "nist.gov",
    "oecd.ai",
    "technologyreview.com",
}

FINANCE_TIER_A_DOMAINS = {
    "sec.gov",
    "edgar.sec.gov",
    "federalreserve.gov",
    "bls.gov",
    "bea.gov",
    "fred.stlouisfed.org",
    "ecb.europa.eu",
    "imf.org",
    "worldbank.org",
}

COMMUNITY_DOMAINS = {"reddit.com", "substack.com", "x.com"}


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    origin: str | None = None
    source: str | None = None
    domain: str | None = None
    published_at: str | None = None
    snippet: str | None = None
    tier: str | None = None
    mode: str | None = None


def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _domain_from_url(url: str) -> str | None:
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host or None
    except Exception:
        return None


def _tier_for_domain(domain: str | None) -> str | None:
    if not domain:
        return None
    if domain.endswith(".gov") or domain.endswith(".mil") or domain.endswith(".int") or domain.endswith(".europa.eu"):
        return "A"
    if domain in HEALTH_TIER_A_DOMAINS or domain in FINANCE_TIER_A_DOMAINS:
        return "A"
    if domain in AI_TIER_B_DOMAINS:
        return "B"
    if domain in NEWS_TIER_C_DOMAINS or domain in AI_TIER_C_DOMAINS:
        return "C"
    if domain in COMMUNITY_DOMAINS:
        return "E"
    return None


def guess_mode(query: str) -> Mode:
    q = query.lower()
    if re.search(r"\b(trial|meta-analysis|systematic review|side effects?|dosage|mg|disease|symptom|vaccine|guideline)\b", q):
        return "health"
    if re.search(r"\b(10-k|10-q|earnings|guidance|sec|edgar|inflation|gdp|cpi|fomc|fed|ecb|bond|yield|stock|equity)\b", q):
        return "finance"
    if re.search(r"\b(llm|gpt|transformer|diffusion|arxiv|openreview|benchmark|model release|ai safety|alignment)\b", q):
        return "ai"
    if re.search(r"\b(latest|today|this week|breaking|announced|lawsuit|election|policy)\b", q):
        return "news"
    return "general"


def _requests_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def search_gdelt_news(query: str, *, max_records: int, since_days: int) -> list[SearchResult]:
    session = _requests_session()
    start = (_now_utc() - dt.timedelta(days=since_days)).strftime("%Y%m%d%H%M%S")
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": max_records,
        "sort": "datedesc",
        "startdatetime": start,
    }
    resp = session.get("https://api.gdeltproject.org/api/v2/doc/doc", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    results: list[SearchResult] = []
    for item in data.get("articles", []):
        url = item.get("url")
        title = item.get("title") or ""
        if not url or not title:
            continue
        domain = (item.get("domain") or _domain_from_url(url) or "").lower() or None
        seendate = item.get("seendate")
        published_at = None
        if seendate:
            # Example: 20251222T163000Z
            try:
                published_at = date_parser.parse(seendate).isoformat()
            except Exception:
                published_at = seendate
        results.append(
            SearchResult(
                title=title.strip(),
                url=url,
                origin="GDELT",
                domain=domain,
                published_at=published_at,
                tier=_tier_for_domain(domain),
                mode="news",
            )
        )
    return results


def search_pubmed(query: str, *, max_results: int, since_years: int, email: str | None) -> list[SearchResult]:
    session = _requests_session()
    today = _now_utc().date()
    try:
        start_date = today.replace(year=today.year - since_years)
    except ValueError:
        # Handle Feb 29th edge cases by approximating in days.
        start_date = today - dt.timedelta(days=365 * since_years)
    start_date_str = start_date.isoformat()
    # PubMed date filter: "YYYY/MM/DD"[dp] : "3000"[dp]
    date_filter = f'("{start_date_str}"[dp] : "3000"[dp])'
    term = f"({query}) AND {date_filter}"

    esearch_params = {
        "db": "pubmed",
        "term": term,
        "retmode": "json",
        "retmax": max_results,
        "sort": "pub date",
        "tool": "web-research-skill",
    }
    if email:
        esearch_params["email"] = email

    esearch = session.get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        params=esearch_params,
        timeout=30,
    )
    esearch.raise_for_status()
    ids = esearch.json().get("esearchresult", {}).get("idlist", []) or []
    if not ids:
        return []

    esummary_params = {
        "db": "pubmed",
        "id": ",".join(ids),
        "retmode": "json",
        "tool": "web-research-skill",
    }
    if email:
        esummary_params["email"] = email

    esummary = session.get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
        params=esummary_params,
        timeout=30,
    )
    esummary.raise_for_status()
    payload = esummary.json().get("result", {})

    results: list[SearchResult] = []
    for pmid in ids:
        item = payload.get(pmid)
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").strip().rstrip(".")
        if not title:
            continue
        pubdate = (item.get("pubdate") or item.get("epubdate") or "").strip() or None
        journal = (item.get("fulljournalname") or item.get("source") or "").strip() or None
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        results.append(
            SearchResult(
                title=title,
                url=url,
                origin="PubMed",
                source=journal,
                domain="pubmed.ncbi.nlm.nih.gov",
                published_at=pubdate,
                tier="B",
                mode="health",
            )
        )
    return results


def search_arxiv(query: str, *, max_results: int) -> list[SearchResult]:
    session = _requests_session()
    # Prefer CS/ML categories for AI-related queries to reduce irrelevant hits.
    cat_query = " OR ".join(
        [
            "cat:cs.AI",
            "cat:cs.CL",
            "cat:cs.LG",
            "cat:cs.CV",
            "cat:cs.RO",
            "cat:stat.ML",
        ]
    )
    params = {
        "search_query": f"({cat_query}) AND all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    resp = session.get("http://export.arxiv.org/api/query", params=params, timeout=30)
    resp.raise_for_status()

    root = etree.fromstring(resp.content)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    results: list[SearchResult] = []
    for entry in root.findall("atom:entry", namespaces=ns):
        title = (entry.findtext("atom:title", namespaces=ns) or "").strip()
        url = (entry.findtext("atom:id", namespaces=ns) or "").strip()
        published_at = (entry.findtext("atom:published", namespaces=ns) or "").strip() or None
        summary = (entry.findtext("atom:summary", namespaces=ns) or "").strip() or None
        if not title or not url:
            continue
        results.append(
            SearchResult(
                title=re.sub(r"\s+", " ", title),
                url=url,
                origin="arXiv",
                domain="arxiv.org",
                published_at=published_at,
                snippet=summary[:280] + ("…" if summary and len(summary) > 280 else "") if summary else None,
                tier="B",
                mode="ai",
            )
        )
    return results


def _ddg_extract_result_url(href: str) -> str:
    if href.startswith("//"):
        href = "https:" + href
    parsed = urllib.parse.urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        qs = urllib.parse.parse_qs(parsed.query)
        uddg = qs.get("uddg", [None])[0]
        if uddg:
            return urllib.parse.unquote(uddg)
    return href


def search_duckduckgo(query: str, *, max_results: int) -> list[SearchResult]:
    session = _requests_session()
    params = {"q": query}

    # DuckDuckGo sometimes throttles; keep requests minimal and retry lightly.
    for attempt in range(3):
        resp = session.get("https://duckduckgo.com/html/", params=params, timeout=30)
        if resp.status_code in {429, 503}:
            time.sleep(1.5 * (attempt + 1))
            continue
        resp.raise_for_status()
        doc = html.fromstring(resp.text)
        anchors = doc.xpath('//a[contains(concat(" ", normalize-space(@class), " "), " result__a ")]')

        results: list[SearchResult] = []
        for a in anchors[: max_results * 2]:
            title = (a.text_content() or "").strip()
            href = a.get("href") or ""
            url = _ddg_extract_result_url(href)
            domain = _domain_from_url(url)
            if not title or not url:
                continue
            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    origin="DuckDuckGo",
                    domain=domain,
                    tier=_tier_for_domain(domain),
                    mode="general",
                )
            )
            if len(results) >= max_results:
                break
        return results

    return []


def _dedupe(results: Iterable[SearchResult]) -> list[SearchResult]:
    seen: set[str] = set()
    out: list[SearchResult] = []
    for r in results:
        if r.url in seen:
            continue
        seen.add(r.url)
        out.append(r)
    return out


def run_search(
    query: str,
    *,
    mode: Mode,
    max_results: int,
    since_days: int,
    since_years: int,
    include_community: bool,
    email: str | None,
    strict: bool,
) -> tuple[Mode, list[SearchResult]]:
    if mode == "auto":
        mode = guess_mode(query)

    if mode == "news":
        raw = search_gdelt_news(query, max_records=max_results * 5, since_days=since_days)
        preferred = [r for r in raw if (r.domain or "") in NEWS_TIER_C_DOMAINS]
        fallback = [r for r in raw if r not in preferred]
        results = _dedupe((preferred + fallback)[:max_results])
        if strict:
            results = [r for r in results if r.tier in {"A", "B", "C"}]
        return mode, results

    if mode == "health":
        results = _dedupe(search_pubmed(query, max_results=max_results, since_years=since_years, email=email))
        if strict:
            results = [r for r in results if r.tier in {"A", "B", "C"}]
        return mode, results

    if mode == "ai":
        results: list[SearchResult] = []
        results.extend(search_arxiv(query, max_results=max_results))
        # Add recent reporting as context (separate signal from evidence when citing).
        news = search_gdelt_news(query, max_records=max_results * 5, since_days=since_days)
        news_preferred = [r for r in news if (r.domain or "") in NEWS_TIER_C_DOMAINS]
        results.extend(
            SearchResult(
                title=r.title,
                url=r.url,
                origin=r.origin,
                source=r.source,
                domain=r.domain,
                published_at=r.published_at,
                snippet=r.snippet,
                tier=r.tier,
                mode="ai",
            )
            for r in news_preferred[: max(1, max_results // 3)]
        )
        if include_community:
            for domain in sorted(COMMUNITY_DOMAINS):
                ddg = search_duckduckgo(f"site:{domain} {query}", max_results=max(2, max_results // 5))
                for r in ddg:
                    results.append(
                        SearchResult(
                            title=r.title,
                            url=r.url,
                            origin=r.origin,
                            source=r.source,
                            domain=r.domain,
                            published_at=r.published_at,
                            snippet=r.snippet,
                            tier="E",
                            mode="ai",
                        )
                    )
        results = _dedupe(results)[:max_results]
        if strict:
            results = [r for r in results if r.tier in {"A", "B", "C"}]
        return mode, results

    if mode == "finance":
        raw = search_gdelt_news(query, max_records=max_results * 5, since_days=since_days)
        preferred = [r for r in raw if (r.domain or "") in (NEWS_TIER_C_DOMAINS | FINANCE_TIER_A_DOMAINS)]
        fallback = [r for r in raw if r not in preferred]
        results = [
            SearchResult(
                title=r.title,
                url=r.url,
                origin=r.origin,
                source=r.source,
                domain=r.domain,
                published_at=r.published_at,
                snippet=r.snippet,
                tier=r.tier,
                mode="finance",
            )
            for r in _dedupe((preferred + fallback)[:max_results])
        ]
        if strict:
            results = [r for r in results if r.tier in {"A", "B", "C"}]
        return mode, results

    # general
    results = _dedupe(search_duckduckgo(query, max_results=max_results))
    if strict:
        results = [r for r in results if r.tier in {"A", "B", "C"}]
    return "general", results


def render_markdown(query: str, mode: Mode, results: list[SearchResult]) -> str:
    lines: list[str] = []
    lines.append(f"# Web search results ({mode})")
    lines.append("")
    lines.append(f"Query: `{query}`")
    lines.append("")
    if not results:
        lines.append("_No results._")
        return "\n".join(lines)

    for i, r in enumerate(results, start=1):
        parts = [f"{i}. {r.title}"]
        meta: list[str] = []
        if r.origin:
            meta.append(r.origin)
        if r.domain:
            meta.append(r.domain)
        if r.published_at:
            meta.append(r.published_at)
        if r.tier:
            meta.append(f"Tier {r.tier}")
        if meta:
            parts.append(f"— {' | '.join(meta)}")
        parts.append(f"\n   {r.url}")
        lines.append("".join(parts))
    return "\n".join(lines)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Domain-aware web research helper.")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--mode", default="auto", choices=["auto", "news", "health", "ai", "finance", "general"])
    parser.add_argument("--max-results", type=int, default=10)
    parser.add_argument("--since-days", type=int, default=14, help="Recency window for news/finance (days)")
    parser.add_argument("--since-years", type=int, default=5, help="Recency window for PubMed (years)")
    parser.add_argument("--include-community", action="store_true", help="Include Reddit/Substack/X results (signal only)")
    parser.add_argument("--strict", action="store_true", help="Only return Tier A/B/C sources")
    parser.add_argument("--email", default=None, help="Optional email for NCBI API politeness")
    parser.add_argument("--format", default="markdown", choices=["json", "markdown"])
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    mode, results = run_search(
        args.query,
        mode=args.mode,
        max_results=args.max_results,
        since_days=args.since_days,
        since_years=args.since_years,
        include_community=args.include_community,
        email=args.email,
        strict=args.strict,
    )

    if args.format == "json":
        payload: dict[str, Any] = {
            "query": args.query,
            "mode": mode,
            "generated_at": _now_utc().isoformat(),
            "results": [asdict(r) for r in results],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print(render_markdown(args.query, mode, results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

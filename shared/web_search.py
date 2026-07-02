import os
import json
import urllib.request
import urllib.parse
import urllib.error
import re
import html
import ssl
import time

from shared.logging_utils import get_logger
from shared.ssl_utils import get_ssl_context

log = get_logger("web_search")

# --- ddgs library (primary backend) ---------------------------------------
#
# ddgs (pip install ddgs, MIT licensed, https://github.com/deedy5/ddgs) is an
# actively maintained open-source metasearch client that aggregates results
# from DuckDuckGo, Bing, Brave, Google, Yahoo, Yandex, Mojeek, Startpage,
# etc. and handles the anti-scraping/User-Agent/markup churn for us instead
# of us maintaining brittle regexes against whichever HTML layout a given
# engine happens to be serving this week (which is what kept breaking with
# the raw DuckDuckGo scraper below).
#
# It's a normal pip dependency -- no server to self-host, no Docker, no API
# key -- so it packages into the Lambda deployment zip exactly like boto3 or
# certifi already do. Its only non-pure-python dependency is `primp` (a
# compiled Rust HTTP client), which just needs to be installed with
# `--platform manylinux2014_x86_64 --only-binary=:all:` when building the
# Lambda package/layer, same as pydantic-core already requires.
try:
    from ddgs import DDGS
    from ddgs.exceptions import DDGSException
    _DDGS_AVAILABLE = True
except ImportError:
    _DDGS_AVAILABLE = False


def search_ddgs(query: str, num_results: int = 5) -> list:
    """
    Search via the ddgs library (open-source, no API key, no self-hosted
    server). This is the primary search backend -- see web_search() below.
    Returns [] (never raises) on any failure so callers can safely fall
    through to the other backends.

    NOTE: this is the general TEXT search -- results have no publish date
    or source URL attached. For time-sensitive lookups use
    search_ddgs_news(); to get the source URL alongside the text (for
    citing where information came from) use search_ddgs_structured().
    """
    if not _DDGS_AVAILABLE:
        log.warning("<- ddgs library not installed (pip install ddgs); skipping to next backend.")
        return []

    log.info("-> ddgs search: %r", query)
    start = time.monotonic()

    try:
        raw_results = DDGS().text(query, max_results=num_results)
        elapsed = time.monotonic() - start

        results = []
        for item in raw_results:
            text = (item.get("body") or item.get("title") or "").strip()
            if text:
                results.append(text)

        if results:
            log.info("<- ddgs OK in %.2fs: %d result(s) for %r", elapsed, len(results), query)
        else:
            log.warning("<- ddgs returned 0 usable results in %.2fs for %r. Falling back to next backend.", elapsed, query)
        return results
    except DDGSException as e:
        elapsed = time.monotonic() - start
        log.warning(
            "<- ddgs search failed after %.2fs for %r: %s: %s (likely a transient rate limit/timeout "
            "against the underlying search engine). Falling back to next backend.",
            elapsed, query, type(e).__name__, e,
        )
        return []
    except Exception as e:
        elapsed = time.monotonic() - start
        log.warning("<- ddgs search failed after %.2fs for %r: %s: %s. Falling back to next backend.", elapsed, query, type(e).__name__, e)
        return []


def search_ddgs_structured(query: str, num_results: int = 5) -> list:
    """
    Like search_ddgs(), but keeps the source URL attached to each result:
    [{"text": "...", "url": "...", "title": "..."}, ...]. Used wherever we
    want to show the user *where* a piece of grounding info came from
    (a "Sources" list), not just feed the text into an LLM prompt.
    """
    if not _DDGS_AVAILABLE:
        return []

    log.info("-> ddgs structured search: %r", query)
    start = time.monotonic()

    try:
        raw_results = DDGS().text(query, max_results=num_results)
        elapsed = time.monotonic() - start

        results = []
        for item in raw_results:
            text = (item.get("body") or item.get("title") or "").strip()
            if text:
                results.append({
                    "text": text,
                    "url": (item.get("href") or "").strip(),
                    "title": (item.get("title") or "").strip(),
                })

        if results:
            log.info("<- ddgs structured OK in %.2fs: %d result(s) for %r", elapsed, len(results), query)
        else:
            log.info("<- ddgs structured returned 0 results in %.2fs for %r.", elapsed, query)
        return results
    except DDGSException as e:
        elapsed = time.monotonic() - start
        log.warning("<- ddgs structured search failed after %.2fs for %r: %s: %s", elapsed, query, type(e).__name__, e)
        return []
    except Exception as e:
        elapsed = time.monotonic() - start
        log.warning("<- ddgs structured search failed after %.2fs for %r: %s: %s", elapsed, query, type(e).__name__, e)
        return []


def search_ddgs_news(query: str, num_results: int = 5, timelimit: str = "m") -> list:
    """
    Search via ddgs's news backend. Unlike search_ddgs()'s general text
    search, news results carry a publish date -- important because a plain
    text search happily surfaces a five-year-old article about a
    long-resolved outbreak, a lifted travel ban, or a past-tense weather
    event with nothing marking it as stale. An LLM fed that snippet with no
    date attached has no way to know it's not describing the present.

    Returns [{"text": "[YYYY-MM-DD] snippet text", "url", "title", "date"}]
    -- the date is baked into "text" so it's visible to whatever consumes
    this (an LLM prompt), and also kept as its own field for source
    tracking. The caller/prompt should still explicitly reason about
    whether a dated item is still relevant, since "published recently" and
    "still true today" aren't the same thing.

    timelimit follows ddgs conventions: "d" (past day), "w" (past week),
    "m" (past month), "y" (past year). Defaults to "m" -- recent enough to
    catch genuinely current advisories without coming back empty for
    smaller/less-newsworthy destinations.
    """
    if not _DDGS_AVAILABLE:
        return []

    log.info("-> ddgs news search: %r (timelimit=%s)", query, timelimit)
    start = time.monotonic()

    try:
        raw_results = DDGS().news(query, max_results=num_results, timelimit=timelimit)
        elapsed = time.monotonic() - start

        results = []
        for item in raw_results:
            text = (item.get("body") or item.get("title") or "").strip()
            pub_date = (item.get("date") or "").strip()
            if text:
                results.append({
                    "text": f"[{pub_date or 'date unknown'}] {text}",
                    "url": (item.get("url") or "").strip(),
                    "title": (item.get("title") or "").strip(),
                    "date": pub_date,
                })

        if results:
            log.info("<- ddgs news OK in %.2fs: %d dated result(s) for %r", elapsed, len(results), query)
        else:
            log.info(
                "<- ddgs news returned 0 results in %.2fs for %r (timelimit=%s) -- "
                "nothing recent found, caller should fall back to undated search.",
                elapsed, query, timelimit,
            )
        return results
    except DDGSException as e:
        elapsed = time.monotonic() - start
        log.warning("<- ddgs news search failed after %.2fs for %r: %s: %s", elapsed, query, type(e).__name__, e)
        return []
    except Exception as e:
        elapsed = time.monotonic() - start
        log.warning("<- ddgs news search failed after %.2fs for %r: %s: %s", elapsed, query, type(e).__name__, e)
        return []


def search_ddgs_images(query: str, num_results: int = 6) -> list:
    """
    Search via ddgs's image backend. Returns
    [{"title", "image", "thumbnail", "source_url"}, ...] -- "image" is the
    full-resolution image URL, "thumbnail" a smaller preview (falls back to
    the full image if no thumbnail is given), and "source_url" the page the
    image was found on (so the UI can credit/link back to it). Never
    raises; returns [] on any failure so images are always treated as
    optional/best-effort.
    """
    if not _DDGS_AVAILABLE:
        return []

    log.info("-> ddgs image search: %r", query)
    start = time.monotonic()

    try:
        raw_results = DDGS().images(query, max_results=num_results)
        elapsed = time.monotonic() - start

        results = []
        for item in raw_results:
            image_url = (item.get("image") or "").strip()
            if not image_url:
                continue
            results.append({
                "title": (item.get("title") or "").strip(),
                "image": image_url,
                "thumbnail": (item.get("thumbnail") or image_url).strip(),
                "source_url": (item.get("url") or "").strip(),
            })

        if results:
            log.info("<- ddgs images OK in %.2fs: %d image(s) for %r", elapsed, len(results), query)
        else:
            log.info("<- ddgs images returned 0 results in %.2fs for %r.", elapsed, query)
        return results
    except DDGSException as e:
        elapsed = time.monotonic() - start
        log.warning("<- ddgs image search failed after %.2fs for %r: %s: %s", elapsed, query, type(e).__name__, e)
        return []
    except Exception as e:
        elapsed = time.monotonic() - start
        log.warning("<- ddgs image search failed after %.2fs for %r: %s: %s", elapsed, query, type(e).__name__, e)
        return []


# --- DuckDuckGo HTML scraping (last-resort fallback) -----------------------
#
# Kept only as a zero-dependency last resort in case the ddgs library isn't
# installed or its underlying engines are all down. DuckDuckGo's markup has
# shifted at least three times on us:
#   1. The original html.duckduckgo.com/html/ page used BEM-style double
#      underscore classes, e.g. class="result__snippet".
#   2. It later started carrying extra classes alongside that
#      (class="result__snippet js-result-snippet"), breaking an exact-match
#      regex.
#   3. Most recently, html.duckduckgo.com/html/ served a near-empty shell
#      with no result markup at all -- i.e. this isn't even a layout change
#      we can regex around, it looks like outright rate-limiting/blocking.
# This is exactly the fragility ddgs/SearxNG exist to avoid, which is why
# this is now the fallback of last resort rather than the primary backend.
_SNIPPET_PATTERNS = [
    re.compile(r'<a[^>]*\bclass="[^"]*\bresult__snippet\b[^"]*"[^>]*>(.*?)</a>', re.DOTALL),
    re.compile(r'<[^>]*\bclass="[^"]*\bresult__snippet\b[^"]*"[^>]*>(.*?)</[a-zA-Z]+>', re.DOTALL),
    re.compile(r'<td[^>]*\bclass="[^"]*\bresult-snippet\b[^"]*"[^>]*>(.*?)</td>', re.DOTALL),
    re.compile(r'<a[^>]*\bclass="[^"]*\bresult-link\b[^"]*"[^>]*>(.*?)</a>', re.DOTALL),
    re.compile(r'<a[^>]*\bclass="[^"]*\bresult__a\b[^"]*"[^>]*>(.*?)</a>', re.DOTALL),
]


def _extract_snippets(html_content: str) -> list:
    for pattern in _SNIPPET_PATTERNS:
        matches = pattern.findall(html_content)
        if matches:
            return matches
    return []


def _debug_dump(html_content: str, query: str) -> None:
    length = len(html_content)
    idx = html_content.lower().find("result")
    window = html_content[max(0, idx - 200): idx + 1800] if idx != -1 else html_content[:2000]
    looks_blocked = any(
        marker in html_content.lower()
        for marker in ("captcha", "unusual traffic", "are you a robot", "blocked")
    )
    log.debug(
        "DuckDuckGo raw HTML for %r: %d bytes total, first 'result' at offset %s, "
        "looks_blocked=%s\n%s",
        query, length, idx, looks_blocked, window,
    )


def search_duckduckgo(query: str, num_results: int = 5) -> list:
    """
    Last-resort fallback: scrape DuckDuckGo's HTML endpoint directly with no
    external dependencies. See module docstring above -- prefer search_ddgs().
    """
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36"
        }
    )

    log.info("-> DuckDuckGo search: %r", query)
    start = time.monotonic()

    try:
        with urllib.request.urlopen(req, timeout=12, context=get_ssl_context()) as response:
            elapsed = time.monotonic() - start
            html_content = response.read().decode("utf-8")
            snippets = _extract_snippets(html_content)

            results = []
            for snippet in snippets[:num_results]:
                clean_text = re.sub(r'<[^>]*>', '', snippet)
                clean_text = html.unescape(clean_text).strip()
                if clean_text:
                    results.append(clean_text)

            if results:
                log.info("<- DuckDuckGo OK in %.2fs: %d result(s) for %r", elapsed, len(results), query)
            else:
                log.warning(
                    "<- DuckDuckGo returned 200 in %.2fs but 0 parsed results for %r "
                    "(page layout may have changed, or DuckDuckGo served a CAPTCHA/block page). "
                    "Set LOG_LEVEL=DEBUG to see the raw HTML DuckDuckGo actually returned.",
                    elapsed, query,
                )
                _debug_dump(html_content, query)
            return results
    except urllib.error.URLError as e:
        elapsed = time.monotonic() - start
        reason = e.reason
        if isinstance(reason, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(reason):
            log.warning(
                "<- DuckDuckGo search failed after %.2fs for %r: SSL certificate verification "
                "failed (%s). This module now forces certifi's CA bundle; if this persists, "
                "run 'pip install --upgrade certifi'.",
                elapsed, query, reason,
            )
        else:
            log.warning("<- DuckDuckGo search failed after %.2fs for %r: %s: %s", elapsed, query, type(e).__name__, e)
        return []
    except Exception as e:
        elapsed = time.monotonic() - start
        log.warning("<- DuckDuckGo search failed after %.2fs for %r: %s: %s", elapsed, query, type(e).__name__, e)
        return []


# --- SearxNG JSON API (optional, opt-in via SEARX_HOST) --------------------
#
# Only used if you've stood up your own SearxNG container and set SEARX_HOST.
# Not the default anymore -- ddgs above covers the same "no self-hosted
# infra" goal with zero setup, so SearxNG is now purely an opt-in extra for
# anyone who already has it running or wants an aggregator they fully
# control. See web_search() for where this sits in the fallback order.
SEARX_ENGINES = ["google", "bing", "duckduckgo"]


def search_searxng(query: str, num_results: int = 5) -> list:
    searx_host = os.environ.get("SEARX_HOST", "").rstrip("/")
    if not searx_host:
        return []

    params = {
        "q": query,
        "format": "json",
        "engines": ",".join(SEARX_ENGINES),
    }
    url = f"{searx_host}/search?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        },
    )

    log.info("-> SearxNG search: %r (host=%s)", query, searx_host)
    start = time.monotonic()

    try:
        with urllib.request.urlopen(req, timeout=12, context=get_ssl_context()) as response:
            elapsed = time.monotonic() - start
            body = response.read().decode("utf-8")
            data = json.loads(body)
            raw_results = data.get("results", [])

            results = []
            for item in raw_results[:num_results]:
                text = (item.get("content") or item.get("title") or "").strip()
                if text:
                    results.append(text)

            if results:
                log.info("<- SearxNG OK in %.2fs: %d result(s) for %r", elapsed, len(results), query)
            else:
                log.warning(
                    "<- SearxNG returned 200 in %.2fs but 0 usable results for %r "
                    "(host=%s, raw result count=%d). Falling back to next backend.",
                    elapsed, query, searx_host, len(raw_results),
                )
            return results
    except urllib.error.HTTPError as e:
        elapsed = time.monotonic() - start
        err_msg = e.read().decode("utf-8", errors="replace")
        if e.code == 403:
            log.warning(
                "<- SearxNG search failed after %.2fs for %r: HTTP 403 (host=%s). "
                "Check that JSON output is enabled and the botdetection limiter allows "
                "this host. Falling back to next backend. Body: %s",
                elapsed, query, searx_host, err_msg[:300],
            )
        else:
            log.warning(
                "<- SearxNG search failed after %.2fs for %r: HTTP %s (host=%s): %s. Falling back to next backend.",
                elapsed, query, e.code, searx_host, err_msg[:300],
            )
        return []
    except urllib.error.URLError as e:
        elapsed = time.monotonic() - start
        log.warning(
            "<- SearxNG search failed after %.2fs for %r: %s: %s (host=%s). Falling back to next backend.",
            elapsed, query, type(e).__name__, e, searx_host,
        )
        return []
    except json.JSONDecodeError as e:
        elapsed = time.monotonic() - start
        log.warning(
            "<- SearxNG returned non-JSON content after %.2fs for %r (host=%s): %s. Falling back to next backend.",
            elapsed, query, searx_host, e,
        )
        return []
    except Exception as e:
        elapsed = time.monotonic() - start
        log.warning("<- SearxNG search failed after %.2fs for %r: %s: %s. Falling back to next backend.", elapsed, query, type(e).__name__, e)
        return []


def search_searxng_structured(query: str, num_results: int = 5) -> list:
    """Like search_searxng(), but keeps each result's source URL attached."""
    searx_host = os.environ.get("SEARX_HOST", "").rstrip("/")
    if not searx_host:
        return []

    params = {
        "q": query,
        "format": "json",
        "engines": ",".join(SEARX_ENGINES),
    }
    url = f"{searx_host}/search?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=12, context=get_ssl_context()) as response:
            body = response.read().decode("utf-8")
            data = json.loads(body)
            raw_results = data.get("results", [])

            results = []
            for item in raw_results[:num_results]:
                text = (item.get("content") or item.get("title") or "").strip()
                if text:
                    results.append({
                        "text": text,
                        "url": (item.get("url") or "").strip(),
                        "title": (item.get("title") or "").strip(),
                    })
            return results
    except Exception as e:
        log.warning("<- SearxNG structured search failed for %r: %s: %s", query, type(e).__name__, e)
        return []


def web_search(query: str, num_results: int = 5) -> list:
    """
    Primary entry point for all live web-search grounding in this project.

    Fallback order:
      1. ddgs library (open-source, no config, no self-hosted infra -- default)
      2. SearxNG (only if you've opted in via SEARX_HOST)
      3. Raw DuckDuckGo HTML scrape (zero-dependency last resort)

    NOTE: these results have no publish date or source URL attached. For
    time-sensitive lookups use search_ddgs_news(); to get citable source
    URLs alongside the text use web_search_with_sources() below.
    """
    results = search_ddgs(query, num_results=num_results)
    if results:
        return results

    results = search_searxng(query, num_results=num_results)
    if results:
        return results

    return search_duckduckgo(query, num_results=num_results)


def web_search_with_sources(query: str, num_results: int = 5) -> list:
    """
    Like web_search(), but returns [{"text", "url", "title"}, ...] instead
    of plain strings, so callers can show the user *where* information came
    from. Same fallback order as web_search(); the last-resort DuckDuckGo
    HTML scrape doesn't reliably expose per-result URLs, so those entries
    come back with an empty "url" (still useful as text, just not citable).
    """
    results = search_ddgs_structured(query, num_results=num_results)
    if results:
        return results

    results = search_searxng_structured(query, num_results=num_results)
    if results:
        return results

    plain = search_duckduckgo(query, num_results=num_results)
    return [{"text": t, "url": "", "title": ""} for t in plain]


def web_search_images(query: str, num_results: int = 6) -> list:
    """
    Primary entry point for destination image lookups. Currently only
    backed by ddgs (no self-hosted SearxNG image fallback wired up) --
    returns [] gracefully if ddgs is unavailable or the search fails, so
    callers should always treat images as optional/best-effort, never
    required for a trip to render.
    """
    return search_ddgs_images(query, num_results=num_results)

import json
import time
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional

from shared.s3_utils import load_country_currencies
from shared.ssl_utils import get_ssl_context
from shared.logging_utils import get_logger

log = get_logger("currency_utils")

# Frankfurter (https://frankfurter.dev) is a free, open-source, keyless
# exchange-rate API backed by the European Central Bank's daily reference
# rates. No API key, no self-hosted infra -- same "open source, zero config"
# bar as ddgs elsewhere in this app. api.frankfurter.app redirects to the
# current api.frankfurter.dev/v1 host; using the .dev host directly avoids
# the extra redirect hop.
FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest"

_currency_map_cache: Optional[dict] = None


def get_currency_for_country(country_code: str) -> Optional[str]:
    """Resolve an ISO 3166-1 alpha-2 country code (e.g. "CA", "JP") to its
    ISO 4217 currency code (e.g. "CAD", "JPY") using the bundled static
    reference table. Returns None if the country code is unknown/blank.
    """
    global _currency_map_cache
    if not country_code:
        return None

    if _currency_map_cache is None:
        try:
            _currency_map_cache = load_country_currencies().get("currencies", {})
        except Exception as e:
            log.warning("Failed to load country->currency reference data: %s: %s", type(e).__name__, e)
            _currency_map_cache = {}

    return _currency_map_cache.get(country_code.upper())


def get_exchange_rate(from_currency: str, to_currency: str) -> Optional[dict]:
    """Fetch the latest exchange rate between two ISO 4217 currency codes via
    the free Frankfurter API. Returns
    {"from_currency", "to_currency", "rate", "date"} or None on any failure
    (unsupported currency, network error, etc.) -- callers should treat
    exchange rate info as optional/best-effort, same as images/sources.
    """
    if not from_currency or not to_currency:
        return None
    if from_currency == to_currency:
        return {"from_currency": from_currency, "to_currency": to_currency, "rate": 1.0, "date": None, "same_currency": True}

    params = {"base": from_currency, "symbols": to_currency}
    url = FRANKFURTER_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        },
    )

    log.info("-> Frankfurter exchange rate lookup: %s -> %s", from_currency, to_currency)
    start = time.monotonic()

    try:
        with urllib.request.urlopen(req, timeout=10, context=get_ssl_context()) as response:
            elapsed = time.monotonic() - start
            data = json.loads(response.read().decode("utf-8"))
            rate = data.get("rates", {}).get(to_currency)
            if rate is None:
                log.warning("<- Frankfurter response missing rate for %s->%s in %.2fs: %s", from_currency, to_currency, elapsed, data)
                return None
            log.info("<- Frankfurter OK in %.2fs: 1 %s = %s %s (as of %s)", elapsed, from_currency, rate, to_currency, data.get("date"))
            return {
                "from_currency": from_currency,
                "to_currency": to_currency,
                "rate": rate,
                "date": data.get("date"),
                "same_currency": False,
            }
    except urllib.error.HTTPError as e:
        elapsed = time.monotonic() - start
        log.warning(
            "<- Frankfurter lookup failed after %.2fs for %s->%s: HTTP %s (likely an unsupported/unknown currency code)",
            elapsed, from_currency, to_currency, e.code,
        )
        return None
    except Exception as e:
        elapsed = time.monotonic() - start
        log.warning("<- Frankfurter lookup failed after %.2fs for %s->%s: %s: %s", elapsed, from_currency, to_currency, type(e).__name__, e)
        return None


def get_exchange_rate_for_countries(from_country_code: str, to_country_code: str) -> Optional[dict]:
    """Convenience wrapper: resolve two country codes to currencies, then
    fetch the exchange rate between them. Returns None if either country
    code is unknown or the rate lookup fails.
    """
    from_currency = get_currency_for_country(from_country_code)
    to_currency = get_currency_for_country(to_country_code)
    if not from_currency or not to_currency:
        log.info(
            "Could not resolve currency for country codes %r -> %r (from_currency=%s, to_currency=%s)",
            from_country_code, to_country_code, from_currency, to_currency,
        )
        return None
    return get_exchange_rate(from_currency, to_currency)

import os
import json
import ssl
import time
import boto3
import urllib.request
import urllib.parse
import urllib.error

from shared.logging_utils import get_logger
from shared.ssl_utils import get_ssl_context

log = get_logger("groq_client")

_ssm = None
MODEL = "llama-3.3-70b-versatile"


def _get_ssm_client():
    """Lazily create the boto3 SSM client.

    Kept lazy so importing this module (which every agent handler does) never
    requires AWS credentials/region locally -- the local dev path resolves the
    Groq key straight from GROQ_API_KEY/SSM_GROQ_KEY_PARAM env vars and never
    touches SSM at all.
    """
    global _ssm
    if _ssm is None:
        _ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return _ssm


def get_groq_key():
    """Retrieve Groq API key from environment variable or SSM Parameter Store."""
    key = os.environ.get("GROQ_API_KEY")
    if key:
        return key

    param_val = os.environ.get("SSM_GROQ_KEY_PARAM", "")
    if param_val.startswith("gsk_"):
        return param_val

    return _get_ssm_client().get_parameter(
        Name=param_val or "/tripnegotiator/groq-key",
        WithDecryption=True,
    )["Parameter"]["Value"]


def _mask_key(key: str) -> str:
    if not key or len(key) < 10:
        return "***"
    return f"{key[:7]}...{key[-4:]}"


def call_groq(prompt: str, system: str) -> dict:
    """
    Call Groq API with JSON mode enabled.
    Uses standard urllib to avoid packaging requests in Lambda.

    Args:
        prompt: User message
        system: System prompt

    Returns:
        Parsed JSON response from model
    """
    url = "https://api.groq.com/openai/v1/chat/completions"
    key = get_groq_key()
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        # Groq's API sits behind a WAF that blocks requests carrying Python's
        # default urllib User-Agent ("Python-urllib/3.x") as a bot signature,
        # returning a 403 even with a valid key. A normal browser/curl-style
        # User-Agent passes fine (same fix web_search.py already applies to
        # DuckDuckGo for the identical reason).
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.7,
    }

    log.info(
        "-> Groq request: model=%s key=%s system_chars=%d prompt_chars=%d",
        MODEL, _mask_key(key), len(system), len(prompt),
    )
    log.debug("Groq prompt payload: %s", prompt[:1000])

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=30, context=get_ssl_context()) as response:
            elapsed = time.monotonic() - start
            resp_body = response.read().decode("utf-8")
            raw = json.loads(resp_body)
            content = raw["choices"][0]["message"]["content"]
            usage = raw.get("usage", {})
            log.info(
                "<- Groq OK in %.2fs (status=%s, tokens prompt=%s completion=%s)",
                elapsed, getattr(response, "status", "200"),
                usage.get("prompt_tokens"), usage.get("completion_tokens"),
            )
            log.debug("Groq raw content: %s", content[:1000])
            return json.loads(content)
    except urllib.error.HTTPError as e:
        elapsed = time.monotonic() - start
        err_msg = e.read().decode("utf-8", errors="replace")
        log.error(
            "<- Groq HTTP %s after %.2fs: %s",
            e.code, elapsed, err_msg[:500],
        )
        if e.code == 403:
            log.error(
                "   Hint: a 403 with a valid key almost always means a WAF/proxy is "
                "blocking the request before it reaches Groq's app servers (bad "
                "User-Agent, corporate proxy/antivirus TLS inspection, etc.) -- "
                "not that the API key itself is invalid."
            )
        raise e
    except urllib.error.URLError as e:
        elapsed = time.monotonic() - start
        reason = e.reason
        if isinstance(reason, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(reason):
            log.error(
                "<- Groq call failed after %.2fs: SSL certificate verification failed: %s",
                elapsed, reason,
            )
            log.error(
                "   Hint: this is the classic conda-on-Windows issue -- Python's default "
                "trust store lookup is broken even though curl.exe (using Windows' native "
                "cert store) works fine with the same URL. Run "
                "'pip install --upgrade certifi' in this environment and restart the "
                "backend; this module now forces certifi's CA bundle for all requests, "
                "which should resolve it."
            )
        else:
            log.error("<- Groq call failed after %.2fs: %s: %s", elapsed, type(e).__name__, e)
        raise e
    except json.JSONDecodeError as e:
        elapsed = time.monotonic() - start
        log.error("<- Groq returned non-JSON content after %.2fs: %s", elapsed, e)
        raise
    except Exception as e:
        elapsed = time.monotonic() - start
        log.error("<- Groq call failed after %.2fs: %s: %s", elapsed, type(e).__name__, e)
        raise e

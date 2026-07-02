"""
Shared SSL context helper.

Why this exists: on some Python installs -- most notably conda environments
on Windows -- the interpreter's default trust store resolution is broken or
incomplete, so every outbound HTTPS request made via urllib/requests fails
with `ssl.SSLCertVerificationError: certificate verify failed: unable to get
local issuer certificate`, even though the exact same request via curl.exe
(which uses Windows' native certificate store) succeeds fine. This makes it
look like the API key or the remote service is at fault when it's actually a
local trust-store problem.

The fix: explicitly build the SSL context from the `certifi` package's
bundled CA certificates rather than trusting Python's default context
resolution. certifi ships a known-good, up-to-date CA bundle as pure data,
so this sidesteps whatever is broken in the conda/Windows cert store lookup.
"""
import ssl

try:
    import certifi
    _CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    # certifi isn't installed for some reason -- fall back to the default
    # context. Requests will still work on machines where the OS trust store
    # resolution isn't broken; just won't get the certifi-based fix.
    _CONTEXT = ssl.create_default_context()


def get_ssl_context() -> ssl.SSLContext:
    return _CONTEXT

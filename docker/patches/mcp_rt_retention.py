#!/usr/bin/env python3
"""Build-time patch: RFC 6749 s6 refresh-token retention in the mcp SDK.

A token refresh response MAY omit ``refresh_token``; the client MUST then retain
the existing one. The pinned mcp SDK (``mcp==1.26.0``) ``_handle_refresh_response``
replaces ``context.current_tokens`` with the response verbatim, dropping the
in-memory refresh token. Guru's MCP token endpoint omits it on refresh, so the
connection dies after ~2h (1h token + one refresh) and the daemon registers zero
guru tools. Linear is unaffected only because it rotates RTs every refresh.

The Hermes-side on-disk fix lives in ``tools/mcp_oauth.py`` (a real source edit);
this script bakes the SDK in-memory half into the image at build time, since the
SDK is a third-party dependency, not Hermes source. ``mcp`` is pinned, so the
anchor is stable. **Fail-loud**: if the anchor is gone (mcp bumped) the build
goes red rather than silently shipping without the fix.

Invoked from the Dockerfile after ``uv sync``. Idempotent (marker check).
"""

import glob
import sys

MARKER = "RFC 6749 s6 refresh-token retention"
SDK_GLOB = "/opt/hermes/.venv/lib/python3*/site-packages/mcp/client/auth/oauth2.py"
ANCHOR = "            token_response = OAuthToken.model_validate_json(content)\n"
INSERT = """
            # RFC 6749 s6 refresh-token retention (build patch): keep the prior
            # refresh token when the refresh response omits one.
            if token_response.refresh_token is None and self.context.current_tokens:
                token_response.refresh_token = self.context.current_tokens.refresh_token
"""


def main() -> None:
    paths = glob.glob(SDK_GLOB)
    if not paths:
        sys.exit(f"[mcp-rt-patch] FATAL: no SDK match for {SDK_GLOB}")
    for path in paths:
        with open(path) as f:
            src = f.read()
        if MARKER in src:
            print(f"[mcp-rt-patch] already applied: {path}")
            continue
        if ANCHOR not in src:
            sys.exit(f"[mcp-rt-patch] FATAL: anchor not found in {path} (mcp bumped? re-derive)")
        with open(path, "w") as f:
            f.write(src.replace(ANCHOR, ANCHOR + INSERT, 1))
        print(f"[mcp-rt-patch] applied: {path}")


if __name__ == "__main__":
    main()

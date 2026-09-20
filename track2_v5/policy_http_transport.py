"""Private one-request local HTTP process; parent enforces a total deadline."""

import json
import sys
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("policy redirects are not supported")


if __name__ == "__main__":
    try:
        request = json.load(sys.stdin)
        if urlparse(request["endpoint"]).hostname not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            raise ValueError("local endpoint required")
        with build_opener(NoRedirect).open(
            Request(
                request["endpoint"],
                data=request["body"].encode(),
                headers={"Content-Type": "application/json"},
            ),
            timeout=request["timeout"],
        ) as response:
            raw = response.read(request["max_bytes"] + 1)
        if len(raw) > request["max_bytes"]:
            raise ValueError("response exceeds policy budget")
        sys.stdout.buffer.write(raw)
    except Exception as exc:  # noqa: BLE001 -- process boundary returns a structured failure
        sys.stderr.write(type(exc).__name__)
        sys.exit(2)

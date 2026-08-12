from __future__ import annotations

import json
import sys
from urllib.error import URLError
from urllib.request import urlopen


def main() -> int:
    try:
        with urlopen("http://localhost:8000/health", timeout=5) as response:
            payload = json.load(response)
            return 0 if response.status == 200 and payload.get("status") == "ok" else 1
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Configure the public raw GitHub cache URL after the repository is created."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "data" / "cache_config.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", help="GitHub repository as owner/name")
    parser.add_argument("--branch", default="main")
    args = parser.parse_args()
    if args.repository.count("/") != 1:
        parser.error("repository must be in owner/name form")
    owner, name = (part.strip() for part in args.repository.split("/", 1))
    if not owner or not name:
        parser.error("repository must be in owner/name form")
    base = f"https://raw.githubusercontent.com/{owner}/{name}/{args.branch}/public/cache"
    CONFIG.write_text(json.dumps({"cache_base_url": base}, indent=2) + "\n", encoding="utf-8")
    print(f"Configured shared cache: {base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Emit the request headers required by the self-hosted Supabase MCP server."""

import json
from pathlib import Path


def read_env_value(path: Path, name: str) -> str:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name:
            return value.strip().strip('"').strip("'")
    raise RuntimeError(f"{name} is not set in {path}")


project_root = Path(__file__).resolve().parent.parent
api_key = read_env_value(project_root / ".env", "SUPABASE_SECRET_KEY")
print(json.dumps({"apikey": api_key}))

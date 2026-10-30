#!/usr/bin/env python
"""Runner script for RepoViva Graph MCP Server."""
import sys
from pathlib import Path

# Ensure project root is in python search path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from repoviva.mcp_server import main

if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""Run the installed audit package without changing the caller's working directory."""
from tts_audit.cli import main
if __name__ == '__main__':
    raise SystemExit(main())

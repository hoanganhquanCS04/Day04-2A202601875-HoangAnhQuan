from __future__ import annotations

import sys


def enable_utf8_io() -> None:
    """Make stdin/stdout/stderr UTF-8 safe.

    On Windows the console defaults to a legacy code page (cp1252), which breaks
    this lab in two ways:

    * printing Vietnamese text or emoji raises UnicodeEncodeError mid-run;
    * reading piped Vietnamese input through input() yields lone surrogates
      (``\\udc9d``), which later blow up json.dumps -> write_text as UTF-8.

    Reconfiguring all three streams with errors="replace" keeps the CLI usable
    instead of crashing, and stops surrogates from entering a transcript.
    """
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):  # detached / non-reconfigurable stream
            pass


def safe_text(value: str) -> str:
    """Drop unpaired surrogates so a string is always UTF-8 encodable."""
    return value.encode("utf-8", errors="replace").decode("utf-8")

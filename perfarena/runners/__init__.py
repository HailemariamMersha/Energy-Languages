"""PerfArena measurement runners.

Two runners exist:

- ``RAPL/perfarena_runner`` (C binary) for Linux x86 with MSR access.
- ``perfarena.runners.codecarbon_runner`` (Python) for macOS and any
  platform where CodeCarbon is installed but RAPL is not available.

Both produce the same JSONL schema so the downstream ingest
(``measurement.py``) works identically regardless of backend.
"""

"""Run worker process: claims queued wiki jobs and runs them in the sandbox."""

from selfmemory.features.runs.worker import main

if __name__ == "__main__":  # pragma: no cover - process entry point
    main()

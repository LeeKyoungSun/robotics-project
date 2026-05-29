#!/usr/bin/env python3

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    from script.sanity_checks.run_yolo_inference import main
except ImportError:
    from sanity_checks.run_yolo_inference import main


if __name__ == "__main__":
    raise SystemExit(main())

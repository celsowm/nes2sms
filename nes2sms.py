#!/usr/bin/env python3
"""
nes2sms - NES to Sega Master System conversion pipeline

Main entry point for the conversion pipeline.
"""

import sys
import os
from pathlib import Path

# Add src to path for imports
script_dir = Path(__file__).parent
src_dir = script_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from nes2sms.cli.main import main

if __name__ == "__main__":
    main()

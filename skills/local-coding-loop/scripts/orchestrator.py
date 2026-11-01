#!/usr/bin/env python3
"""Resolve the installed skill symlink back to its maintained checkout."""
from pathlib import Path
import runpy
import sys

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
runpy.run_path(str(root / 'orchestrator.py'), run_name='__main__')

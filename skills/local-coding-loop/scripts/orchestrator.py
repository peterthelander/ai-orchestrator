#!/usr/bin/env python3
"""Launch the maintained checkout from a linked or Windows-readable copied skill."""
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

skill = Path(__file__).resolve().parents[1]
marker = skill / 'installation.json'
if marker.is_file():
    installation = json.loads(marker.read_text())
    if os.name == 'nt':
        argv = ['wsl.exe']
        if installation.get('distribution'):
            argv += ['--distribution', installation['distribution']]
        sys.exit(subprocess.call(argv + ['--exec', 'python3',
            installation['checkout'] + '/orchestrator.py', *sys.argv[1:]]))
    root = Path(installation['checkout'])
else:
    root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
runpy.run_path(str(root / 'orchestrator.py'), run_name='__main__')

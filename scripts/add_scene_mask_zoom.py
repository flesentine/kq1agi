#!/usr/bin/env python3
from pathlib import Path
import runpy
import sys

# Kept as the workflow entry point for compatibility. The consolidated installer
# now owns zoom plus parser-safe F2/button controls so the generated editor stays
# internally consistent.
script = Path(__file__).with_name('install_scene_mask_controls.py')
if not script.exists():
    raise SystemExit(f'missing scene-mask controls installer: {script}')

runpy.run_path(str(script), run_name='__main__')

#!/usr/bin/env python3
from pathlib import Path
import runpy
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_debug_canvas_restore.py /path/to/index.html')

here = Path(__file__).resolve().parent
runpy.run_path(str(here / 'fix_debug_canvas_restore_base.py'), run_name='__main__')
runpy.run_path(str(here / 'patch_web_debug_view_presets.py'), run_name='__main__')
runpy.run_path(str(here / 'patch_web_debug_view_bridge.py'), run_name='__main__')
runpy.run_path(str(here / 'patch_web_fall_accessibility.py'), run_name='__main__')
runpy.run_path(str(here / 'patch_web_fall_scan_refresh.py'), run_name='__main__')
runpy.run_path(str(here / 'simplify_fall_legend.py'), run_name='__main__')

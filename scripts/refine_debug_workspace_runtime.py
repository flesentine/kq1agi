#!/usr/bin/env python3
from pathlib import Path
import runpy
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: refine_debug_workspace_runtime.py /path/to/agile-gdx')

here = Path(__file__).resolve().parent
runpy.run_path(str(here / 'refine_debug_workspace_runtime_base.py'), run_name='__main__')
runpy.run_path(str(here / 'fix_debug_view_presets_runtime.py'), run_name='__main__')
runpy.run_path(str(here / 'fix_debug_view_bridge_runtime.py'), run_name='__main__')
runpy.run_path(str(here / 'fix_debug_eraser_bridge_runtime.py'), run_name='__main__')
runpy.run_path(str(here / 'fix_debug_test_bridge_runtime.py'), run_name='__main__')
runpy.run_path(str(here / 'improve_fall_accessibility_runtime.py'), run_name='__main__')
runpy.run_path(str(here / 'fix_scene_seed_tick.py'), run_name='__main__')
runpy.run_path(str(here / 'fix_shared_array_signed_reads.py'), run_name='__main__')
runpy.run_path(str(here / 'add_scene_mask_reset_default.py'), run_name='__main__')
runpy.run_path(str(here / 'fix_room_entry_control_grace.py'), run_name='__main__')
runpy.run_path(str(here / 'fix_room_entry_hazard_flags.py'), run_name='__main__')
runpy.run_path(str(here / 'run_danger_composite_runtime.py'), run_name='__main__')

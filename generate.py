#!/usr/bin/env python3
"""Raccourci racine : `python generate.py` lance generator/generate.py (mêmes options : --data, --root)."""
import os
import runpy
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "generator"))
sys.exit(runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "generator", "generate.py"), run_name="__main__") and 0)

#!/usr/bin/env python3
"""
Run the game. Just type: python3 run.py
"""
import sys
import os
import warnings
warnings.filterwarnings("ignore")  # suppress Python 3.9 deprecation warnings

# Make sure the project root is on the path so imports work
sys.path.insert(0, os.path.dirname(__file__))

from app.main import main

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Run the game.
  Terminal mode: python3 run.py
  Web mode:      python3 run.py --web
"""
import sys
import os
import warnings
warnings.filterwarnings("ignore")  # suppress Python 3.9 deprecation warnings

# Make sure the project root is on the path so imports work
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    if "--web" in sys.argv:
        # Web mode — Flask server with HTML frontend
        port = 5000
        # Check for custom port: --port 8080
        if "--port" in sys.argv:
            idx = sys.argv.index("--port")
            if idx + 1 < len(sys.argv):
                port = int(sys.argv[idx + 1])
        from app.server import start_server
        start_server(port=port)
    else:
        # Terminal mode — original rich-based UI
        from app.main import main
        main()

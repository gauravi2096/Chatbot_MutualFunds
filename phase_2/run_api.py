"""
Phase 2 — Run the backend API server.

Usage:
  export GROQ_API_KEY=your_key
  python phase_2/run_api.py

Or run from project root; .env is loaded automatically if present.
"""

import os
import sys
from pathlib import Path

# Project root on path for phase_0 / phase_1 / phase_2 imports
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

# Load .env from project root if present (so GROQ_API_KEY etc. are set)
_env_file = _project_root / ".env"
if _env_file.is_file():
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip()
                if v and ((v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'"))):
                    v = v[1:-1]
                os.environ.setdefault(k, v)

from phase_2.api import app
from phase_2.config import API_HOST, API_PORT

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT)

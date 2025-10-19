import os
from dotenv import load_dotenv


load_dotenv()

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(PROJECT_ROOT), "data")

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", os.path.join(os.path.dirname(PROJECT_ROOT), ".chroma"))

# Unified debug flag controlled via env, default ON
# MULTI_SEARCH_DEBUG accepts: 1/true/yes/on (case-insensitive) to enable
# Any other value disables structured LCEL debug logs

def debug_enabled() -> bool:
    v = os.getenv("MULTI_SEARCH_DEBUG", "1")
    return str(v).lower() in ("1", "true", "yes", "on")
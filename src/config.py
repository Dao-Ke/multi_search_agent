import os
from dotenv import load_dotenv


load_dotenv()

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(PROJECT_ROOT), "data")

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", os.path.join(os.path.dirname(PROJECT_ROOT), ".chroma"))
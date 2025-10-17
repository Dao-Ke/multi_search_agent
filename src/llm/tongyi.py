import os
from typing import List

from src.llm.embeddings import EmbeddingProvider


class TongyiEmbedding(EmbeddingProvider):
    """Tongyi (DashScope) embedding provider for text-embedding-v4.

    Reads API key from env: `TONGYI_API_KEY` or `DASHSCOPE_API_KEY`.
    """

    def __init__(self, model: str = "text-embedding-v4", api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.getenv("TONGYI_API_KEY") or os.getenv("DASHSCOPE_API_KEY")

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not self.api_key:
            raise RuntimeError("DashScope API key not set in TONGYI_API_KEY or DASHSCOPE_API_KEY")

        # Ensure dashscope picks up the key from env
        os.environ["DASHSCOPE_API_KEY"] = self.api_key

        # Lazy import to avoid dependency in test-only environments
        from dashscope import Embedding

        # DashScope supports batch inputs; we call once for the list
        resp = Embedding.call(model=self.model, input=texts)

        # Try to parse response in a robust way across SDK versions
        # Prefer resp.output["embeddings"], fallback to resp.get("data")
        if hasattr(resp, "output") and resp.output and "embeddings" in resp.output:
            return [item["embedding"] for item in resp.output["embeddings"]]

        data = getattr(resp, "data", None)
        if isinstance(data, list):
            return [item["embedding"] for item in data]

        # As a last resort, attempt dict-style access
        if isinstance(resp, dict):
            if "output" in resp and "embeddings" in resp["output"]:
                return [item["embedding"] for item in resp["output"]["embeddings"]]
            if "data" in resp:
                return [item["embedding"] for item in resp["data"]]

        raise RuntimeError("Unexpected DashScope embedding response format")
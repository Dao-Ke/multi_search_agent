import hashlib
import math
import random
from typing import List


class EmbeddingProvider:
    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError


class HashEmbedding(EmbeddingProvider):
    """
    Deterministic lightweight embedding for tests and offline use.
    Generates fixed-size vectors from text hashes without external calls.
    """

    def __init__(self, dim: int = 384):
        self.dim = dim

    def _embed_one(self, text: str) -> List[float]:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        seed = int.from_bytes(h[:8], "big")
        rnd = random.Random(seed)
        vec = [rnd.uniform(-1.0, 1.0) for _ in range(self.dim)]
        # L2 normalize for stability
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def embed(self, texts: List[str]) -> List[List[float]]:
        return [self._embed_one(t) for t in texts]
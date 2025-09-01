import os
from typing import List
from google import genai
from google.genai import types

EMBED_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
EMBED_DIM = int(os.getenv("EMBEDDING_DIM", "1536"))

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def embed_one(text: str) -> List[float]:
    resp = client.models.embed_content(
        model=EMBED_MODEL,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=EMBED_DIM),
    )
    # O SDK retorna objeto com lista de embeddings; para 1 conteúdo, pegue o primeiro
    # O formato concreto é serializável; usamos .values se disponível, senão normalizamos:
    vec = (getattr(resp, "embeddings", None) or getattr(resp, "embedding", None))
    # resp.embeddings[0].values em versões recentes
    if isinstance(vec, list) and hasattr(vec[0], "values"):
        return vec[0].values
    if hasattr(vec, "values"):
        return vec.values
    # fallback: tentamos mapear para list[float]
    return list(vec)  # pode ser já uma lista de floats

def embed_batch(texts: List[str]) -> List[List[float]]:
    resp = client.models.embed_content(
        model=EMBED_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(output_dimensionality=EMBED_DIM),
    )
    embs = getattr(resp, "embeddings", None) or []
    return [e.values if hasattr(e, "values") else list(e) for e in embs]

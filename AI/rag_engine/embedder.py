"""
Embedder for HumanLoop RAG System

Uses sentence-transformers (all-MiniLM-L6-v2) to generate embeddings.
Outputs float32 numpy arrays for FAISS compatibility.
"""

import numpy as np
from typing import List
from sentence_transformers import SentenceTransformer


# Model loaded lazily to avoid import-time download
_model = None


def get_model() -> SentenceTransformer:
    """Load and cache the SentenceTransformer model."""
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_texts(texts: List[str]) -> np.ndarray:
    """
    Generate embeddings for a list of texts.

    Args:
        texts: List of text strings (e.g., chunk texts or a single query).

    Returns:
        Numpy array of shape (n_texts, embedding_dim) as float32.
    """
    if not texts:
        raise ValueError("texts cannot be empty")

    model = get_model()
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=len(texts) > 10)
    return embeddings.astype(np.float32)


def main() -> None:
    """Demo: Embed a sample text."""
    sample = ["This is a sample text for embedding."]
    emb = embed_texts(sample)
    print(f"Embedding shape: {emb.shape}")
    print(f"dtype: {emb.dtype}")


if __name__ == "__main__":
    main()

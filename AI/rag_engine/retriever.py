"""
Retriever for HumanLoop RAG System

Uses in-memory FAISS index (loaded once, cached). Embeds user query, retrieves top-k chunks.
Converts L2 distance to similarity score (lower distance = higher similarity).
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

import faiss
import numpy as np

from embedder import embed_texts


def get_index_path() -> Path:
    """Get path to the FAISS index file."""
    return Path(__file__).resolve().parent / "index.faiss"


def get_metadata_path() -> Path:
    """Get path to the metadata JSON file."""
    return Path(__file__).resolve().parent / "metadata.json"


# In-memory cache: load index and metadata once per process
_index: Optional[faiss.Index] = None
_metadata: Optional[List[Dict[str, Any]]] = None


def l2_to_similarity(distance: float) -> float:
    """
    Convert L2 distance to similarity score (0-1 range).
    Lower L2 distance = higher similarity.
    Uses 1 / (1 + distance) for bounded, monotonic mapping.
    """
    return 1.0 / (1.0 + float(distance))


def _load_index() -> faiss.Index:
    """Load FAISS index from disk (cached after first call)."""
    global _index
    if _index is None:
        index_path = get_index_path()
        if not index_path.exists():
            raise FileNotFoundError(f"FAISS index not found at {index_path}. Run build_index.py first.")
        _index = faiss.read_index(str(index_path))
    return _index


def _load_metadata() -> List[Dict[str, Any]]:
    """Load metadata JSON from disk (cached after first call)."""
    global _metadata
    if _metadata is None:
        meta_path = get_metadata_path()
        if not meta_path.exists():
            raise FileNotFoundError(f"Metadata not found at {meta_path}. Run build_index.py first.")
        with open(meta_path, "r", encoding="utf-8") as f:
            _metadata = json.load(f)
    return _metadata


def reload_vector_store() -> None:
    """Clear cache so next retrieve() reloads index and metadata from disk. Call after rebuilding index."""
    global _index, _metadata
    _index = None
    _metadata = None


def retrieve(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Retrieve top-k most relevant chunks for a user query.
    FAISS index and metadata are loaded once and reused (in-memory vector store).

    Args:
        query: User query string.
        top_k: Number of chunks to retrieve (default 5).

    Returns:
        List of chunk dicts with text, source, category, score (sorted by relevance).
    """
    index = _load_index()
    metadata = _load_metadata()

    # Embed query
    query_embedding = embed_texts([query])
    query_embedding = np.array(query_embedding, dtype=np.float32)

    # Search FAISS (returns L2 distances)
    k = min(top_k, index.ntotal)
    distances, indices = index.search(query_embedding, k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx < 0:
            continue
        meta = metadata[idx]
        score = l2_to_similarity(dist)
        results.append({
            "chunk_id": meta["chunk_id"],
            "text": meta["text"],
            "source": meta["source"],
            "category": meta["category"],
            "score": score,
        })

    return results


def main() -> None:
    """Demo: Retrieve chunks for a sample query."""
    query = "How can NGOs support renewable energy in rural areas?"
    results = retrieve(query, top_k=5)
    print(f"Query: {query}")
    print(f"Retrieved {len(results)} chunks:")
    for r in results:
        print(f"  - {r['source']} ({r['category']}) score={r['score']:.4f}")


if __name__ == "__main__":
    main()

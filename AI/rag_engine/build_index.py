"""
Build Vector Index for HumanLoop RAG System

Loads documents, chunks them, generates embeddings, and creates FAISS IndexFlatL2.
Saves index.faiss and metadata mapping (JSON) for retrieval.
"""

import json
from pathlib import Path

import faiss
import numpy as np

from kb_loader import load_documents
from chunker import chunk_documents
from embedder import embed_texts


def get_index_path() -> Path:
    """Get path to the FAISS index file."""
    return Path(__file__).resolve().parent / "index.faiss"


def get_metadata_path() -> Path:
    """Get path to the metadata JSON file."""
    return Path(__file__).resolve().parent / "metadata.json"


def build_index(knowledge_base_path: Path = None) -> tuple:
    """
    Build FAISS index from knowledge base documents.

    Args:
        knowledge_base_path: Path to knowledge_base. If None, uses default.

    Returns:
        Tuple of (faiss_index, metadata_list).
    """
    print("Loading documents...")
    documents = load_documents(knowledge_base_path)
    if not documents:
        raise ValueError("No documents found in knowledge base")

    print("Chunking documents...")
    chunks = chunk_documents(documents)
    print(f"Created {len(chunks)} chunks")

    print("Generating embeddings...")
    texts = [c["text"] for c in chunks]
    embeddings = embed_texts(texts)

    print("Building FAISS index...")
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)

    # Metadata: list aligned with index positions
    metadata = [{"chunk_id": c["chunk_id"], "text": c["text"], "source": c["source"], "category": c["category"]} for c in chunks]

    return index, metadata


def save_index(index: faiss.Index, metadata: list) -> None:
    """Save FAISS index and metadata to disk."""
    root = Path(__file__).resolve().parent
    index_path = root / "index.faiss"
    meta_path = root / "metadata.json"

    faiss.write_index(index, str(index_path))
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"Saved index to {index_path}")
    print(f"Saved metadata to {meta_path}")


def main() -> None:
    """Build and save the vector index."""
    index, metadata = build_index()
    save_index(index, metadata)
    print("Index build complete.")


if __name__ == "__main__":
    main()

"""
Chunker for HumanLoop RAG System

Splits text into chunks of 300-400 words with 50-word overlap.
Preserves metadata (source, category) for each chunk.
"""

import re
from typing import List, Dict, Any


def word_tokenize(text: str) -> List[str]:
    """Split text into words (simple whitespace-based tokenization)."""
    return re.findall(r"\b\w+\b", text)


def chunk_text(
    text: str,
    chunk_size: int = 350,
    overlap: int = 50,
    source: str = "",
    category: str = "",
) -> List[Dict[str, Any]]:
    """
    Split text into overlapping chunks of roughly chunk_size words.

    Args:
        text: Raw document text.
        chunk_size: Target words per chunk (default 350, range 300-400).
        overlap: Number of overlapping words between consecutive chunks.
        source: Filename or source identifier.
        category: Folder category (e.g., ngos, pilots, sdg, guidelines).

    Returns:
        List of chunk dicts with chunk_id, text, source, category.
    """
    words = word_tokenize(text)
    chunks = []
    start = 0
    chunk_id = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]
        chunk_text_str = " ".join(chunk_words)

        if chunk_text_str.strip():
            chunk_id += 1
            chunks.append({
                "chunk_id": chunk_id,
                "text": chunk_text_str,
                "source": source,
                "category": category,
            })

        start = end - overlap if end < len(words) else len(words)

    return chunks


def chunk_documents(documents: List[Dict[str, Any]], chunk_size: int = 350, overlap: int = 50) -> List[Dict[str, Any]]:
    """
    Chunk a list of documents from kb_loader.

    Args:
        documents: List of dicts with keys text, filename, category.
        chunk_size: Target words per chunk.
        overlap: Overlap in words between chunks.

    Returns:
        List of all chunks with metadata.
    """
    all_chunks = []
    for doc in documents:
        chunks = chunk_text(
            text=doc["text"],
            chunk_size=chunk_size,
            overlap=overlap,
            source=doc["filename"],
            category=doc["category"],
        )
        all_chunks.extend(chunks)

    # Re-index chunk_ids globally
    for i, c in enumerate(all_chunks, start=1):
        c["chunk_id"] = i

    return all_chunks


def main() -> None:
    """Demo: Chunk a sample document."""
    sample = {
        "text": " ".join(["word"] * 500),
        "filename": "sample.txt",
        "category": "pilots",
    }
    chunks = chunk_documents([sample])
    print(f"Created {len(chunks)} chunks from 500 words (350 size, 50 overlap)")
    if chunks:
        print(f"Chunk 1: {len(word_tokenize(chunks[0]['text']))} words")


if __name__ == "__main__":
    main()

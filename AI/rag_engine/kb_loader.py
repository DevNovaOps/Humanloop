"""
Knowledge Base Loader for HumanLoop RAG System

Recursively loads all .txt files from the knowledge_base directory.
Returns structured list of documents with text, filename, and folder category.
"""

import os
from pathlib import Path
from typing import List, Dict, Any


def get_project_root() -> Path:
    """Get the root directory of the RAG engine project."""
    return Path(__file__).resolve().parent


def load_documents(knowledge_base_path: Path = None) -> List[Dict[str, Any]]:
    """
    Recursively load all .txt files from the knowledge base directory.

    Args:
        knowledge_base_path: Path to knowledge_base folder. If None, uses default.

    Returns:
        List of dicts with keys: text, filename, category (folder name)
    """
    if knowledge_base_path is None:
        knowledge_base_path = get_project_root() / "knowledge_base"

    if not knowledge_base_path.exists():
        raise FileNotFoundError(f"Knowledge base path not found: {knowledge_base_path}")

    documents = []

    for root, dirs, files in os.walk(knowledge_base_path):
        for filename in files:
            if not filename.lower().endswith(".txt"):
                continue

            filepath = Path(root) / filename

            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except IOError as e:
                print(f"Warning: Could not read {filepath}: {e}")
                continue

            # Category is the immediate parent folder name relative to knowledge_base
            rel_path = filepath.relative_to(knowledge_base_path)
            category = rel_path.parts[0] if len(rel_path.parts) > 1 else "root"

            documents.append({
                "text": text.strip(),
                "filename": filename,
                "category": category,
            })

    return documents


def main() -> None:
    """Demo: Load and print summary of documents."""
    docs = load_documents()
    print(f"Loaded {len(docs)} documents:")
    for doc in docs:
        print(f"  - {doc['category']}/{doc['filename']}: {len(doc['text'])} chars")


if __name__ == "__main__":
    main()

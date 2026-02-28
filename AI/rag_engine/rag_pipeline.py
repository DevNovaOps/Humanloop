"""
RAG Pipeline for HumanLoop

End-to-end pipeline: accept user query, retrieve chunks (cached vector store),
build prompt (trimmed context), call Ollama. Tuned for minimum latency.
"""

from typing import List, Dict, Any, Tuple, Optional

from retriever import retrieve
from llm.prompt_builder import build_prompt
from llm.ollama_client import generate


def run_rag(
    user_query: str,
    top_k: int = 3,
    model: str = "mistral",
    max_chars_per_chunk: Optional[int] = 600,
    timeout: Optional[int] = 300,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Run full RAG pipeline: retrieve, prompt, generate.

    Args:
        user_query: User's question or pilot description.
        top_k: Number of chunks to retrieve (default 3 for faster LLM).
        model: Ollama model name (default: mistral).
        max_chars_per_chunk: Truncate context to this many chars per chunk (default 600). None = no limit.
        timeout: Ollama request timeout in seconds. None = use client default.

    Returns:
        Tuple of (generated_answer, retrieved_chunks).
    """
    # Retrieve relevant chunks (uses cached FAISS index)
    chunks = retrieve(user_query, top_k=top_k)
    if not chunks:
        return "No relevant context found. Please ensure the index is built (run build_index.py) and your query relates to the knowledge base.", []

    # Build prompt with trimmed context for faster LLM
    prompt = build_prompt(user_query, chunks, max_chars_per_chunk=max_chars_per_chunk)

    # Generate response via Ollama
    kwargs = {"model": model}
    if timeout is not None:
        kwargs["timeout"] = timeout
    answer = generate(prompt, **kwargs)

    return answer, chunks


def main() -> None:
    """Demo: Run RAG on a sample query."""
    query = "What NGOs focus on environmental conservation in Africa?"
    print(f"Query: {query}\n")
    answer, chunks = run_rag(query)
    print("Retrieved Sources:")
    for c in chunks:
        print(f"  - {c['source']} ({c['category']})")
    print("\nAI Recommendation:")
    print(answer)


if __name__ == "__main__":
    main()

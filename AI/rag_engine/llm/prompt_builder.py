"""
Prompt Builder for HumanLoop RAG System

Builds structured prompts for social innovation advisory.
Injects user query and retrieved context into a consistent template.
Supports truncating chunk text to limit prompt size and speed up LLM.
"""

from typing import List, Dict, Any, Optional


def format_chunks_for_prompt(
    chunks: List[Dict[str, Any]],
    max_chars_per_chunk: Optional[int] = None,
) -> str:
    """Convert retrieved chunks into readable context text. Optionally truncate each chunk to max chars."""
    parts = []
    for i, c in enumerate(chunks, start=1):
        text = c["text"]
        if max_chars_per_chunk and len(text) > max_chars_per_chunk:
            text = text[:max_chars_per_chunk].rsplit(" ", 1)[0] + "…"
        parts.append(f"[{i}] Source: {c['source']} ({c['category']})\n{text}")
    return "\n\n---\n\n".join(parts)


def build_prompt(
    user_query: str,
    retrieved_chunks: List[Dict[str, Any]],
    max_chars_per_chunk: Optional[int] = 600,
) -> str:
    """
    Build structured prompt for social innovation advisory.
    Chunk text is truncated to max_chars_per_chunk to keep prompt small and LLM fast.

    Args:
        user_query: The user's question or pilot description.
        retrieved_chunks: List of chunk dicts from retriever.
        max_chars_per_chunk: Max characters per chunk in context (default 600). None = no truncation.

    Returns:
        Formatted prompt string.
    """
    retrieved_context = format_chunks_for_prompt(retrieved_chunks, max_chars_per_chunk)

    prompt = f"""You are an AI advisor for social innovation.

User Query:
{user_query}

Retrieved Context:
{retrieved_context}

Instructions:
- Provide a structured recommendation
- Use the retrieved context only
- Explain your reasoning clearly
- Be concise
- Mention relevant NGO names if found in the context

Return clean text output."""

    return prompt


def main() -> None:
    """Demo: Build a sample prompt."""
    query = "How can we design a solar pilot for rural villages?"
    chunks = [
        {"text": "Sample chunk about solar microgrids...", "source": "pilot1.txt", "category": "pilots"},
    ]
    prompt = build_prompt(query, chunks)
    print("Sample prompt:")
    print("-" * 40)
    print(prompt[:500] + "...")


if __name__ == "__main__":
    main()

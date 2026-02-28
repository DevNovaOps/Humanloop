"""
Ollama Client for HumanLoop RAG System

Connects to local Ollama API at http://localhost:11434/api/generate.
Uses mistral model. No external APIs.
"""

import requests
from typing import Optional

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "mistral"
# RAG prompts with context can be long; local LLM may need several minutes
DEFAULT_TIMEOUT = 300  # seconds


def generate(
    prompt: str,
    model: str = DEFAULT_MODEL,
    stream: bool = False,
    timeout: Optional[int] = None,
    num_predict: Optional[int] = None,
) -> str:
    """
    Send prompt to Ollama and return generated text.

    Args:
        prompt: The prompt to send to the LLM.
        model: Ollama model name (default: mistral).
        stream: Whether to stream the response (default: False for simpler usage).
        timeout: Request timeout in seconds. None = use DEFAULT_TIMEOUT (300).
        num_predict: Max tokens to generate. Lower = faster. e.g. 300 for quick responses.

    Returns:
        Generated text from the model.
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": stream,
    }
    if num_predict is not None:
        payload["options"] = {"num_predict": num_predict}

    to_use = timeout if timeout is not None else DEFAULT_TIMEOUT
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=to_use)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            "Could not connect to Ollama. Ensure Ollama is running at http://localhost:11434"
        )
    except requests.exceptions.Timeout:
        raise TimeoutError(
            "Ollama request timed out. RAG prompts are long—ensure Ollama has enough RAM; "
            "you can pass timeout=600 to generate() for slower machines."
        )
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"Ollama API error: {e}") from e


def main() -> None:
    """Demo: Generate a short response from Ollama."""
    prompt = "In one sentence, what is sustainable development?"
    print(f"Sending prompt: {prompt}")
    try:
        output = generate(prompt)
        print(f"Response: {output}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()

# HumanLoop RAG Engine

Local RAG (Retrieval-Augmented Generation) system for the HumanLoop social impact platform. Uses sentence-transformers, FAISS, and Ollama—no external APIs.

## Setup

1. **Create virtual environment** (recommended):
   ```
   python -m venv venv
   venv\Scripts\activate   # Windows
   ```

2. **Install dependencies**:
   ```
   pip install -r requirements.txt
   ```

3. **Install and run Ollama** (https://ollama.ai):
   - Install Ollama
   - Run: `ollama pull mistral` (for quality)
   - **Fastest** (~3–8s): `ollama pull qwen2:0.5b` (0.5B params, ~350MB)
   - Also fast: `ollama pull tinyllama` or `ollama pull phi3:mini`

4. **Build the vector index** (required before retrieval):
   ```
   python build_index.py
   ```

## Usage

- **Interactive demo**:
  ```
  python main_demo.py
  ```

- **Direct RAG pipeline**:
  ```python
  from rag_pipeline import run_rag
  answer, chunks = run_rag("How can NGOs support renewable energy?")
  ```

## Project Structure

```
rag_engine/
├── knowledge_base/    # Static .txt documents (ngos, pilots, sdg, guidelines)
├── kb_loader.py       # Document loader
├── chunker.py         # Text chunker (300-400 words, 50 overlap)
├── embedder.py        # SentenceTransformer embeddings
├── build_index.py     # FAISS index builder
├── retriever.py       # Vector search
├── llm/               # Ollama client + prompt builder
├── rag_pipeline.py    # End-to-end RAG
└── main_demo.py       # Interactive demo
```

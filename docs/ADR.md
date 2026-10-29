# Architecture Decision Record (ADR) - Local RAG Knowledge Infrastructure

**Date:** October 28, 2026  
**Status:** Approved & Implementing  

## System Architecture Overview

```
                          ┌────────────────────────────────────────────────────────┐
                          │               Applications / SDKs / CLI                │
                          │   (Python SDK, TypeScript SDK, REST API, CLI Tools)    │
                          └───────────────────────────┬────────────────────────────┘
                                                      │
                                           ┌──────────▼──────────┐
                                           │  FastAPI Web Layer  │
                                           │  (Auth, API Routes) │
                                           └──────────┬──────────┘
                                                      │
                       ┌──────────────────────────────┼──────────────────────────────┐
                       │                              │                              │
            ┌──────────▼──────────┐        ┌──────────▼──────────┐        ┌──────────▼──────────┐
            │ Ingestion Service   │        │ Hybrid Retrieval    │        │ Review & Feedback   │
            │ (Parsers & Chunkers)│        │ (Vector + Lexical)  │        │ (Workflow Engine)   │
            └──────────┬──────────┘        └──────────┬──────────┘        └──────────┬──────────┘
                       │                              │                              │
            ┌──────────▼──────────┐                   │                   ┌──────────▼──────────┐
            │ Embedding Provider  │                   │                   │ Annotations & Facts │
            │ (BGE-small / ONNX)  │                   │                   │ (Verified Context)  │
            └──────────┬──────────┘                   │                   └──────────┬──────────┘
                       │                              │                              │
                       └──────────────────────────────┼──────────────────────────────┘
                                                      │
                                           ┌──────────▼──────────┐
                                           │   Persistence       │
                                           │ Qdrant Vector DB    │
                                           │ SQLite Metadata DB  │
                                           └─────────────────────┘
```

## Decisions & Technology Selections

### 1. Vector Database: Qdrant Local Engine & Docker Option
- **Choice:** Qdrant in-process python client / Qdrant Docker container (`qdrant/qdrant:latest`).
- **Rationale:** Native support for multi-tenancy payloads (`application_id`, `collection_id`), high-performance HNSW index, filtering during vector search, payload indexing.
- **Port:** Bound to `127.0.0.1:6333` for localhost security.

### 2. Metadata & State Store: SQLite
- **Choice:** SQLite3 with WAL (Write-Ahead Logging) mode and Foreign Key constraints enabled.
- **Schema:**
  - `applications`: API keys, settings, status.
  - `collections`: Application binding, custom chunking parameters, embedding model specification.
  - `documents`: Source URI, type, content hash, version, ingestion status, metadata JSON.
  - `chunks`: Chunk index, document ID, collection ID, start/end byte offsets, content hash.
  - `review_cases`: Query ID, feedback type, status, resolution, reviewer ID.
  - `annotations`: Verified Q&A pairs, approved corrections, source references.
  - `audit_logs`: Timestamped event tracking for administrative operations.

### 3. Embedding Provider: Local HuggingFace / ONNX Runtime
- **Model:** `BAAI/bge-small-en-v1.5` (384-dimensional embeddings, 512 max tokens).
- **Runtime:** `fastembed` / `sentence-transformers` running locally on CPU/CUDA with fast batch processing.
- **Fallback:** ONNX runtime quantization for low-memory CPU execution.

### 4. Text Processing & Parsers
- **Text & Markdown:** Structure-aware heading and sentence chunker (`tiktoken`/character splitting).
- **PDF:** `pypdf` / `pdfplumber` text extraction.
- **DOCX:** `python-docx` XML parser.
- **JSON/JSONL/CSV:** Structured field flattening and row-based record extraction.
- **HTML:** `BeautifulSoup4` text and main body isolation.
- **Code:** Syntax-aware chunking preserving function/class boundaries.

### 5. Hybrid Retrieval Engine
- **Dense Vector:** Qdrant similarity search with distance scoring (Cosine / Dot product).
- **Sparse Lexical:** SQLite FTS5 (Full-Text Search) with BM25 scoring.
- **Combination:** Reciprocal Rank Fusion (RRF) with configurable $k$ parameter ($k=60$).
- **Source Provenance:** Full citation tracing (`document_id`, `source_uri`, `chunk_index`, offsets).

### 6. Generation & Answer Adapter
- **Generation Provider:** Optional local Ollama endpoint (`http://localhost:11434`) or OpenAI-compatible local server.
- **Strict Grounding:** Returns source citations and passages; states when evidence is insufficient. Works cleanly in retrieval-only mode if no LLM generator is running.

### 7. Security & Local-First Guarantees
- **Host Binding:** `127.0.0.1` (localhost only).
- **URL Ingestion:** Strict SSRF prevention blocking private ranges (`127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.169.254`).

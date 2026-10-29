# Local RAG Knowledge Infrastructure

A production-minded, fully local-first Retrieval-Augmented Generation (RAG) platform that acts as a reusable knowledge and memory service for all future projects.

## Features

- **Local-First**: All data (documents, embeddings, vector indexes, metadata, feedback) stays on your machine
- **Multi-Tenant**: `Instance → Application → Collection → Document → Chunk` hierarchy with strict namespace isolation
- **Model-Agnostic**: Local embedding models (BGE, MiniLM, etc.) with optional remote generation adapters (Ollama, OpenAI-compatible)
- **Hybrid Retrieval**: Vector similarity + Lexical (BM25/FTS5) combined with Reciprocal Rank Fusion (RRF)
- **Controlled Feedback Loop**: Feedback submission → Review queues → Approved corrections → Re-indexing (no silent data mutation)
- **Multi-Interface**: REST API (FastAPI), Python SDK, TypeScript SDK, CLI
- **Data Exchange**: Export/import, backup/restore, audit logging
- **Secure**: Localhost-only binding, SSRF-protected URL ingestion, API key auth, no external data leakage

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Applications / SDKs / CLI                │
└─────────────────────────────┬───────────────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │  FastAPI Web Layer │
                    │ (Auth, API Routes) │
                    └─────────┬─────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼───────┐   ┌─────────▼─────────┐   ┌───────▼───────┐
│ Ingestion     │   │ Hybrid Retrieval  │   │ Review &      │
│ (Parsers &    │   │ (Vector + Lexical)│   │ Feedback      │
│ Chunkers)     │   │                   │   │ (Workflow)    │
└───────┬───────┘   └─────────┬─────────┘   └───────┬───────┘
        │                     │                     │
┌───────▼───────┐             │             ┌───────▼───────┐
│ Embedding     │             │             │ Annotations   │
│ Provider      │             │             │ & Facts       │
│ (BGE-small)   │             │             │ (Verified)    │
└───────┬───────┘             │             └───────┬───────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   Persistence     │
                    │ Qdrant Vector DB  │
                    │ SQLite Metadata   │
                    └───────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.10+
- Docker (for Qdrant)
- ~2GB disk space for models

### Installation

```bash
# Clone and setup
cd ~/local-rag

# Start Qdrant
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant:latest

# Create virtual environment and install
python3 -m venv .venv
source .venv/bin/activate
pip install -e .  # or use the uv-based install in the build script

# Start server
python -m src.api.main
```

### Using the Python SDK

```python
from src.sdk.python.client import LocalRAGClient

client = LocalRAGClient("http://127.0.0.1:8001")

# Register application
client.register_application("myapp", "My Application")

# Create collection
client.create_collection("myapp", "docs", "My Documents")

# Ingest text
client.ingest_text(
    app_id="myapp",
    collection_id="docs",
    text="Your document content here...",
    source_uri="https://example.com/doc1",
    document_id="doc1",
    metadata={"topic": "example"}
)

# Search
results = client.search("myapp", "docs", "your query", top_k=5)

# Get context for generation
context = client.get_context("myapp", "docs", "your question", top_k=3)

# Grounded Q&A (retrieval-only mode works without LLM)
answer = client.ask("myapp", "docs", "What is ...?")

# Submit feedback
client.submit_feedback(
    app_id="myapp",
    collection_id="docs",
    query="your question",
    feedback_type="helpful",
    rating=5,
    explanation="Good answer",
    retrieved_chunks=[...],
    response="The answer..."
)
```

### Using the CLI

```bash
# Health check
local-rag --url http://127.0.0.1:8001 health

# Register application
local-rag --url http://127.0.0.1:8001 app create --id myapp --name "My App"

# Create collection
local-rag --url http://127.0.0.1:8001 collection create --app-id myapp --id docs --name "Documents"

# Ingest text
local-rag --url http://127.0.0.1:8001 ingest text \
  --app-id myapp --collection-id docs \
  --text "Document content" --source-uri "https://example.com/doc1"

# Search
local-rag --url http://127.0.0.1:8001 search \
  --app-id myapp --collection-id docs --query "your query" --top-k 5

# Ask (grounded generation)
local-rag --url http://127.0.0.1:8001 ask \
  --app-id myapp --collection-id docs --query "What is ...?"

# Submit feedback
local-rag --url http://127.0.0.1:8001 feedback \
  --app-id myapp --collection-id docs \
  --query "question" --feedback-type helpful --rating 5
```

## API Reference

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Basic health check |
| GET | `/health/ready` | Readiness with dependency checks |
| POST | `/applications` | Register application |
| GET | `/applications/{app_id}` | Get application |
| POST | `/applications/{app_id}/collections` | Create collection |
| GET | `/applications/{app_id}/collections` | List collections |
| POST | `/ingest/text` | Ingest raw text |
| POST | `/ingest/file` | Upload and ingest file |
| POST | `/search` | Hybrid search (RRF) |
| POST | `/search/vector` | Vector-only search |
| POST | `/search/lexical` | Lexical-only search |
| POST | `/search/context` | Get formatted context |
| POST | `/generate/ask` | Grounded Q&A |
| POST | `/feedback` | Submit feedback |
| GET | `/feedback/{app_id}/pending` | List pending reviews |
| POST | `/feedback/annotations` | Create verified annotation |

See `/docs` on running server for full OpenAPI documentation.

## Data Model

```
Application
├── id (str)
├── name (str)
├── api_key_hash (str)
└── created_at

Collection (per Application)
├── id (str)
├── name (str)
├── embedding_model (str)
├── embedding_dim (int)
├── chunk_strategy (str)
├── chunk_size (int)
├── chunk_overlap (int)
└── created_at

Document (per Collection)
├── id (str)
├── source_uri (str)
├── source_type (str)
├── content_hash (str)
├── document_version (int)
├── metadata (JSON)
├── access_scope (str)
└── status (indexed/pending/error)

Chunk (per Document)
├── chunk_id (UUID)
├── document_id (str)
├── chunk_index (int)
├── content (str)
├── content_hash (str)
├── start/end_offset (int)
├── metadata (JSON)
└── embedding (vector in Qdrant)
```

## Supported File Formats

| Format | Parser | Notes |
|--------|--------|-------|
| .txt, .md, .py, .js, .json, .yaml, etc. | TextParser | Structure-aware chunking |
| .pdf | PDFParser (pdfplumber/pypdf) | Text extraction |
| .docx | DocxParser (python-docx) | Paragraph extraction |
| .html | HTMLParser (BeautifulSoup) | Main content extraction |
| .csv | CSVParser | Row-based JSON records |
| .json/.jsonl | JSONParser | Record flattening |

## Embedding Models

| Model | Dimensions | Max Tokens | Languages | Size |
|-------|------------|------------|-----------|------|
| BAAI/bge-small-en-v1.5 | 384 | 512 | English | 134 MB |
| BAAI/bge-base-en-v1.5 | 768 | 512 | English | 440 MB |
| BAAI/bge-large-en-v1.5 | 1024 | 512 | English | 1.3 GB |
| sentence-transformers/all-MiniLM-L6-v2 | 384 | 256 | English | 90 MB |
| paraphrase-multilingual-MiniLM-L12-v2 | 384 | 128 | 12 langs | 420 MB |

Default: `BAAI/bge-small-en-v1.5` (fast, efficient, good quality)

## Feedback & Review Workflow

1. **Submit Feedback** - Users rate retrieval/generation (helpful, hallucination, missing_info, etc.)
2. **Review Queue** - Reviewers inspect query, response, retrieved chunks, and feedback
3. **Resolve** - Mark as accepted/rejected/resolved with notes
4. **Create Annotation** - Approved corrections become verified Q&A entries
5. **Re-index** - Annotations can be added to collection for future retrieval

**Key Principle**: Feedback never silently mutates trusted data. All changes go through explicit review and approval.

## Security

- **Localhost Binding**: All services bind to `127.0.0.1` by default
- **API Keys**: Per-application API key authentication
- **SSRF Protection**: URL ingestion blocks private IPs (127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- **Input Validation**: Request size limits, Pydantic schema validation
- **Secrets**: Environment variables only, excluded from version control

## Testing

```bash
# Run integration tests
PYTHONPATH=. .venv/bin/python tests/test_full_flow.py

# Run demo
PYTHONPATH=. .venv/bin/python examples/demo_app.py
```

## Project Structure

```
local-rag/
├── src/
│   ├── api/
│   │   ├── main.py              # FastAPI app entry point
│   │   └── routes/              # API route modules
│   ├── core/
│   │   ├── sqlite_store.py      # SQLite metadata store
│   │   ├── qdrant_store.py      # Qdrant vector store wrapper
│   │   ├── embedding.py         # Embedding provider & registry
│   │   ├── parsers.py           # Document parsers & chunkers
│   │   ├── ingestion.py         # Ingestion pipeline
│   │   ├── retrieval.py         # Hybrid retrieval (RRF)
│   │   └── generation.py        # Generation adapters
│   ├── sdk/
│   │   ├── python/client.py     # Python SDK
│   │   └── typescript/          # TypeScript SDK
│   └── cli/
│       └── main.py              # CLI entry point
├── tests/
│   ├── test_full_flow.py        # Integration tests
│   └── test_sqlite.py           # Unit tests
├── examples/
│   └── demo_app.py              # Demo application
├── docs/
│   └── ADR.md                   # Architecture Decision Record
├── data/                        # SQLite DB, sample data
├── README.md
└── pyproject.toml
```

## License

MIT License - See LICENSE file for details.
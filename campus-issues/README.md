# Campus Issues

A local-first campus issue reporting and tracking system built on top of the Local RAG infrastructure.

## Features

### Student Features
- **Report Issues**: Submit complaints with title, description, category, building, and location
- **Track Status**: View all submitted tickets with real-time status updates
- **Duplicate Detection**: RAG-powered similarity search warns about existing similar issues before submission
- **Status History**: Complete timeline of status changes with actor details

### Staff Features
- **Dashboard**: Filterable view of all tickets with statistics
- **Ticket Management**: Update status through defined workflow (Submitted → Acknowledged → Assigned → In Progress → Resolved → Closed)
- **Assignment**: Assign tickets to team members
- **Internal Notes**: Add private notes visible only to staff
- **Reopen Support**: Reopen closed tickets when needed

### Admin Features
- All staff capabilities
- User role management
- System analytics (via dashboard stats)

## Architecture

```
Campus Issues (FastAPI + Jinja2 + HTMX)
    │
    ├── SQLite (metadata.db) — Users, Tickets, History
    ├── Qdrant (localhost:6333) — Vector embeddings for tickets
    └── BGE-small-en-v1.5 — Local embedding model
```

### Tech Stack
- **Backend**: FastAPI (reuses Local RAG core modules)
- **Frontend**: Jinja2 templates + HTMX + Tailwind CSS + Alpine.js
- **Auth**: Session-based with `itsdangerous` signing, `passlib` (pbkdf2_sha256)
- **Database**: SQLite with WAL mode, FTS5 for lexical search
- **Vector DB**: Qdrant (shared with Local RAG)
- **Embeddings**: BAAI/bge-small-en-v1.5 (384-dim, local)

## Quick Start

### Prerequisites
- Python 3.10+
- Docker (for Qdrant)
- ~2GB disk space for embedding model

### Setup

```bash
cd ~/local-rag/campus-issues

# Start Qdrant (if not already running)
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant:latest

# Install dependencies
cd ~/local-rag
uv pip install --python .venv/bin/python jinja2 itsdangerous passlib bcrypt

# Run Campus Issues
cd campus-issues
PYTHONPATH=/home/saamarth/local-rag .venv/bin/python -m app.api.main
```

### Access
- **Application**: http://127.0.0.1:8002
- **API Docs**: http://127.0.0.1:8002/docs

### Default Accounts (seeded on first run)
| Role | Email | Password |
|------|-------|----------|
| Student | alice@example.com | student123 |
| Student | bob@example.com | student123 |
| Staff | maintenance@campus.local | staff123 |
| Staff | facilities@campus.local | staff123 |
| Admin | admin@campus.local | admin123 |

## Ticket Lifecycle

```
Submitted → Acknowledged → Assigned → In Progress → Resolved → Closed
    │            │            │            │             │
    └─ Rejected ─┴────────────┴────────────┴─────────────┘
    │
    └─ Duplicate (terminal)
```

### Valid Transitions
| From | To |
|------|-----|
| Submitted | Acknowledged, Rejected, Duplicate |
| Acknowledged | Assigned, Rejected |
| Assigned | In Progress, Rejected |
| In Progress | Resolved, Rejected |
| Resolved | Closed, Reopened |
| Closed | Reopened |
| Reopened | Assigned, In Progress, Rejected |

## RAG Integration

### Duplicate Detection
When a student submits a report, the system:
1. Queries the RAG index with the title + description
2. Returns similar existing tickets (RRF score > 0.01)
3. Shows similar tickets as potential duplicates
4. User can review or confirm submission anyway

### Re-indexing on Status Change
When staff updates ticket status, the ticket is re-ingested into the RAG index with updated metadata, ensuring search reflects current state.

## Project Structure

```
campus-issues/
├── app/
│   ├── api/
│   │   └── main.py          # FastAPI entry point
│   ├── core/
│   │   └── campus_auth.py   # Session auth, password hashing
│   └── routes/
│       └── campus_issues.py # All route handlers
├── templates/
│   ├── base.html            # Base layout
│   ├── login.html
│   ├── register.html
│   ├── student_dashboard.html
│   ├── report.html          # Issue submission + duplicate warning
│   ├── ticket_detail.html
│   ├── staff_dashboard.html
│   └── staff_ticket_detail.html
├── data/
│   └── metadata.db          # SQLite database
└── README.md
```

## Reusing Local RAG Infrastructure

The Campus Issues app reuses these Local RAG modules directly:
- `src.core.sqlite_store` — SQLite metadata store (with Campus Issues tables added)
- `src.core.qdrant_store` — Qdrant vector store wrapper
- `src.core.embedding` — BGE embedding provider
- `src.core.ingestion` — Text ingestion pipeline
- `src.core.retrieval` — Hybrid retrieval (vector + lexical via RRF)

The app creates its own `campus-issues` application and `tickets` collection in the shared RAG infrastructure.

## Configuration

Environment variables (create `.env` in campus-issues/):
```bash
CAMPUS_SECRET_KEY=your-secret-key-here  # Required for production
CORS_ALLOW_ORIGINS=http://localhost:8001,http://localhost:8080
```

## Testing

```bash
# Register student
curl -X POST http://127.0.0.1:8002/register \
  -d "username=test&email=test@example.com&password=test123&confirm_password=test123"

# Login
curl -X POST http://127.0.0.1:8002/login \
  -d "email=test@example.com&password=test123" \
  -c cookies.txt

# Submit report
curl -X POST http://127.0.0.1:8002/report \
  -b cookies.txt \
  -d "title=Test Issue&description=Details&category=Wi-Fi&building=Main&location=Room 1"
```

## License

MIT License - See LICENSE file for details.
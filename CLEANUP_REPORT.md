# Cleanup Report — local-rag test/demo artifacts

**Date:** 2026-10-29
**Scope:** Phase 1 — Safe cleanup of test/demo artifacts before building Campus Issues
**Backup:** `~/.local-rag-backup-20261029/` (27 MB, full source + DBs + config)
**Manifest:** `~/.local-rag-backup-20261029/manifest/ARTIFACTS.md`

## 1. Artifacts identified and deleted

| Category | Items |
|---|---|
| Demo websites | `nasa-website/` (single HTML), `dashboard/` (single HTML) |
| Demo scripts | `nasa_demo.py`, `examples/demo_app.py` |
| Test DBs (5) | `data/repro_metadata.db`, `data/test_metadata.db`, `data/test_backup.db`, `data/cleanroom_test.db`, `tests/test_metadata.db` (+ WAL/SHM) |
| Test scripts (5) | `tests/cleanroom_test.py`, `tests/test_backup_restore.py`, `tests/test_full_flow.py`, `tests/test_sqlite.py`, `tests/test_dashboard.py` |
| Demo backend modules (6) | `src/core/nasa_ingestor.py`, `src/core/website_platform.py`, `src/core/sources.py`, `src/api/routes/nasa.py`, `src/api/routes/dashboard.py`, `src/api/routes/sources.py` |
| Demo data rows | 16 applications, 13 collections, 33 documents, 74 chunks, 2 sources, 3 API keys, 6 review cases, 4 annotations, 18 audit logs in `data/metadata.db` |
| Qdrant demo collection | `nasa_primary` (and 9 other orphaned test collections) |
| Dev reports (4) | `AUDIT_AND_PLAN.md`, `AUDIT_REPORT.md`, `DASHBOARD_FIX_REPORT.md`, `FINAL_REPORT.md` |

## 2. Preserved (untouched)

- Core RAG: `src/core/sqlite_store.py`, `auth.py`, `backup.py`, `embedding.py`, `parsers.py`, `ingestion.py`, `retrieval.py`, `generation.py`
- API: `src/api/main.py` (NASA/dashboard/sources references removed), `routes/health.py`, `applications.py`, `ingestion.py`, `retrieval.py`, `generation.py`, `feedback.py`
- SDK/CLI: `src/sdk/`, `src/cli/`
- Config: `README.md`, `.env.example`, `.gitignore`, `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `docs/ADR.md`
- `tests/eval/` (empty)
- Qdrant service, SQLite schema, embedding model, all installed dependencies

## 3. Post-cleanup verification

| Check | Result |
|---|---|
| `import src.api.main` | OK |
| FastAPI server `127.0.0.1:8001` | `{"status":"ready","checks":{"sqlite":"ok","qdrant":"ok","embeddings":"ok"}}` |
| OpenAPI paths | 25 endpoints, all core RAG routes intact (no `/nasa`, `/dashboard`, `/sources`) |
| `data/metadata.db` | 0 rows in all 9 tables |
| Qdrant collections | 0 (empty) |
| End-to-end ingest → search | Verified: 1 chunk ingested, 1 result returned, then cleaned up |

## 4. No destructive commands used

No `rm -rf` on project roots, no full DB wipe, no Qdrant reset, no git history rewrite. All deletions targeted confirmed test/demo artifacts. A full backup precedes every destructive operation.

## 5. Outstanding

None. RAG infrastructure is operational and clean, ready for Campus Issues.
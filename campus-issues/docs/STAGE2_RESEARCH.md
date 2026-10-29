# STAGE 2 — Research Notes
**Campus Issues** | Date: 2026-10-29

## 1. Existing Solutions & Competitors

| Solution | Type | Strengths | Limitations |
|---|---|---|---|
| Issuetrak | Commercial SaaS | Multi-department, complaint tracking, IT helpdesk | Expensive, not campus-specific, no RAG |
| FMX | Commercial SaaS | Work orders, preventive maintenance, space management | Facilities-only, no student-facing portal |
| Incident IQ | K-12 focused | Simple ticket submission | Not designed for higher-ed workflows |
| Zendesk / Freshdesk | Generic helpdesk | Mature lifecycle, SLA tracking | Overkill for campus, per-agent pricing |
| GitHub Issues | Dev tool | Labels, assignment, status | No RBAC for students vs staff, no categories |
| WhatsApp groups | Informal | Zero friction | No tracking, no dedup, no analytics |

**Gap:** No free, local-first solution that combines student-facing complaint submission with staff dashboard AND uses RAG for duplicate detection.

## 2. Ticket Lifecycle Best Practices

Based on industry research (Zendesk, Vivantio, Zluri guides):

Standard lifecycle: **New → Open/Triage → Assigned → In Progress → On Hold (optional) → Resolved → Closed**

Key findings:
- "Resolved" ≠ "Closed". Resolved means fix applied; Closed means requester confirmed or timeout elapsed.
- Reopen must be supported — sends ticket back to In Progress.
- Every transition needs: timestamp, actor identity, optional note.
- Invalid transitions must be blocked (e.g., can't go from New directly to Closed without resolution).
- Status definitions must be enforced by backend, not UI convention.

Our adapted lifecycle: `Submitted → Acknowledged → Assigned → In Progress → Resolved → Closed` + `Rejected` and `Duplicate` terminal states.

## 3. Technology Findings

### Backend (reuse existing)
- **FastAPI** already installed, running on port 8001
- **SQLite** via `src/core/sqlite_store.py` — supports FTS5, WAL mode, foreign keys
- **Qdrant** + **BGE-small-en-v1.5** (384-dim) for vector search
- **Auth**: API key based (`src/core/auth.py`) — needs extension for user/password auth with roles
- **Jinja2** now installed for server-side templates
- **Passlib + bcrypt** now installed for password hashing
- **python-multipart** already present for form data + file uploads
- **itsdangerous** installed for session tokens

### Frontend
- **HTMX** (CDN, no build step) — perfect for server-rendered interactive pages
- **Tailwind CSS** (CDN) — matches existing dashboard pattern
- **Alpine.js** (CDN) — lightweight client state for modals/dropdowns

### RAG Integration Points
The existing RAG API contract:
- `POST /search` `{app_id, collection_id, query, top_k}` → hybrid search results
- `POST /ingest/text` → index complaint descriptions for similarity matching
- `DELETE /ingest/{app_id}/{collection_id}/{document_id}` → remove from index on deletion

Use case: When a student types a complaint description, query the RAG for similar existing complaints BEFORE submission to suggest duplicates.

## 4. Security & Privacy Requirements

- FERPA considerations: student identity/complaints are educational records
- Students must only see their own complaints (or anonymized public ones)
- Internal staff notes never visible to students
- Password hashing mandatory (bcrypt via passlib)
- Session tokens signed (itsdangerous)
- File uploads: restrict to images (jpg/png/webp), max 5MB
- Rate limiting on submission endpoint
- CSRF protection for forms

## 5. Accessibility

- WCAG 2.1 AA target
- Semantic HTML (nav, main, section, button, form labels)
- Focus management for HTMX swaps
- Color contrast ≥ 4.5:1
- Screen reader announcements for status changes
- Mobile-first (students report from phones)

## 6. Source Register

| Source | URL | Accessed | Type |
|---|---|---|---|
| Issuetrak Education | issuetrak.com/solutions/education | 2026-10-29 | Vendor site |
| FMX Higher Ed | gofmx.com/higher-education-facilities-management-software | 2026-10-29 | Vendor site |
| Zendesk Ticket Lifecycle | support.zendesk.com/.../ticket-lifecycle | 2026-10-29 | Documentation |
| Zluri Ticket Statuses | zluri.com/blog/ticket-statuses | 2026-10-29 | Industry guide |
| Vivantio Support Lifecycle | vivantio.com/blog/support-ticket-lifecycle-viv | 2026-10-29 | Industry guide |
| Plane Issue Tracking | plane.so/blog/issue-tracking-workflow | 2026-10-29 | Industry guide |

## 7. Identified Opportunities

1. **RAG-powered duplicate detection** — unique differentiator vs all competitors
2. **Local-first, no cloud dependency** — works offline in campus intranet
3. **Zero cost** — no SaaS subscription needed
4. **Existing infrastructure** — 80% of backend plumbing already built
5. **Import workflow** — seed buildings/departments from CSV for any campus
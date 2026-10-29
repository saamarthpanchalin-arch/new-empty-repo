# STAGE 5 — MVP Planning & STAGE 6 — Technology
**Campus Issues** | Date: 2026-10-29

---

## Stage 5 — MVP Planning

### A. MVP Features
- **Must-haves:**
    - Student Login/Signup
    - Report issue form (title, desc, category, building, location)
    - Ticket tracking dashboard (list + status indicator)
    - Ticket details view (status history, public updates, original request)
    - Staff dashboard (list unresolved, assign, change status, internal notes)
    - Duplicate detection (RAG search on form submission)
- **Should-haves:**
    - Email-style status change notifications
    - Image attachment (safety-verified)
    - Simple search filtering (by category/building)
- **Excluded:**
    - Complex analytics dashboards
    - Automated email triggers
    - Third-party integration (e.g., Jira/Slack)

### B. User Flow
1. Student logs in.
2. Clicks "Report Issue".
3. Enters details → Submission triggers RAG lookup.
4. If duplicates found, user reviews or confirms submission.
5. System creates ticket, returns ID.
6. Staff see ticket on dashboard.
7. Staff assigns, marks In Progress, adds note.
8. Student sees state changes on tracker.

### C. Acceptance Criteria (Must-Haves)
1. Unique ticket ID generation (e.g., `C-20261029-001`).
2. Server-side validation (all fields present, file type checks).
3. RBAC (students cannot assign/resolve, admins can do all).
4. Persistence verified via service restart.
5. Search matches existing issue titles/descriptions.

---

## Stage 6 — Technology & Roles

### Stack
- **Frontend:** Jinja2 (server-rendered HTML), HTMX (interactions), Tailwind CSS (styling), Alpine.js (modals).
- **Backend:** FastAPI (reusing existing app).
- **Database:** SQLite + Qdrant.
- **Auth:** Session tokens (`itsdangerous`) + Password hashing (`bcrypt`).
- **Deployment:** Docker/Docker Compose.

### Workstreams
1. **Model/Schema:** Define `User`, `Ticket`, `AuditLog`, `StatusHistory` in SQLite.
2. **Auth:** Implement Session handling, login/signup forms, role-based decorators.
3. **Complaint Workflow:** Forms, backend routes, status state machine.
4. **Staff Dashboard:** Lists, search, ticket assignment/status update.
5. **RAG Integration:** Connect submission form to RAG vector search.
6. **Testing:** Unit + Integration tests.

### Secrets/Environment
- `SECRET_KEY` (Auth): `/app/campus-issues/.env`
- Acquisition: `openssl rand -base64 32`
- Check: Verify `SECRET_KEY` is non-empty at app start.
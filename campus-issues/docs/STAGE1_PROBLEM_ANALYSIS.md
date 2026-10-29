# STAGE 1 — Problem Analysis
**Campus Issues** — Student issue reporting, tracking, and resolution
**Date:** 2026-10-29

---

## 1. Problem Statement

Students on college campuses frequently face problems such as broken classroom
equipment, Wi-Fi connectivity issues, unclean washrooms, water shortages, and
damaged campus facilities.

Currently these problems are reported **verbally to college staff or through
informal messaging groups**. As a result:

| Symptom | Root cause |
|---|---|
| Complaints are overlooked | No central queue; reports live in chat history that scrolls away |
| Duplicate complaints raised | No visibility into what is already reported |
| Students cannot track resolution | No persistent record; status communicated ad hoc |
| Administrators lack overview | No analytics on recurring/unresolved issues |

**Core problem:** Campus facilities issues are reported through channels with no
persistence, no ownership, and no visibility. The fix is a structured system
that makes reporting, assignment, and resolution transparent and auditable.

## 2. Target Users & Personas

### Student (Reporter)
- Submits a complaint with title, description, category, location, optional photo
- Receives a unique ticket ID
- Tracks status and progress; views status-change history
- Sees similar existing complaints before duplicating effort
- Gets notified on status changes (where configured)
- **Cannot** see other students' private info, staff notes, or admin actions

### Staff (Resolver)
- Dashboard of incoming/unresolved complaints
- Filter by category, building, priority, status, date
- Assign to a department/person; move through a defined workflow
- Add **internal notes** (hidden from students) and **public updates** (visible)
- Mark resolved with a resolution record; reopen when appropriate
- Identify duplicates and recurring problems

### Administrator
- All staff capabilities plus:
- View analytics (resolution time, unresolved counts, issue frequency, building trends)
- Export authorized reports
- Manage roles/permissions
- **Students must not reach admin actions by modifying frontend requests**

## 3. Constraints

| Type | Constraint |
|---|---|
| Technical | Reuse existing Local RAG for search/similarity; use SQLite for structured records |
| Time | MVP first; core submit→track→resolve workflow before analytics polish |
| Financial | Local-first; no paid external APIs for core flow |
| Operational | Runs on localhost during dev; synthetic sample data only (no real campus info) |
| Security | RBAC, server-side auth checks, password hashing, file validation, audit trail |
| Privacy | No student PII exposure to other users; internal notes hidden |

## 4. Success Metrics (measurable)

1. Student can submit a complaint and receive a unique ticket ID in < 5 s
2. Ticket ID is globally unique (UUID + sequential number)
3. Status transitions are enforced: only valid transitions allowed
4. Staff can assign and resolve; each transition records timestamp + actor
5. Backend rejects unauthorized requests (student → admin endpoint = 403)
6. Duplicate detection surfaces similar open complaints at submission time
7. Data survives service restart (SQLite persistence verified)
8. Search-index stays consistent after edits/deletes (RAG re-indexed)
9. All must-have features have passing automated tests

## 5. Assumptions (to validate, not assert)

- The user will supply real campus buildings/departments later via a clearly
  labelled import workflow; for now we use synthetic sample records.
- Email/notification provider is optional; polling is the default notification
  mechanism.
- No real student identities are created; all dev accounts are synthetic.
- The app is not claimed to be officially adopted by any college.

## 6. Deliverables

- Requirements document (this file)
- Research notes + source register (`STAGE2_RESEARCH.md`)
- 3–5 solution concepts + decision matrix (`STAGE3_IDEATION.md`)
- MVP scope + acceptance criteria (`STAGE5_MVP_PLANNING.md`)
- Architecture + tech stack (`STAGE6_TECH.md`)
- Working prototype (code)
- Test results (`STAGE8_TESTING.md`)
- Presentation outline (`STAGE9_PRESENTATION.md`)
- Submission package (`README.md`, setup docs)
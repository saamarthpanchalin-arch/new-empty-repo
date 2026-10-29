# STAGE 3 — Ideation & STAGE 4 — Solution Selection
**Campus Issues** | Date: 2026-10-29

---

## Stage 3 — Ideation (3 Solution Options)

### Option 1: Full SPA (React + FastAPI + PostgreSQL)
- **Concept:** Modern Single Page Application built with React/Vite communicating with FastAPI via REST.
- **Target Users:** Students and staff.
- **Main Workflow:** Rich client-side routing, instant filtering, optimistic UI updates.
- **Expected Benefit:** Highly fluid, app-like user experience.
- **Technical Requirements:** Node.js build step, React router, Tailwind, separate frontend container, JWT auth.
- **Risks & Limitations:** Adds a complex frontend build pipeline, separate hosting, and heavier setup burden.
- **Differentiation:** Most polished UI feel, but violates the "smallest complete change" rule.

### Option 2: Server-Rendered with HTMX & Jinja2 (FastAPI Monolith)
- **Concept:** Server-side rendered templates via Jinja2 enhanced with HTMX for dynamic partial page updates, paired with FastAPI.
- **Target Users:** Students, staff, administrators.
- **Main Workflow:** HTML rendered on server, HTMX swaps partials on form submission/search/tab-switch without full reloads.
- **Expected Benefit:** Single codebase, zero separate build steps, extremely fast to load, reuses Python/FastAPI entirely.
- **Technical Requirements:** Jinja2, HTMX (CDN), Tailwind (CDN), SQLite, existing RAG infrastructure.
- **Risks & Limitations:** Slightly less rich client-side state animation than a full SPA, but more than sufficient for issue tracking.
- **Differentiation:** Perfect balance of speed, simplicity, robustness, and zero frontend toolchain bloat.

### Option 3: CLI + Static HTML Dashboard
- **Concept:** Pure static HTML pages fetching JSON from FastAPI endpoints with vanilla JavaScript.
- **Target Users:** Basic demo evaluators.
- **Main Workflow:** Client-side rendering via fetch.
- **Expected Benefit:** Simpler than React, no HTMX dependency.
- **Technical Requirements:** Vanilla JS fetch logic, DOM manipulation boilerplate.
- **Risks & Limitations:** Verbose vanilla JS code for form validation, state management, and error handling.
- **Differentiation:** Simple, but tedious to maintain forms and validation states without a framework or HTMX.

---

## Stage 4 — Solution Selection (Decision Matrix)

### Evaluation Criteria (Weighted)
1. **Relevance to Problem (25%):** How well it solves reporting, tracking, and staff management.
2. **Implementation Speed & Feasibility (25%):** Fits within local-first python environment without external build tools.
3. **Maintainability & Simplicity (20%):** Minimal dependencies, easy to audit and run.
4. **Demonstrability (15%):** Smooth user flows, clear status badges, responsive UI.
5. **RAG Integration (15%):** Seamless connection to existing search and duplicate detection.

### Decision Matrix Scorecard

| Criterion (Weight) | Option 1 (React SPA) | Option 2 (Jinja + HTMX) | Option 3 (Vanilla JS) |
|---|---|---|---|
| Relevance (25%) | 9 / 10 | **9 / 10** | 7 / 10 |
| Feasibility (25%) | 6 / 10 | **10 / 10** | 8 / 10 |
| Maintainability (20%) | 6 / 10 | **9 / 10** | 7 / 10 |
| Demonstrability (15%) | 9 / 10 | **9 / 10** | 6 / 10 |
| RAG Integration (15%) | 8 / 10 | **9 / 10** | 7 / 10 |
| **Weighted Score** | **7.45** | **9.25** | **7.15** |

### Selected Solution
**Option 2: Server-Rendered with Jinja2 & HTMX.**
- **Rationale:** It offers the highest feasibility and maintainability while providing modern dynamic interactions (instant search, partial updates, modal dialogs) without requiring Node.js, Webpack, Vite, or npm build pipelines. It aligns perfectly with the "smallest complete change" principle and reuses the existing FastAPI backend directly.
- **Rejected Alternatives:** Option 1 (React) was rejected due to unnecessary build complexity and separate toolchain overhead. Option 3 (Vanilla JS) was rejected because manual DOM manipulation for complex forms and tabs leads to messy boilerplate.
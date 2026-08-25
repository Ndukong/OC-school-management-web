# Skills & Knowledge Required

## Core Technologies
- **Python 3.11+** — backend language
- **Django 5.x** — web framework (ORM, admin, auth, REST)
- **Django REST Framework (DRF)** — API for mobile mark entry
- **SQLite** — zero-config database (local deployment)
- **WeasyPrint** — HTML/CSS to PDF with precise layout control
- **HTML5 + CSS3 + JavaScript** — frontend templates
- **Bootstrap 5** or **Tailwind CSS** — responsive UI for mobile/desktop

## Supporting Libraries
- **openpyxl** — .xlsx import/export (bulk student registration, subject competencies)
- **Pillow** — image processing (student photos, logo, seal)
- **django-crispy-forms** — better form rendering
- **django-auditlog** or custom audit middleware — audit trail
- **django-mptt** or **django-treebeard** — if hierarchical classes needed
- **Webcam.js** or **MediaDevices API** — student photo capture from browser

## Development Tools
- **Git** — version control
- **pip + virtualenv** or **uv** — Python package management
- **Black + Ruff** — code formatting & linting
- **pytest-django** — testing
- **SQLite Browser** (optional) — inspect local database

## Deployment Skills
- **NSSM** (Non-Sucking Service Manager) or **Windows Task Scheduler** — run Django as a Windows service
- **ngrok** or local tunnel — if remote debugging needed
- **WiFi hotspot setup** — school laptop as local server

## Design Patterns
- **Multi-tenant architecture** — `school_id` on every table
- **Repository pattern** — data access layer for complex queries
- **Template method pattern** — report generation with common base class
- **Observer pattern** — audit log via Django signals
- **DRY principle** — shared mixins for permission checks, school scoping

## Testing Strategy
- **Unit tests** — model validation, scoring logic, permission checks
- **Integration tests** — API endpoints, bulk import, report generation
- **Snapshot tests** — PDF output compared to known-good versions
- **Property-based tests** — edge cases in grading formulas

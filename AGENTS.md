# OpenCode Agents Configuration

This file documents the agent patterns and conventions used when working with OpenCode on this project.

## Project Context
- **Language:** Python 3.10+
- **Framework:** Django 5.x
- **Database:** SQLite (development), PostgreSQL (optional production)
- **PDF Engine:** WeasyPrint
- **Test Framework:** pytest-django
- **Linting:** Ruff
- **Formatting:** Black

## Before Writing Code
1. Always check existing models in `core/models/` before creating new ones
2. Verify database migrations exist and are up-to-date
3. Check for existing utility functions in `core/utils/`
4. Read relevant test files to understand testing patterns

## Code Conventions
- Follow Django best practices (Fat models, thin views, dumb templates)
- Use Class-Based Views (CBVs) where possible
- All database queries must filter by `school_id` (multi-tenant)
- Use Django's `@login_required` and custom permission decorators
- Write tests for every new feature
- Use type hints on all function signatures
- No hardcoded strings in templates — use `{% trans %}` for future i18n
- Comments: None unless absolutely necessary for complex logic

## Testing Conventions
- Test file location: `tests/test_<module>.py`
- Use pytest fixtures for test data
- Name tests as `test_<feature>_<expected_behavior>`
- Run tests: `pytest`
- Run linter: `ruff check .`
- Run formatter: `black .`

## Report Generation
- All reports extend a base `BaseReport` class in `core/utils/reports.py`
- Grading logic lives in `core/utils/grading.py`
- Report card generator in `core/utils/report_card.py`
- Templates live in `templates/reports/`
- CSS for PDFs in `static/reports/css/`
- Use WeasyPrint's `@page` rules for exact page dimensions
- Preview mode: render to HTML first (`preview_term_report` view), then PDF for final
- Views in `core/views/reports.py`; URLs in `config/urls.py`

## Permissions (User Roles)
- `superuser` — full access
- `admin` (principal/VP) — everything except system transfer
- `bursar` — finance only
- `class_master` — their assigned class only
- `teacher` — their assigned subjects only

## Deployment (Phase 12)
- Windows-first deployment targets a non-technical school administrator.
- Batch scripts live at project root: `setup.bat`, `start_server.bat`, `backup.bat`, `wifi_hotspot.bat`, `nssm_service.bat`.
- Full deployment guide: `DEPLOYMENT.md`; screenshots referenced from `screenshots/`.
- `core/management/commands/seed_default_config.py` seeds 30 Cameroon subjects, Form 1–6 classes, and 3 academic terms. It is idempotent and scopes to the active school; call with `--auto` to skip the prompt.
- `core/management/commands/import_xlsx_defaults.py` imports the official Cameroon GCE subjects and first-cycle competencies from `Subjects and comptencies.xlsx`. Replicates each competency for form_level 1–5 (all first-cycle forms share the same competencies per term). Idempotent; use `--subjects-only` or `--competencies-only` to run selectively.
- Static assets must be fully local — **never introduce CDN URLs in templates** (a test enforces this). Vendor JS is already bundled at `static/vendor/alpinejs/` and `static/vendor/htmx/`.
- All templates must work without internet access (no external fonts/CSS).
- License keys are generated via `generate_license`; activation wizard lives in `core/views/auth_views.py` (3 steps: key → school → admin).
- Backups go to `backups/` via `core/utils/backup.py`; `backup.bat` and Windows Task Scheduler both supported.
- NSSM service name: `SchoolManagementSystem`, runs `manage.py runserver 0.0.0.0:8000`.
- Offline PDFs require WeasyPrint + GTK; see `DEPLOYMENT.md` for Windows install steps.

## Key Commands
```bash
# Setup
.venv\Scripts\pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser

# Development
python manage.py runserver 0.0.0.0:8000

# Testing
pytest
pytest --cov=core --cov-report=html

# Lint & Format
ruff check .
black .

# Deployment
python manage.py seed_default_config --auto
python manage.py import_xlsx_defaults --auto
python manage.py generate_license "School Name" --days 365 --max-students 500
python manage.py create_backup --type full --notes "manual"
python manage.py render_report --report=report_card --student=<id>

# Generate reports (for debugging — need WeasyPrint system libs)
python manage.py render_report --report=annual --student=<id> --year-start=2025 --year-end=2026

# Preview report as HTML in browser
# Visit /reports/term/<student_id>/<term_id>/preview/

# Demo/test data (deterministic, idempotent — safe to re-run)
python manage.py seed_demo_students_marks
python manage.py seed_demo_students_marks --form1 35 --seed 20260814
python manage.py seed_demo_forms
```

The `seed_demo_students_marks` command creates 35 Form 1 students (North West
Cameroon names + fake personal info, only the shortfall), enrolls every F1-F5
student in all 3 terms of the current year, generates 1-3 randomized
competency scores (3-19) per subject per student for the classes' selected
subjects, then recomputes subject averages, term results and ranks. Re-running
regenerates the same scores (fixed seed) and recomputes.

The `seed_demo_forms` command builds the demo structure first if missing:
Form 1-5 classes, three 2026/2027 terms (First Term current), the Form 1-5
subject scheme with coefficients in display order (F1/F2 junior set; F3 adds
ECO between HIS and BIO; F4/F5 senior set with HBI and COM), 11 teachers
(sample signature files attached where available) with subject-pair
assignments across classes and one class master per class, and 21-50 students
per form (NW/SW Cameroon names, full registration details) enrolled in the
current term. Run it before `seed_demo_students_marks` on a fresh database.

# School Management System

A web-based school management system for secondary schools in Cameroon. Designed to run **offline** on a local laptop/server with WiFi access.

## Features

- **School Configuration** — Custom letterhead (EN/FR), logo, seal, classes, streams, terms
- **Student Management** — Registration (single & bulk .xlsx/.csv import), photo capture, unique 9-digit ID
- **Teacher Management** — Multi-class/subject assignment, signatures, contact info
- **CBA Academics** — Subjects with coefficients, competencies (1–5 per subject), scores on 20, auto-totals
- **Discipline & Attendance** — Daily register, absences, lateness, punishments, conduct thresholds
- **Teacher Assiduity** — Period tracking, work coverage, PTA salary calculation
- **Finance** — State & PTA separation, customizable dues & rubric heads, expenditure tracking
- **Reporting** — Report cards, mark sheets, student IDs, results summaries, class council reports, PTA financial reports
- **Role-Based Access** — Superuser, Admin, Bursar, Class Master, Teacher + audit log
- **Multi-School** — Product key licensing, isolated school data

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+ / Django 5.x |
| API | Django REST Framework |
| Database | SQLite (local) |
| PDF Reports | WeasyPrint |
| Frontend | Django Templates + Bootstrap 5 |
| Mobile | Responsive web (PWA-ready) |

## Quick Start

```bash
# Clone and enter project
git clone <repo-url>
cd school-management-system

# Setup virtual environment
uv venv
uv pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start server (accessible on local network)
python manage.py runserver 0.0.0.0:8000
```

Access the app at `http://localhost:8000` or from other devices on the same network via `http://<laptop-ip>:8000`.

## Deployment (School Laptop)

1. Install Python 3.11+ on the school laptop
2. Copy the project folder
3. Run the setup script or use NSSM to register Django as a Windows service
4. Configure the laptop as a WiFi hotspot
5. Teachers connect and access via browser

## Project Structure

```
school-management-system/
├── core/                    # Main Django app
│   ├── models/              # Database models
│   │   ├── school.py        # School config, classes, terms
│   │   ├── student.py       # Student records
│   │   ├── teacher.py       # Teacher profiles
│   │   ├── academics.py     # Subjects, competencies, scores
│   │   ├── discipline.py    # Attendance, conduct
│   │   ├── finance.py       # Income, expenditure
│   │   └── auth.py          # User roles, audit log
│   ├── views/               # View logic
│   ├── templates/           # HTML templates
│   │   └── reports/         # PDF report templates
│   ├── static/              # CSS, JS, images
│   ├── utils/               # Helpers (PDF, import, export)
│   └── admin.py             # Django Admin config
├── tests/                   # Test suite
├── config/                  # Django project settings
├── requirements.txt         # Python dependencies
├── PLAN.md                  # Full build plan
├── SKILLS.md                # Required knowledge
├── AGENTS.md                # OpenCode agent config
└── README.md                # This file
```

## License & Distribution

This system is designed for multi-school deployment with product key activation. Contact the developer for licensing.

---

*Built for secondary schools in Cameroon's rural areas.*

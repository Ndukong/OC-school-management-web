# Deployment Guide — OC School Management System

## Quick Start (5 minutes)

1. **Copy this folder** to the school laptop
2. **Double-click `setup.bat`** — installs everything automatically
   ![Setup running](screenshots/01-setup-run.png)
3. **Double-click `start_server.bat`** — starts the server
4. **Open `http://127.0.0.1:8000`** in Chrome/Edge
5. Follow the 3-step wizard: activate → configure school → create admin
   ![Activation wizard](screenshots/02-wizard-step1.png)
   ![School profile](screenshots/03-wizard-step2.png)
   ![Admin account](screenshots/04-wizard-step3.png)

---

## Guide Screenshots

Screenshots referenced throughout this guide live in the **`screenshots/`** folder.
Capture them during a real install so a non-technical administrator can follow along
visually. Recommended capture order:

| # | File | What to capture |
|---|------|-----------------|
| 1 | `01-setup-run.png` | The console window while `setup.bat` runs (progress lines) |
| 2 | `02-wizard-step1.png` | Activation wizard — product key entry |
| 3 | `03-wizard-step2.png` | School profile form |
| 4 | `04-wizard-step3.png` | Admin account creation form |
| 5 | `05-login.png` | Login page |
| 6 | `06-dashboard.png` | Admin dashboard after login |
| 7 | `07-seed-config.png` | "Seed Default Config" result message |
| 8 | `08-hotspot.png` | Hotspot console output (network name/password) |
| 9 | `09-mark-entry.png` | Mark entry grid with scores |
| 10 | `10-reports-hub.png` | Reports hub (term report, mark sheet, ID cards) |
| 11 | `11-report-preview.png` | A rendered report (HTML preview) |
| 12 | `12-backup.png` | Backup & Restore page after a successful backup |

Capture tips:
- Use **Windows + Shift + S** (snipping tool) — saves directly to `screenshots/`.
- Blur or crop any real student names/faces if publishing the guide.
- After capturing, reference each file with `![alt](screenshots/01-setup-run.png)`.

---

## Detailed Installation

### Prerequisites

- **Windows 10/11** laptop with WiFi
- **Python 3.10+** — Download from [python.org](https://python.org)
  - ⚠️ Check "Add Python to PATH" during install
- **No internet required** after initial setup — everything runs offline

### Step 1: Run `setup.bat`

```
Right-click setup.bat → Run as Administrator
```

This will:
- Create a Python virtual environment (`.venv/`)
- Install Django, WeasyPrint, openpyxl, and all dependencies
- Run database migrations
- Seed 30 Cameroon subjects and Form 1–6 classes
- Collect static files (CSS, JS) into `staticfiles/`

### Step 2: Start the Server

```
Double-click start_server.bat
```

A console window opens with the server running. Keep this open.

Open **http://127.0.0.1:8000** in Chrome, Edge, or Firefox.

### Step 3: First-Time Setup Wizard

**Step 1 — Activate License**
- Enter your product key (format: `OC-xxxxxxxx-xxxxxxxxxx`)
- Click "Activate"

**Step 2 — Configure School**
- Enter school name (English + French)
- Enter region, division, phone
- Upload school logo (optional)
- Click "Save"

**Step 3 — Create Admin**
- Choose username and password (min 6 characters)
- Click "Create Account"

You're now logged in as administrator.

### Step 4: Seed Default Configuration

From the Settings page, click **"Seed Default Config"** or run:

```bash
python manage.py seed_default_config
```

This creates:
- 30 Cameroon subjects (English, French, Math, Physics, etc.)
- 7 classes (Form 1 through Upper Sixth)
- 3 academic terms for 2025/2026

---

## WiFi Sharing (Phones Connect to Laptop)

### Option A: WiFi Hotspot (Recommended)

1. Double-click `wifi_hotspot.bat` (run as Administrator)
2. Phone connects to **"SchoolManager"** WiFi, password: `school123`
3. Open browser on phone → `http://192.168.137.1:8000`

### Option B: Direct WiFi Router

If the school has a WiFi router:
1. Connect the laptop to the school WiFi network
2. Find the laptop's IP address: open CMD → type `ipconfig`
3. On phones, connect to school WiFi, browse to `http://[laptop-ip]:8000`

### Option C: LAN Cable

1. Connect laptop to router with Ethernet cable
2. Phones connect to the router's WiFi
3. Browse to `http://[laptop-ip]:8000`

---

## WeasyPrint & GTK Installation

WeasyPrint is needed for **PDF report generation** (report cards, mark sheets, ID cards).

### If PDFs Don't Work

The system works without WeasyPrint — only PDF export is affected. To enable PDFs:

1. Download WeasyPrint Windows bundle from:
   `https://github.com/Kozea/WeasyPrint/releases`
   
2. Or install via pip (requires GTK):
   ```
   .venv\Scripts\pip install weasyprint
   ```

3. GTK runtime (bundled with Windows installer or download separately):
   `https://github.com/niccokunzmann/Win32-GTK/releases`
   
4. Ensure `gtk` folder is in your PATH

### Verify WeasyPrint

```bash
python -c "import weasyprint; weasyprint.HTML(string='<p>OK</p>').write_pdf(); print('WeasyPrint working')"
```

If it prints "WeasyPrint working", PDFs are ready.

---

## Backups

### Manual Backup

```bash
Double-click backup.bat
```

Or from the admin dashboard: **Settings → Backup & Restore → Create Backup**

### Automatic Daily Backups

**Option A: Windows Task Scheduler**

1. Double-click `nssm_service.bat` (or open Task Scheduler manually)
2. Create a daily task running `python manage.py create_backup --notes "Daily auto-backup"`

**Option B: Scheduled batch file**

```
schtasks /create /tn "SchoolBackup" /tr "C:\path\to\backup.bat" /sc daily /st 02:00
```

### Restore from Backup

1. Open admin dashboard
2. Go to **Settings → Backup & Restore**
3. Click "Restore" next to the backup you want
4. Confirm — the database will be replaced with the backup

---

## Running as a Windows Service (Unattended)

For a laptop that stays on 24/7 without anyone logged in:

### Install NSSM

1. Download NSSM from https://nssm.cc/download
2. Extract `nssm.exe` to the project folder

### Install the Service

```bash
# Right-click → Run as Administrator
nssm_service.bat
# Select option 1: Install
```

The server now starts automatically on boot at `http://127.0.0.1:8000`.

### Manage the Service

```bash
nssm_service.bat
# Option 3: Start
# Option 4: Stop
# Option 5: Status
```

---

## Subject Configuration (Cameroon GCE System)

### First Cycle (Form 1–5)

| Subject | Code |
|---------|------|
| English Language | ENL |
| French Language | FRE |
| Mathematics | MAT |
| Physics | PHY |
| Chemistry | CHM |
| Biology | BIO |
| History | HIS |
| Geography | GEO |
| Computer Science | CMP |
| Economics | ECN |
| Food & Nutrition | FND |
| Civic Education | CVE |
| Art & Design | ATD |
| Physical Education | PED |
| Entrepreneurship | ENT |

### Second Cycle (Lower/Upper Sixth)

Additional subjects: Philosophy, Logic, Literature, Religious Studies, Further Mathematics, German, Arabic, Chinese, Technical Drawing.

### How to Add Subjects

1. Go to **Settings → Subjects**
2. Enter subject name and 3-letter code
3. Click "Add Subject"
4. Then go to **Settings → Classes & Streams**
5. Click "Configure" next to each class
6. Add subjects with their coefficients

---

## Coefficients by Class

Default coefficients for Cameroon GCE:

| Subject | Form 1–4 | Form 5 | Sixth Form |
|---------|----------|--------|------------|
| English | 3 | 3 | 4 |
| French | 3 | 3 | 4 |
| Mathematics | 4 | 4 | 6 |
| Physics | 3 | 3 | 4 |
| Chemistry | 3 | 3 | 4 |
| Biology | 3 | 3 | 4 |

Set these via **Settings → Subjects → Configure** for each class.

---

## Troubleshooting

### "Server won't start"
- Check Python is installed: open CMD, type `python --version`
- Check port 8000 is not in use: `netstat -ano | findstr :8000`
- Kill any existing server: `taskkill /f /im python.exe`

### "Phones can't connect"
- Ensure laptop firewall allows port 8000
- Try: `netsh advfirewall firewall add rule name="SchoolServer" dir=in action=allow protocol=tcp localport=8000`
- Verify hotspot is running: `netsh wlan show hostednetwork`

### "PDFs don't generate"
- Check WeasyPrint installation (see section above)
- Reports still work as HTML (just not PDF)

### "Slow performance"
- Close unused browser tabs
- The server is single-threaded for development
- For production use `python manage.py runserver --threads 4`

### "Need to reset everything"
```bash
python manage.py flush           # Clear all data
python manage.py seed_default_config  # Re-seed
```

---

## Folder Structure

```
OC-school-management-system/
├── .venv/                  Python virtual environment
├── backups/                Backup files (.zip)
├── config/                 Django project settings
├── core/                   Main application
│   ├── models/             Database models
│   ├── views/              Business logic
│   ├── utils/              Reports, grading, exports
│   ├── management/commands Management commands
│   └── templates/          HTML templates
├── media/                  Uploaded files (photos, logos)
├── static/                 Bundled vendor JS/CSS (offline)
├── templates/              Base HTML templates
├── db.sqlite3              Database file
├── manage.py               Django management script
├── setup.bat               First-time setup
├── start_server.bat        Start the server
├── backup.bat              Create a backup
├── wifi_hotspot.bat        WiFi hotspot setup
├── nssm_service.bat        Windows service installer
└── DEPLOYMENT.md           This file
```

---

## License

This is a licensed product. Each deployment requires a valid product key.
Contact your system administrator for keys.

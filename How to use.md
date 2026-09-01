# How to Use — School Management System (Offline / Hotspot Edition)

A plain-language guide for everyone who uses the system: the platform owner
(SuperUser), the school's Admin, the Bursar, Class Masters and Teachers.
Everything works over your school's own WiFi or hotspot — **no internet is
required** for day-to-day use.

---

## Contents

1. [What this system is](#1-what-this-system-is)
2. [Installing it for a school](#2-installing-it-for-a-school-superuser)
3. [Getting connected (hotspot & WiFi)](#3-getting-connected-hotspot--wifi)
4. [Accounts, roles and passwords](#4-accounts-roles-and-passwords)
5. [SuperUser guide](#5-superuser-guide-platform-owner)
6. [School Admin guide](#6-school-admin-guide)
7. [Bursar guide](#7-bursar-guide)
8. [Class Master guide](#8-class-master-guide)
9. [Teacher guide](#9-teacher-guide)
10. [The school year, step by step](#10-the-school-year-step-by-step)
11. [Reports hub reference](#11-reports-hub-reference)
12. [Printing student ID cards](#12-printing-student-id-cards)
13. [SMS alerts](#13-sms-alerts)
14. [Backups and restoring](#14-backups-and-restoring)
15. [Troubleshooting & FAQ](#15-troubleshooting--faq)

---

## 1. What this system is

A web app that runs **on one laptop at the school**. The laptop becomes the
server; every phone, tablet or computer connected to the school's WiFi or
hotspot opens the system in a browser. No internet needed after installation.

It manages: students, teachers, classes, the competency-based mark system
(CBA, scores on 20), term and annual report cards, mark sheets, results
summaries, class council reports, attendance, discipline, PTA/finance
records, student ID cards and SMS alerts to parents.

**Two ways to run it:**

| Mode | Where it lives | Who reaches it |
|---|---|---|
| **Offline / hotspot** (this guide) | One laptop at the school | Everyone on the school WiFi/hotspot |
| **Hosted** (Railway or your own server) | The internet | Anyone with the web address, from anywhere |

The screens and steps are identical in both modes — only the address you
type in the browser differs. Hosting is covered in `DEPLOYMENT.md`.

---

## 2. Installing it for a school (SuperUser)

One-time setup, about 10 minutes, on the laptop that will be the server.

1. Copy the project folder to the laptop (e.g. `C:\SchoolMS`).
2. Double-click **`setup.bat`**. This installs everything (Python packages,
   the database, the government subject list and standard terms) and
   collects the print/PDF support files.
3. When it finishes, double-click **`start_server.bat`**. The system is now
   live on that laptop at `http://127.0.0.1:8000`.
4. Create the **SuperUser** (that's you — the technician/platform owner):
   open Command Prompt in the project folder and run
   `python manage.py createsuperuser`, then follow the prompts. Keep this
   password safe; it is separate from all school accounts.
5. On the laptop's browser, open `http://127.0.0.1:8000/activate/` and walk
   through the **activation wizard**:
   - **Step 1 — License:** paste the product key you generated for this
     school (see [5.2](#52-generating-a-product-key-for-a-school)). The key
     controls the expiry date and the maximum number of students.
   - **Step 2 — School profile:** school name, region, division, phone,
     motto, logo and seal. Saving this automatically creates Form 1–5
     classes, the government subject list and the three terms of the
     current academic year.
   - **Step 3 — Admin account:** create the username and password the
     school's Admin (e.g. the principal) will use every day.

Hand the Admin their username and password — setup is done. Everything in
section 6 onwards is now theirs to run.

> **Renewing an expired license:** when a school's license runs out, staff
> are pointed back to the activation page. Generate a fresh product key and
> enter it at Step 1 — school data, students and marks are never touched.

---

## 3. Getting connected (hotspot & WiFi)

**On the server laptop:** double-click **`start_server.bat`** and leave the
window open. Closing it stops the system.

**To find the address other devices will use:**

1. On the server laptop, press `Win + R`, type `cmd`, press Enter, then run
   `ipconfig`.
2. Look for **IPv4 Address** under the WiFi adapter (e.g. `192.168.43.14`).
3. Every other device opens: `http://192.168.43.14:8000`
   (use your own number — it can change between days, so re-check after
   changing networks).

**Sharing the connection:** run **`wifi_hotspot.bat`** to start the laptop's
hotspot, then connect phones to it as usual. Any normal WiFi router works
too — just keep all devices on the same network as the laptop.

**Tip:** bookmark the address on each phone's browser ("Add to Home
Screen") so staff can find it every morning.

**Running without anyone logged in:** for schools that want the system on
all day unattended, `nssm_service.bat` installs it as a Windows service that
starts automatically with the laptop. Pair it with `backup.bat` in Task
Scheduler for automatic daily backups (see [5.6](#56-backups-restore-and-data-transfer)).

---

## 4. Accounts, roles and passwords

Everyone signs in at the **Login** page with a username and password
(minimum 6 characters). After login, each role lands on its own dashboard
and its own sidebar.

| Role | Who it is for | Sees |
|---|---|---|
| **SuperUser** | You — the technician/platform owner | Everything, including backups, product keys, data transfer and the technical admin site |
| **Admin** | Principal / vice-principal / bursar-office staff | Everything in their school: settings, students, teachers, marks, reports, discipline, SMS, finance, audit trail |
| **Bursar** | The finance officer | The Finance hub and student fee lookups only |
| **Class Master** | A teacher who leads one class | Their class dashboard, attendance for **their class only**, discipline, preview of their class mark sheet, their own mark entry |
| **Teacher** | Subject teachers | Mark entry **only for the subjects assigned to them**, plus view-only mark sheets for the classes they teach |

**Good to know:**

- You can have **any number of Admins** — e.g. one account for the
  technician who configured the school and one for the principal.
- Hovering the mouse over any button shows a short hint of what it does.
- Marks entered by a teacher save instantly; averages, grades, subject
  ranks and the class rank are computed by the system.
- **Forgotten password?** Passwords are not self-resettable. Ask your
  SuperUser, who will set a new one for you from the technical admin site.

---

## 5. SuperUser guide (platform owner)

You own the platform: you install systems for schools, issue their product
keys, and stay in the background afterwards. You sign in with the
SuperUser account created during installation.

### 5.1 The activation wizard (onboarding a school)

Covered in [section 2](#2-installing-it-for-a-school-superuser). One wizard
per school. You can onboard as many schools as you like on separate laptops
— each activation creates its own isolated school.

### 5.2 Generating a product key for a school

Every school needs a key before the wizard will run.

1. Log in as SuperUser → sidebar → **Settings → Generate License**.
2. Fill in: **School Name**, **Max Students** (e.g. 500), **Max Devices**,
   **Validity (days)** (e.g. 365 for one school year).
3. Click Generate and copy the key — it looks like
   `OC-ab12cd34-eyJzY2h...`.
4. Send the key to the school (SMS, WhatsApp or print it). Keys are tied to
   your secret signing key — they cannot be forged or reused between
   schools.

Check **Settings → License** any time to see the school's expiry, student
count against the quota, and device count. **Settings → Offline License
Check** does the same without the internet.

### 5.3 Backups, restore and data transfer

- **Settings → Backup & Restore:** create a backup (database + media in one
  ZIP, saved to the laptop's `backups/` folder), download it, or restore
  from a previous one. Set `backup.bat` up in Task Scheduler for a daily
  automatic backup.
- **Settings → Data Export / Import:** exports the whole school as a single
  data file and imports it into another deployment — the supported way to
  move a school between laptops, or from offline to a hosted server.

**Rule of thumb:** make a backup at least once a week, and always after
end-of-term marks are final. Keep one copy off the laptop (USB stick or
cloud drive).

### 5.4 The technical admin site

`/admin/` (link in the browser address bar, or add `/admin/` to your
address) is the raw Django admin — only SuperUsers can enter. Use it for
occasional power tasks: resetting a password, deleting a user, fixing
data. School staff can never reach it.

### 5.5 Audit trail

**Settings → Audit Trail** shows the latest 200 events: who logged in, who
logged out, failed login attempts, and every tracked change (with the time
and IP address). Use it to answer "who changed this?" without doubt.

### 5.6 Backups, restore and data transfer

Covered in [5.3](#53-backups-restore-and-data-transfer) — the essentials:
`Backup & Restore` for ZIP backups, `Data Export / Import` for moving a
school between machines, `backup.bat` + Task Scheduler for automation.

---

## 6. School Admin guide

You run the school inside the system. Your sidebar is the map: everything
is under **Settings**, plus day-to-day pages for students, teachers, marks,
reports, attendance, discipline and finance.

### 6.1 First-week setup checklist

Do these once, in order (the **Settings** page shows the same list as a
checklist):

1. **School Profile** — name, matricule, phone, region/division, the three
   letterhead lines (English and French), logo, seal and **periods per day**
   (6–10, default 8).
2. **Academic Terms** — create the three terms of the school year and mark
   the current one. Saving a term as current automatically clears the flag
   from older terms.
3. **Classes & Streams** — the wizard created Form 1–5 already; adjust
   names/streams, set promotion and dismissal marks.
4. **Subjects** — the government catalogue is pre-loaded; add or rename as
   needed.
5. **Class Subjects & Coefficients** — for each class, pick its subjects
   and set each coefficient (they control the weighted averages).
6. **Competencies** — pre-loaded per subject/term/form level from the
   government list; edit freely, and add up to 4 per subject per term.
7. **Teachers** — create each teacher (name, code, phone, email, signature
   image for report cards).
8. **Users & Teacher Links** — create the login accounts (admin, bursar,
   class masters, teachers) and link teacher accounts to their Teacher
   record. This is also where you create additional admins.
9. **PTA Configuration** — rubric heads and sub-heads, per-class PTA dues,
   and fee types (the Bursar depends on these).
10. **Conduct Thresholds** — absence/hours levels that drive the class
    council recommendations.

The demo subjects, competencies and class-subject assignments created
during onboarding match the standard government layout — adjust
coefficients per class and you are ready to enroll students.

### 6.2 Students

- **Register** one student at a time (**Students → + Register**), or bulk
  **Import Students** from the government Excel list (or your own sheet —
  the importer matches columns automatically).
- Every student needs: names, sex, the **9-digit state ID** (must be
  unique), date/place of birth, guardian name and contact, region,
  division and sub-division of origin. A photo can be added now or later.
- **Students list** pages let you search every field, filter by class and
  sex, and export the current view to Excel.
- Click a student's name for the full profile: enrollments, subject
  averages, term results and fee status.

### 6.3 Teachers, users and permissions

- Create teachers under **Teachers**, then create their logins under
  **Settings → Users & Teacher Links** and link each login to its Teacher
  record — the link is what gives a teacher their mark-entry rights.
- Assign subjects on the teacher's page (**Assignments**): choose the
  class and subject; tick **Class Master** for the teacher who leads that
  class.
- Give the **Bursar** account the role "bursar" (no teacher link needed
  unless they also teach). Class masters get the "class master" role;
  everyone else "teacher".
- Deactivating a user (uncheck Active) blocks their login without
  deleting anything.

### 6.4 Marks and results

1. Teachers enter competency scores themselves (see the Teacher guide) —
   you don't need to, but you can: **Mark Entry** lets an admin pick any
   class and subject.
2. When a deadline passes, open **Compute Results**, choose a class and
   term, and run it. This computes every subject average, the weighted
   term average, class ranks, grades, remarks and promotion decisions.
3. The **Reports hub** then has everything ready: report cards (single or
   whole-class batch, term and annual), mark sheets (preview, PDF,
   Excel), results summaries, class council reports and ID cards.

### 6.5 Attendance, discipline and conduct

- Admins can load any class in the **Attendance** module; class masters
  see only theirs.
- **Discipline summary** computes each student's absence/punishment totals
  per term; record individual punishments on the same page.
- **Conduct thresholds** set the hours/lateness levels behind the class
  council's recommendations.

### 6.6 SMS and notifications

- **Settings → SMS** holds the provider settings and message history;
  queued messages can be cancelled there.
- The system auto-sends parent alerts at the right moments: absence
  warnings when absences pile up, fee reminders when a term's balance is
  outstanding, and a "report ready" notice when results are computed.
- Staff also get **in-app notifications** from the bell icon (e.g. new
  term notices).

### 6.7 Audit trail

**Settings → Audit Trail** lists the latest logins, failed logins and
every tracked change — with the user, time and IP address. Check it any
time records "mysteriously" change, and review it with the Bursar each
term for the finance records.

### 6.8 Finance

The **Finance** dashboard and PTA pages are shared with the Bursar —
see the [Bursar guide](#7-bursar-guide) for what exists today.

---

## 7. Bursar guide

Your world is the **Finance** hub. Everything recorded there is
**immutable** — entries cannot be edited or deleted after saving, which is
what makes the books trustworthy. Double-check before you save.

### 7.1 What you see

- **Finance dashboard:** income vs expenditure for the term (chart and
  totals), PTA collection per class (expected vs collected vs
  outstanding), quick forms to record money in and out, and recent
  transactions.
- **Student fee status:** search any student to see payments received and
  the outstanding balance for the term.

### 7.2 Recording income (fees received)

1. Collect the fee and issue your receipt.
2. Finance → **Record Income**: choose the **fee type** (PTA or State —
   this classification drives the PTA reports), the student, the amount,
   date and receipt number. Save.
3. The dashboard totals and the PTA-per-class table update instantly.

> Amounts must match your receipt book exactly. There is no editing after
> saving — mistakes require a counter-entry, which keeps the audit trail
> honest.

### 7.3 Recording expenditure

Same idea from the **Record Expenditure** form: pick the PTA rubric
sub-head or state category, amount, date and a clear description. Save.
Expenditures are also permanent.

### 7.4 Reports and exports

- **PTA Financial Report** — preview in the browser, download as PDF for
  the PTA meeting, or export to Excel for your own working.
- **Export Excel** — the term's income/expenditure working.

> The Admin must first set up **PTA dues per class** and **fee types**
> under Settings → PTA Configuration — if a class is missing from your
> reports, ask the admin to add its dues.

### 7.5 If you also teach

If a teacher assignment is linked to your account, your dashboard also
includes mark entry for those subjects — same flow as the Teacher guide
below.

---

## 8. Class Master guide

You are the-class-its-eyes-and-ears: attendance, discipline and a view of
your class's marks.

### 8.1 Your dashboard

The landing page shows each class you master, this week's attendance
percentage, and the students with pending discipline.

### 8.2 Taking attendance

1. Sidebar → **Attendance**.
2. Choose your **class** and the **date**, and load the register.
3. One column per period of the day. **Click a cell** to cycle the state:
   Present → Late → Absent → Permission → clear. The cell saves itself
   the moment you click, and the summary bar updates.
4. In a hurry? **Mark All Present** fills every cell as Present in one
   go — then just click the few who are late or absent.
5. Picked the wrong day? Change the date at the top and load again.

Attendance is saved per period — that history feeds the discipline
summary and the SMS absence alerts to guardians.

### 8.3 Discipline

- **Discipline summary** computes each student's totals for the term and
  lets you record a punishment (with the conduct levels your admin
  configured).
- These totals flow into the class council report and the report card's
  discipline box.

### 8.4 Your class's marks (transparency)

- **Reports → Mark Sheets → Preview** shows your class's full mark sheet
  for any term — including every teacher's entries — so you can verify
  results before the council meets.
- Preview is read-only: downloads stay with the admin.

---

## 9. Teacher guide

Everything you need lives on your dashboard: one card per class-subject
pair you teach.

### 9.1 Entering marks (competencies)

Marks in Cameroon follow the competency-based approach: for each subject,
the government defines 2–4 competencies per term, and each is scored **on
20**.

1. Dashboard → **Enter Marks** on the card for your class and subject.
2. The grid lists every enrolled student with one column per competency.
3. Click a cell, type the score (0–20), and move on — each cell saves
   itself as you leave it. Failing scores (below 10) turn red.
4. The subject **average /20** and **grade** are computed automatically;
   when the admin runs Compute Results, subject ranks and the class rank
   are added.
5. Scores can be corrected any time before results are finalized — reopen
   the same grid and change the cell.

**Tips:**

- You only see students actually enrolled in that class for the current
  term, and only the competencies defined for your subject.
- You can enter marks for the competencies you actually tested — you don't
  need a score in every column.
- Mark entry works from any device on the school network, so you can enter
  from a phone in the staff room.

### 9.2 Checking your marks weren't touched (transparency)

**Reports → Mark Sheets → Preview** for any class you teach shows the
final mark sheet exactly as the admin will print it — your entries, your
colleagues' entries, averages and ranks. If something looks wrong, raise
it with the admin *before* report cards go out.

### 9.3 What teachers don't see

Attendance (class masters handle it), finance, settings, and report card
downloads. If you also serve as a class master, see the Class Master
guide.

---

## 10. The school year, step by step

The intended rhythm of a term:

1. **Before the term starts (Admin):** create the new academic terms, mark
   the current one, adjust classes, check class-subject coefficients and
   competencies.
2. **Week 1:** enroll students (new + returning), hand out ID cards,
   record PTA dues for the term.
3. **Every school day (Class Master):** take attendance in a minute.
4. **Continuous assessment (Teachers):** enter competency scores as tests
   happen — don't wait for the deadline.
5. **After tests (Teachers):** finish the grid.
6. **End of term (Admin):** Compute Results for every class → preview mark
   sheets and report cards → batch-download report cards → class council
   reports → SMS "report ready" alerts go to guardians.
7. **Council & fees (Bursar + Master):** PTA financial report, fee
   follow-ups from the outstanding list.
8. **Next term:** create the term (or reuse), mark it current, repeat.

For the **annual report cards**, all three terms must have computed
results; the annual average is the weighted mean of the term averages and
drives the promotion decision (against each class's promotion mark).

---

## 11. Reports hub reference

One page, every document. Pick your filters, then Preview (opens in the
browser) or Download (file). Nothing here can be opened by the wrong role.

| Report | Inputs | Outputs |
|---|---|---|
| **Report Cards** | class + term + student (or "All" to batch) | HTML preview / PDF / whole-class batch |
| **Annual Report Cards** | class + year range + student | preview / PDF / batch |
| **Mark Sheets** | class + term | term: preview / PDF / Excel; annual: preview / PDF |
| **Student ID Cards** | 1–4 students | printable HTML booklet |
| **Results Summary** | term or year range | preview / PDF / Excel |
| **Class Council Report** | term or year range | preview / PDF (with withheld-result motifs) |
| **PTA Financial Report** | term | preview / PDF / Excel (admin & bursar) |
| **Attendance Export** | class + term | Excel |
| **Students Export** | current filters | Excel |

Batch jobs (a whole class at once) may take a minute for large classes —
the download starts when all PDFs are merged.

---

## 12. Printing student ID cards

1. **Reports → Student ID Cards**: select 1–4 students (fewer than 4 are
   repeated to fill the sheet), then **Preview** or **Download HTML**.
2. Open the downloaded file in a browser and print — the layout is A4
   **landscape**, two-sided: sheet 1 is the inside spread (details + photo,
   seal and principal's signature), sheet 2 is the front cover and the
   renewals page, already ordered for folding.
3. Enable background graphics in the print dialog, use A4 landscape at
   100% scale, cut along the dashed lines, and fold.
4. Page 3 shows the issue date and the **expiry date** — always the next
   10th of September, when the new school year begins.

---

## 13. SMS alerts

Configure your provider once under **Settings → SMS** (choose the provider
and enter its credentials). After that, the system sends guardian alerts
automatically at the right moments:

- **Absence alert** — when a student's absences cross the threshold.
- **Fee reminder** — when a term's balance is still outstanding.
- **Report ready** — when results are computed and report cards are out.

**Settings → SMS History** lists every message with its status, and queued
messages can be cancelled before they go out. Staff see in-app
notifications from the bell icon as well.

---

## 14. Backups and restoring

- **Offline deployment:** run `backup.bat` (or SuperUser → Settings →
  Backup & Restore → Create Backup). A dated ZIP with the database and all
  photos is saved to the laptop's `backups/` folder. Restore is one click
  from the same page — pick the backup, confirm, done.
- **Hosted deployment:** archives are uploaded to your object store
  automatically, plus Railway's own daily database backups.
- **Move a school** between laptops or to the cloud: Settings → Data
  Export / Import.

Do it weekly at minimum, and always before any software update.

---

## 15. Troubleshooting & FAQ

**A teacher forgot their password.**
The SuperUser resets it from the technical admin site (or creates a fresh
login). Passwords have no self-reset by design.

**The attendance register is empty.**
Check that the students are enrolled for the **current** term (Students →
the student's enrollments), and that a current term exists — only students
enrolled in the current term appear.

**A subject is missing from mark entry.**
It must be assigned to that teacher for that class (Teachers →
Assignments), and the class must have the subject with a coefficient
(Settings → Class Subjects).

**Marks entered but averages are zero.**
Run **Compute Results** (admin) — averages and ranks are computed there.

**A phone can't open the page.**
Confirm it's on the same WiFi/hotspot as the server laptop, and type the
full address including `http://` and the port (`:8000`). Re-check the
laptop's IP — it can change.

**The report card PDF looks cut off.**
Print at A4 portrait, 100% scale, with background graphics enabled.

**The license expired.**
The system keeps all data but points staff to re-activation. Ask your
SuperUser for a renewal key and enter it at the activation page.

**Hover over any button** — every button in the system explains itself.

---

## Glossary

| Term | Meaning |
|---|---|
| **CBA** | Competency-Based Approach — scoring students on defined competencies per subject, each on 20 |
| **Competency** | A skill the government requires a subject to test each term |
| **Coefficient** | A subject's weight in the weighted average |
| **AV/20, AVxCoef** | Average on 20, and that average × the coefficient |
| **Term rank** | A student's overall position in class for the term |
| **Subject rank** | Position in one subject among everyone who took it |
| **Promotion mark** | Annual average (default 10/20) needed to move up |
| **Dismissal mark** | Annual average below which a student is dismissed |
| **CVWA / CWA / CA / CAA / CNA** | Council recommendation boxes on the report card |
| **Motif** | The note a council writes on a withheld result |
| **Product key** | The signed license the SuperUser issues to activate a school |

---

*School Management System v1.0 — offline/hotspot edition. Hosted edition:
same screens, served from the internet; see `DEPLOYMENT.md` for that setup.*

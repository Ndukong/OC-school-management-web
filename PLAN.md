# School Management System — Build Plan

## Overview
A web-based school management system for secondary schools in rural Cameroon. Designed to run offline on a local laptop/server with WiFi access for teachers.

**Target Users:** Principals/VPs, Bursars, Class Masters, Teachers (via phone/laptop)
**Deployment:** Local server (no internet required), accessed via browser over school WiFi
**Tech Stack:** Django (Python) + SQLite + WeasyPrint (PDF) + Django REST Framework (mobile API)

---

## System Requirements (from info.docx)

### 1. School Configuration
- Customizable letterhead (English/French dual textboxes, logo centered, matricule + phone below)
- Classes & streams (Form 1–5, Lower/Upper Sixth, with sections like Form 1A, 1B, etc.)
- Three-term system (Term 1, 2, 3) — promotion based on annual average
- School seal for documents
- Only country and motto are universal; everything else is per-school

### 2. Academics (CBA System)
- Subjects with coefficients (weightings)
- 1–5 competencies per subject per term (minimum 2 tested per term)
- Scores recorded on 20 marks; fail marks highlighted red
- Customizable competencies (government may change them)
- ~25 standard subjects with standard competencies (to be provided via .xlsx)

### 3. Student Management
- Fields: first name, other names, sex, unique 9-digit state ID, repeater status, DOB, place of birth, guardian info, division/region of origin, father's name, mother's name, contact
- Photo capture (file upload or webcam)
- Single registration + bulk import from .xlsx/.csv

### 4. Teacher Management
- Multi-class, multi-subject assignment
- Contact info (email, phone)
- Signature capture for report cards

### 5. Discipline & Attendance
- Daily attendance per class
- Justified/unjustified absences tracking
- Lateness (absent from first period)
- Punishment hours
- Threshold-based conduct comments (customizable)

### 6. Teacher Assiduity
- Periods assigned vs taught
- Work coverage (topics taught)
- PTA salary calculation for PTA-employed teachers
- Incentive calculation for state-employed teachers

### 7. School Finances
- **State finances** vs **PTA finances** (separate tracking)
- Income types: registration fees, PTA dues, exam fees, cooperative/canteen sales, etc.
- Expenditure tracking
- PTA rubric heads (editable): Assistance to pedagogy, PTA office running, clean school program, digitalization of education, inclusive education, PTA projects, miscellaneous
- PTA dues fixed by class (e.g., 15,000 FCFA Form 1, 20,000 FCFA Lower Sixth)

### 8. Reports (most critical feature)
- **Student ID Cards** — 4 per A4 page, foldable (4 pages per ID)
- **Mark Sheets** — landscape, school letterhead, school seal
- **Report Cards** — portrait, exact state-prescribed layout
- **Results Summary** — enrollment, sat, passed, pass %, average, top/bottom 3 per class
- **Class Council Reports** — landscape, term & annual versions
- **PTA Financial Reports** — detailed & summarized by rubric head, with signatures and seal
- Batch print/download for entire class or individual student

### 9. Access Control (5 Levels)
| Role | Access |
|------|--------|
| **Superuser** (developer) | Full access to everything |
| **Administrator** (Principal/VP) | Almost everything except system transfer/licensing |
| **Bursar** | Finance section only |
| **Class Master** | Their class only |
| **Teacher** | Their subjects only (fill marks, view-only mark sheets, no report cards) |

### 10. Audit System
- Log who logged in and what they edited
- Mandatory for finance accountability

### 11. Multi-School / Licensing
- Product key activation system
- Each school isolated (multi-tenant)
- Superuser can transfer/license to new schools

---

## Build Phases

### Phase 0 — Foundation Setup
- [ ] Django project scaffolding
- [ ] SQLite configuration
- [ ] Django Admin customization
- [ ] Database schema design (all models before any UI)
- [ ] Multi-tenancy layer (school_id scoping)
- [ ] Authentication & role-based permissions
- [ ] Audit log middleware
- [ ] Product key/licensing model

### Phase 1 — School Configuration Module
- [ ] School profile (letterhead EN/FR, logo upload, seal upload, matricule, phone)
- [ ] Class & stream management (Form 1–5, Lower/Upper Sixth, custom sections)
- [ ] Term management (Term 1, 2, 3)
- [ ] Subject management (with coefficient)
- [ ] Competency management (per subject per term, editable)

### Phase 2 — Student Module
- [ ] Student model with all required fields
- [ ] Single registration form
- [ ] Photo capture (file + webcam)
- [ ] Bulk import from .xlsx/.csv with validation preview
- [ ] Student listing & search

### Phase 3 — Teacher Module
- [ ] Teacher profile (name, email, phone, signature)
- [ ] Class-subject assignment
- [ ] Teacher dashboard (my classes, my subjects)

### Phase 4 — Mark Entry Engine
- [ ] Competency score entry (per student per subject per term)
- [ ] Automatic total calculation with coefficient weighting
- [ ] Fail mark detection (red highlighting)
- [ ] Mobile-responsive API for phone entry
- [ ] Validation rules (at least 2 competencies tested)

### Phase 5 — Report Card Engine (MOST CRITICAL)
- [ ] Template-based PDF generation with exact positioning
- [ ] School letterhead rendering
- [ ] Student info, subject table, scores, totals, ranks
- [ ] Conduct/discipline section
- [ ] Promotion decision logic
- [ ] Annual report card (3-term average)
- [ ] Batch download for entire class
- [ ] Individual student download

### Phase 6 — Other Reports
- [ ] Student ID card (4 per A4, foldable)
- [ ] Mark sheet (landscape, with seal)
- [ ] Results summary (per class, per term/annual)
- [ ] Class council report (term + annual)
- [ ] PTA financial report (detailed + summarized by rubric)

### Phase 7 — Discipline & Attendance
- [ ] Daily attendance register
- [ ] Absence tracking (justified/unjustified)
- [ ] Lateness tracking
- [ ] Punishment hours
- [ ] Conduct threshold configuration
- [ ] Discipline section on report card

### Phase 8 — Teacher Assiduity
- [ ] Period allocation per teacher
- [ ] Hours taught entry (by VP)
- [ ] Work coverage tracking
- [ ] PTA salary calculation
- [ ] Incentive calculation

### Phase 9 — Finance Module
- [ ] Income types (customizable)
- [ ] Expenditure tracking
- [ ] State vs PTA separation
- [ ] PTA rubric heads (editable)
- [ ] PTA dues configuration per class
- [ ] Transaction audit trail

### Phase 10 — Deployment & Licensing
- [ ] Offline-first design (service worker, local storage)
- [ ] Product key generation & validation
- [ ] School data export/import for backup
- [ ] One-click installer or setup script

---

## Error Prevention Strategy

| Risk | Mitigation |
|------|-----------|
| Report card layout mismatch | Template-based PDF with exact coordinates; preview mode before final |
| CBA grading logic errors | Unit tests for every scoring scenario |
| Multi-school data leak | Global `school_id` query filter on every model |
| Bulk import corruption | Preview validation — show errors before committing |
| Finance discrepancies | Double-entry bookkeeping; immutable transaction log |
| Offline data loss | Local database with sync mechanism |
| Permission bypass | Decorator-based permission checks on every view/API endpoint |
| Lost data (rural schools) | Automated daily backup to USB/external drive option |

---

## Files Needed to Begin (from you)

1. **Sample report card** (PDF or DOCX with bracketed fields like `[student_name]`)
2. **Sample student ID card** layout (4 per A4)
3. **Sample mark sheet** (landscape)
4. **Sample class council report** (term + annual)
5. **Sample PTA financial report**
6. **Subjects & competencies .xlsx** (25 subjects, 3 terms)
7. **Custom letterhead example** (optional, if description wasn't enough)

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404

from core.models import (
    AcademicTerm,
    AttendanceRecord,
    AttendanceRegister,
    ExpenditureRecord,
    IncomeRecord,
    SchoolClass,
    Student,
    StudentEnrollment,
    SubjectAverage,
    TermResult,
)
from core.utils.excel_exports import build_workbook, excel_response
from core.utils.finance import get_finance_totals
from core.utils.permissions import get_school_for_user, role_required


@login_required
@role_required("admin", "superuser")
def export_students_excel(request):
    school = get_school_for_user(request.user)
    if not school:
        from django.http import HttpResponse

        return HttpResponse("No school linked.", status=400)

    students = list(
        Student.objects.filter(school=school, is_active=True).order_by("first_name")
    )
    rows = []
    for s in students:
        enrollment = (
            s.enrollments.filter(academic_term__is_current=True)
            .select_related("school_class")
            .first()
        )
        rows.append(
            [
                s.unique_id,
                s.full_name,
                s.get_sex_display(),
                str(enrollment.school_class) if enrollment else "",
                s.date_of_birth,
                s.guardian_name,
                s.guardian_contact,
                "Active" if s.is_active else "Inactive",
            ]
        )

    wb = build_workbook(
        [
            {
                "title": "Students",
                "headers": [
                    "Student ID",
                    "Name",
                    "Sex",
                    "Class",
                    "Date of Birth",
                    "Guardian",
                    "Contact",
                    "Status",
                ],
                "rows": rows,
            }
        ]
    )
    return excel_response(wb, f"students_{school.matricule}.xlsx")


@login_required
@role_required("admin", "superuser")
def export_marks_excel(request, class_id: int, term_id: int):
    school = get_school_for_user(request.user)
    school_class = get_object_or_404(SchoolClass, pk=class_id, school=school)
    term = get_object_or_404(AcademicTerm, pk=term_id, school=school)

    enrollments = list(
        StudentEnrollment.objects.filter(
            school_class=school_class, academic_term=term
        ).select_related("student")
    )
    rows = []
    for e in enrollments:
        s = e.student
        averages = list(
            SubjectAverage.objects.filter(student=s, academic_term=term)
            .select_related("subject")
            .order_by("subject__sort_order")
        )
        result = TermResult.objects.filter(student=s, academic_term=term).first()
        subjects = [f"{a.subject.code}: {a.average} ({a.grade})" for a in averages]
        rows.append(
            [
                s.unique_id,
                s.full_name,
                s.get_sex_display(),
                "; ".join(subjects),
                result.average if result else "",
                result.grade if result else "",
                result.rank if result else "",
                "Promoted" if result and result.promoted else "",
            ]
        )

    wb = build_workbook(
        [
            {
                "title": "Marks",
                "headers": [
                    "Student ID",
                    "Name",
                    "Sex",
                    "Subject Averages",
                    "Overall Average",
                    "Grade",
                    "Rank",
                    "Promotion",
                ],
                "rows": rows,
            }
        ]
    )
    return excel_response(wb, f"marks_{school_class.code}_{term}.xlsx")


@login_required
@role_required("admin", "superuser")
def export_finance_excel(request, term_id: int):
    school = get_school_for_user(request.user)
    term = get_object_or_404(AcademicTerm, pk=term_id, school=school)

    income_rows = []
    for inc in IncomeRecord.objects.filter(
        school=school, academic_term=term
    ).select_related("fee_type"):
        income_rows.append(
            [
                inc.date_paid,
                inc.receipt_number or "",
                inc.fee_type.name if inc.fee_type else "",
                inc.fee_type.get_category_display() if inc.fee_type else "",
                inc.amount,
                inc.notes or "",
            ]
        )

    exp_rows = []
    for exp in ExpenditureRecord.objects.filter(school=school, academic_term=term):
        exp_rows.append(
            [
                exp.date,
                exp.get_category_display(),
                exp.rubric_sub_head.name if exp.rubric_sub_head else "",
                exp.description or "",
                exp.amount,
            ]
        )

    totals = get_finance_totals(school, term)
    wb = build_workbook(
        [
            {
                "title": "Income",
                "headers": ["Date", "Receipt #", "Fee Type", "Category", "Amount", "Notes"],
                "rows": income_rows,
            },
            {
                "title": "Expenditure",
                "headers": ["Date", "Category", "Sub-Head", "Description", "Amount"],
                "rows": exp_rows,
            },
            {
                "title": "Summary",
                "headers": ["Item", "Amount"],
                "rows": [
                    ["Total PTA Income", totals["total_pta_income"]],
                    ["Total State Income", totals["total_state_income"]],
                    ["Total Income", totals["total_income"]],
                    ["Total PTA Expenditure", totals["total_pta_expenditure"]],
                    ["Total State Expenditure", totals["total_state_expenditure"]],
                    ["Total Expenditure", totals["total_expenditure"]],
                    ["Balance", totals["balance"]],
                    ["PTA Balance", totals["pta_balance"]],
                    ["State Balance", totals["state_balance"]],
                ],
            },
        ]
    )
    return excel_response(wb, f"finance_{term}.xlsx")


@login_required
@role_required("admin", "superuser")
def export_attendance_excel(request, class_id: int, term_id: int):
    school = get_school_for_user(request.user)
    school_class = get_object_or_404(SchoolClass, pk=class_id, school=school)
    term = get_object_or_404(AcademicTerm, pk=term_id, school=school)

    registers = list(
        AttendanceRegister.objects.filter(
            school_class=school_class, date__year__gte=term.year_start, date__year__lte=term.year_end
        ).order_by("date")
    )
    register_ids = [r.pk for r in registers]
    records = AttendanceRecord.objects.filter(register_id__in=register_ids).select_related(
        "student", "register"
    )

    student_totals = {}
    for rec in records:
        key = rec.student_id
        entry = student_totals.setdefault(
            key,
            {"student": rec.student, "P": 0, "L": 0, "A": 0, "PRM": 0, "sessions": 0},
        )
        entry[rec.status] = entry.get(rec.status, 0) + 1
        entry["sessions"] += 1

    rows = []
    for key, entry in student_totals.items():
        s = entry["student"]
        present_pct = (
            round(Decimal(entry["P"]) * 100 / Decimal(entry["sessions"]), 1)
            if entry["sessions"]
            else Decimal(0)
        )
        rows.append(
            [
                s.unique_id,
                s.full_name,
                entry["P"],
                entry["L"],
                entry["A"],
                entry["PRM"],
                entry["sessions"],
                present_pct,
            ]
        )

    wb = build_workbook(
        [
            {
                "title": "Attendance",
                "headers": [
                    "Student ID",
                    "Name",
                    "Present",
                    "Late",
                    "Absent",
                    "Permission",
                    "Total Periods",
                    "Present %",
                ],
                "rows": rows,
            }
        ]
    )
    return excel_response(wb, f"attendance_{school_class.code}_{term}.xlsx")


@login_required
@role_required("admin", "superuser")
def export_results_excel(request, term_id: int):
    school = get_school_for_user(request.user)
    term = get_object_or_404(AcademicTerm, pk=term_id, school=school)

    results = list(
        TermResult.objects.filter(academic_term=term).select_related("student")
    )
    rows = []
    for r in results:
        s = r.student
        enrollment = (
            s.enrollments.filter(academic_term=term)
            .select_related("school_class")
            .first()
        )
        rows.append(
            [
                str(enrollment.school_class) if enrollment else "",
                s.unique_id,
                s.full_name,
                s.get_sex_display(),
                r.total_score,
                r.total_coef,
                r.average,
                r.grade,
                r.remark,
                r.rank,
                "Promoted" if r.promoted else ("Repeat" if r.promoted is False else ""),
            ]
        )

    wb = build_workbook(
        [
            {
                "title": "Results",
                "headers": [
                    "Class",
                    "Student ID",
                    "Name",
                    "Sex",
                    "Total Score",
                    "Total Coef",
                    "Average",
                    "Grade",
                    "Remark",
                    "Rank",
                    "Promotion",
                ],
                "rows": rows,
            }
        ]
    )
    return excel_response(wb, f"results_{term}.xlsx")

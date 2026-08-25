from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.models import (
    AcademicTerm,
    SchoolClass,
    Student,
)
from core.utils.mark_sheet import AnnualMarkSheet, MarkSheet
from core.utils.permissions import get_school_for_user, role_required
from core.utils.report_card import AnnualReportCard, TermReportCard


def _merge_pdf_bytes(pdf_blobs: list[bytes]) -> bytes:
    """Concatenate PDF byte strings into one PDF.

    Uses page-by-page copy (PdfReader -> add_page) which is the most compatible
    merge strategy — pypdf's ``append()``/``merge()`` run deep catalog
    processing (outlines, annotations, AcroForm, StructTreeRoot) that can fail
    on WeasyPrint-generated PDFs.
    """
    from io import BytesIO

    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for blob in pdf_blobs:
        reader = PdfReader(BytesIO(blob))
        for page in reader.pages:
            writer.add_page(page)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@login_required
def reports_hub(request):
    school = get_school_for_user(request.user)
    if not school:
        from django.contrib import messages

        messages.error(request, "No school linked to your account.")
        return render(request, "reports/hub.html", {"school": None})

    from datetime import date

    from core.models import Subject, Teacher

    classes = SchoolClass.objects.filter(school=school).order_by("sort_order")
    terms = AcademicTerm.objects.filter(school=school).order_by(
        "-year_start", "-year_end", "term_number"
    )
    students = list(
        Student.objects.filter(school=school, is_active=True).order_by("first_name")
    )
    teachers = Teacher.objects.filter(school=school, is_active=True).order_by(
        "first_name", "last_name"
    )
    subjects = Subject.objects.filter(school=school).order_by("sort_order")

    current_year = date.today().year
    years = list(range(current_year - 1, current_year + 3))

    return render(
        request,
        "reports/hub.html",
        {
            "classes": classes,
            "terms": terms,
            "students": students,
            "teachers": teachers,
            "subjects": subjects,
            "years": years,
        },
    )


@login_required
@role_required("admin")
def batch_report_cards(request, class_id: int, term_id: int):
    """Download one merged PDF containing report cards for all students in a class."""
    import logging

    logger = logging.getLogger(__name__)

    school_class = get_object_or_404(SchoolClass, pk=class_id)
    school = school_class.school
    term = get_object_or_404(AcademicTerm, pk=term_id)

    students = list(
        Student.objects.filter(
            enrollments__school_class=school_class,
            enrollments__academic_term=term,
            term_results__academic_term=term,
        ).distinct()
    )

    pdf_blobs = []
    errors = []
    for student in students:
        try:
            report = TermReportCard(student, term, school)
            pdf_blobs.append(report.render_pdf(request.build_absolute_uri("/")))
        except Exception as exc:
            logger.exception("Batch report card failed for student %s", student.pk)
            errors.append(f"{student.full_name}: {exc}")

    if not pdf_blobs:
        detail = "; ".join(errors[:3]) if errors else "No students with results in this class/term."
        return HttpResponse(
            f"No report cards could be generated. {detail}",
            status=500,
            content_type="text/plain",
        )

    pdf = _merge_pdf_bytes(pdf_blobs)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="report_cards_{school_class.code}_{term}.pdf"'
    )
    return response


@login_required
@role_required("admin")
def class_council_view(request, term_id: int):
    from core.utils.class_council import ClassCouncilReport

    term = get_object_or_404(AcademicTerm, pk=term_id)
    school = term.school
    report = ClassCouncilReport(term, school)

    if request.GET.get("format") == "pdf":
        pdf = report.render_pdf(request.build_absolute_uri("/"))
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="{report.filename()}"'
        )
        return response

    html = report.render_html()
    response = HttpResponse(html)
    response["Content-Disposition"] = "inline"
    return response


@role_required("admin")
def annual_class_council_view(request, year_start: int, year_end: int):
    from core.utils.class_council import AnnualClassCouncilReport

    school = get_school_for_user(request.user)
    report = AnnualClassCouncilReport(year_start, year_end, school)

    if request.GET.get("format") == "pdf":
        pdf = report.render_pdf(request.build_absolute_uri("/"))
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="{report.filename()}"'
        )
        return response

    html = report.render_html()
    response = HttpResponse(html)
    response["Content-Disposition"] = "inline"
    return response


@login_required
@role_required("admin")
def class_council_motifs(request):
    """Manage withheld-class remarks (motifs) for a term or academic year."""
    from django.contrib import messages

    from core.models import ClassCouncilRemark

    school = get_school_for_user(request.user)
    if not school:
        messages.error(request, "No school linked to your account.")
        return render(request, "reports/class_council_motifs.html", {"school": None})

    terms = AcademicTerm.objects.filter(school=school).order_by(
        "-year_start", "-year_end", "term_number"
    )
    classes = SchoolClass.objects.filter(school=school).order_by("sort_order")

    term_id = request.GET.get("term") or request.POST.get("term")
    year = request.GET.get("year") or request.POST.get("year")
    mode = request.GET.get("mode", "term")

    term_obj = None
    year_start = None
    year_end = None
    if term_id and str(term_id).isdigit():
        term_obj = AcademicTerm.objects.filter(pk=int(term_id), school=school).first()
        mode = "term"
    elif year and "/" in year:
        parts = year.split("/")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            year_start = int(parts[0])
            year_end = int(parts[1])
            mode = "year"

    if request.method == "POST":
        for cls in classes:
            motif = request.POST.get(f"motif_{cls.pk}", "").strip()
            existing = None
            if mode == "term" and term_obj:
                existing = ClassCouncilRemark.objects.filter(
                    school=school, school_class=cls, academic_term=term_obj
                ).first()
            elif mode == "year":
                existing = ClassCouncilRemark.objects.filter(
                    school=school,
                    school_class=cls,
                    academic_term__isnull=True,
                    year_start=year_start,
                    year_end=year_end,
                ).first()
            if motif:
                if existing:
                    existing.motif = motif
                    existing.save()
                else:
                    ClassCouncilRemark.objects.create(
                        school=school,
                        school_class=cls,
                        academic_term=term_obj if mode == "term" else None,
                        year_start=year_start if mode == "year" else None,
                        year_end=year_end if mode == "year" else None,
                        motif=motif,
                    )
            elif existing:
                existing.delete()
        messages.success(request, "Class council remarks saved.")
        return redirect(
            f"{request.path}?mode={mode}&term={term_obj.pk if term_obj else ''}&year={year or ''}"
        )

    remarks = {}
    if mode == "term" and term_obj:
        for r in ClassCouncilRemark.objects.filter(
            school=school, academic_term=term_obj
        ):
            remarks[r.school_class_id] = r.motif
    elif mode == "year":
        for r in ClassCouncilRemark.objects.filter(
            school=school,
            academic_term__isnull=True,
            year_start=year_start,
            year_end=year_end,
        ):
            remarks[r.school_class_id] = r.motif

    return render(
        request,
        "reports/class_council_motifs.html",
        {
            "school": school,
            "terms": terms,
            "classes": classes,
            "term_obj": term_obj,
            "mode": mode,
            "selected_year": year or "",
            "remarks": remarks,
        },
    )


@login_required
@role_required("admin", "bursar")
def pta_financial_view(request, term_id: int):
    from core.utils.pta_finance import PTAFinanceReport

    term = get_object_or_404(AcademicTerm, pk=term_id)
    school = term.school
    report = PTAFinanceReport(term, school)

    if request.GET.get("format") == "pdf":
        pdf = report.render_pdf(request.build_absolute_uri("/"))
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="{report.filename()}"'
        )
        return response

    html = report.render_html()
    response = HttpResponse(html)
    response["Content-Disposition"] = "inline"
    return response



@role_required("admin")
def download_term_report(request, student_id: int, term_id: int):
    student = get_object_or_404(Student, pk=student_id)
    term = get_object_or_404(AcademicTerm, pk=term_id)
    school = student.school
    report = TermReportCard(student, term, school)
    pdf = report.render_pdf(request.build_absolute_uri("/"))
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{report.filename()}"'
    return response


@role_required("admin")
def download_annual_report(request, student_id: int, year_start: int, year_end: int):
    student = get_object_or_404(Student, pk=student_id)
    school = student.school
    report = AnnualReportCard(student, year_start, year_end, school)
    pdf = report.render_pdf(request.build_absolute_uri("/"))
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{report.filename()}"'
    return response


@role_required("admin")
def preview_term_report(request, student_id: int, term_id: int):
    student = get_object_or_404(Student, pk=student_id)
    term = get_object_or_404(AcademicTerm, pk=term_id)
    school = student.school
    report = TermReportCard(student, term, school)
    html = report.render_html()
    return HttpResponse(html)


@role_required("admin")
def preview_annual_report(request, student_id: int, year_start: int, year_end: int):
    student = get_object_or_404(Student, pk=student_id)
    school = student.school
    report = AnnualReportCard(student, year_start, year_end, school)
    html = report.render_html()
    return HttpResponse(html)


@role_required("admin")
def batch_annual_report_cards(
    request, class_id: int, year_start: int, year_end: int
):
    import logging

    logger = logging.getLogger(__name__)

    school_class = get_object_or_404(SchoolClass, pk=class_id)
    school = school_class.school
    terms = AcademicTerm.objects.filter(
        school=school, year_start=year_start, year_end=year_end
    ).order_by("term_number")

    students = list(
        Student.objects.filter(
            enrollments__school_class=school_class,
            enrollments__academic_term__in=terms,
            subject_averages__academic_term__in=terms,
        ).distinct()
    )

    pdf_blobs = []
    errors = []
    for student in students:
        try:
            report = AnnualReportCard(student, year_start, year_end, school)
            pdf_blobs.append(report.render_pdf(request.build_absolute_uri("/")))
        except Exception as exc:
            logger.exception("Batch annual report failed for student %s", student.pk)
            errors.append(f"{student.full_name}: {exc}")

    if not pdf_blobs:
        detail = "; ".join(errors[:3]) if errors else "No students with results in this class/year."
        return HttpResponse(
            f"No report cards could be generated. {detail}",
            status=500,
            content_type="text/plain",
        )

    pdf = _merge_pdf_bytes(pdf_blobs)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="annual_report_cards_{school_class.code}_{year_start}_{year_end}.pdf"'
    )
    return response


@role_required("admin")
def download_mark_sheet(request, class_id: int, term_id: int):
    school_class = get_object_or_404(SchoolClass, pk=class_id)
    term = get_object_or_404(AcademicTerm, pk=term_id)
    school = school_class.school
    report = MarkSheet(school_class, term, school)
    pdf = report.render_pdf(request.build_absolute_uri("/"))
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{report.filename()}"'
    return response


@role_required("admin")
def download_annual_mark_sheet(request, class_id: int, year_start: int, year_end: int):
    school_class = get_object_or_404(SchoolClass, pk=class_id)
    school = school_class.school
    report = AnnualMarkSheet(school_class, year_start, year_end, school)
    pdf = report.render_pdf(request.build_absolute_uri("/"))
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{report.filename()}"'
    return response


@role_required("admin")
def preview_mark_sheet(request, class_id: int, term_id: int):
    school_class = get_object_or_404(SchoolClass, pk=class_id)
    term = get_object_or_404(AcademicTerm, pk=term_id)
    school = school_class.school
    report = MarkSheet(school_class, term, school)
    html = report.render_html()
    return HttpResponse(html)


@role_required("admin")
def preview_annual_mark_sheet(request, class_id: int, year_start: int, year_end: int):
    school_class = get_object_or_404(SchoolClass, pk=class_id)
    school = school_class.school
    report = AnnualMarkSheet(school_class, year_start, year_end, school)
    html = report.render_html()
    return HttpResponse(html)


def _selected_id_students(request, school):
    """Resolve up to 4 students from ?students=1,2,3 (defaults to first 4 active)."""
    from core.models import Student

    raw = request.GET.get("students", "")
    if raw:
        ids = [int(x) for x in raw.split(",") if x.strip().isdigit()][:4]
        order = {pk: i for i, pk in enumerate(ids)}
        students = list(
            Student.objects.filter(pk__in=ids, school=school, is_active=True)
        )
        students.sort(key=lambda s: order.get(s.pk, 99))
    else:
        students = list(Student.objects.filter(school=school, is_active=True)[:4])
    return students


@role_required("admin")
def preview_id_cards(request):
    from datetime import date

    from core.models import School
    from core.utils.student_id import distribute_to_four, render_full_set_html

    school = School.objects.first()
    students = distribute_to_four(_selected_id_students(request, school))
    context = {"academic_year": "2025/2026", "today": date.today()}
    html = render_full_set_html(students, school, context)
    return HttpResponse(html)


@role_required("admin")
def download_id_cards(request):
    from datetime import date

    from core.models import School
    from core.utils.student_id import distribute_to_four, render_full_set_html

    school = School.objects.first()
    students = distribute_to_four(_selected_id_students(request, school))
    context = {"academic_year": "2025/2026", "today": date.today()}
    html = render_full_set_html(students, school, context)
    response = HttpResponse(html, content_type="text/html")
    response["Content-Disposition"] = 'attachment; filename="id_cards.html"'
    return response


@role_required("admin")
def download_results_summary(request, term_id: int):
    from django.template.loader import render_to_string

    from core.models import AcademicTerm, SchoolClass
    from core.utils.results_summary import ResultsSummary

    term = get_object_or_404(AcademicTerm, pk=term_id)
    school = term.school
    classes = SchoolClass.objects.filter(school=school).order_by("sort_order")
    sections = []
    for sc in classes:
        report = ResultsSummary(sc, term, school)
        ctx = report.get_context_data()
        if ctx["num_sat"] == 0 or ctx["enrolment_total"] == 0:
            continue
        sections.append(render_to_string("reports/results_summary_section.html", ctx))
    html = render_to_string(
        "reports/results_summary.html",
        {
            "school": school,
            "term": term,
            "sections": sections,
        },
    )
    return HttpResponse(html)


@role_required("admin")
def preview_results_summary(request, term_id: int):
    from django.template.loader import render_to_string

    from core.models import AcademicTerm, SchoolClass
    from core.utils.results_summary import ResultsSummary

    term = get_object_or_404(AcademicTerm, pk=term_id)
    school = term.school
    classes = SchoolClass.objects.filter(school=school).order_by("sort_order")
    sections = []
    for sc in classes:
        report = ResultsSummary(sc, term, school)
        ctx = report.get_context_data()
        if ctx["num_sat"] == 0 or ctx["enrolment_total"] == 0:
            continue
        sections.append(render_to_string("reports/results_summary_section.html", ctx))
    html = render_to_string(
        "reports/results_summary.html",
        {
            "school": school,
            "term": term,
            "sections": sections,
        },
    )
    response = HttpResponse(html, content_type="text/html")
    response["Content-Disposition"] = 'inline; filename="results_summary.html"'
    return response


def _render_results_summary(html_template, **kwargs):
    from django.template.loader import render_to_string

    from core.models import SchoolClass

    school = kwargs["school"]
    classes = SchoolClass.objects.filter(school=school).order_by("sort_order")
    sections = []
    for sc in classes:
        report = kwargs["factory"](sc)
        ctx = report.get_context_data()
        if ctx["num_sat"] == 0 or ctx["enrolment_total"] == 0:
            continue
        sections.append(render_to_string("reports/results_summary_section.html", ctx))
    return render_to_string(
        html_template,
        {
            "school": school,
            "term": kwargs["term"],
            "sections": sections,
        },
    )


@role_required("admin")
def download_annual_results_summary(request, year_start: int, year_end: int):
    from django.template.loader import render_to_string

    from core.models import SchoolClass
    from core.utils.results_summary import AnnualResultsSummary

    school = get_school_for_user(request.user)
    classes = SchoolClass.objects.filter(school=school).order_by("sort_order")
    sections = []
    for sc in classes:
        report = AnnualResultsSummary(sc, year_start, year_end, school)
        ctx = report.get_context_data()
        if ctx["num_sat"] == 0 or ctx["enrolment_total"] == 0:
            continue
        sections.append(render_to_string("reports/results_summary_section.html", ctx))
    html = render_to_string(
        "reports/results_summary.html",
        {
            "school": school,
            "term": classes.first(),
            "sections": sections,
            "is_annual": True,
            "year_start": year_start,
            "year_end": year_end,
        },
    )
    response = HttpResponse(html, content_type="text/html")
    response["Content-Disposition"] = (
        f'attachment; filename="results_summary_annual_{year_start}_{year_end}.html"'
    )
    return response


@role_required("admin")
def preview_annual_results_summary(request, year_start: int, year_end: int):
    from django.template.loader import render_to_string

    from core.models import SchoolClass
    from core.utils.results_summary import AnnualResultsSummary

    school = get_school_for_user(request.user)
    classes = SchoolClass.objects.filter(school=school).order_by("sort_order")
    sections = []
    for sc in classes:
        report = AnnualResultsSummary(sc, year_start, year_end, school)
        ctx = report.get_context_data()
        if ctx["num_sat"] == 0 or ctx["enrolment_total"] == 0:
            continue
        sections.append(render_to_string("reports/results_summary_section.html", ctx))
    html = render_to_string(
        "reports/results_summary.html",
        {
            "school": school,
            "term": classes.first(),
            "sections": sections,
            "is_annual": True,
            "year_start": year_start,
            "year_end": year_end,
        },
    )
    response = HttpResponse(html, content_type="text/html")
    response["Content-Disposition"] = 'inline; filename="results_summary_annual.html"'
    return response

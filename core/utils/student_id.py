from datetime import date

from django.template.loader import render_to_string

from core.models import Student


def distribute_to_four(students: list[Student]) -> list[Student]:
    """Return exactly 4 students, replicating selected ones to fill the booklet.

    - 1 student  -> replicated 4 times
    - 2 students -> each replicated twice
    - 3 students -> student 1 twice, students 2 & 3 once
    - 4 students -> as selected
    """
    if not students:
        return []
    n = len(students)
    base, extra = divmod(4, n)
    distributed = []
    for i, st in enumerate(students):
        copies = base + (1 if i < extra else 0)
        distributed.extend([st] * copies)
    return distributed


def render_single_id_page(page_num: int, student: Student, school, context: dict = None) -> str:
    if context is None:
        context = {}
    ctx = {
        "school": school,
        "student": student,
        "page_num": page_num,
        "today": context.get("today", date.today()),
        "academic_year": context.get("academic_year", "2025/2026"),
    }
    return render_to_string("reports/student_id_page.html", ctx)


def render_full_set_html(students: list[Student], school, context: dict = None) -> str:
    """Render 2 A4 sheets with booklet imposition for 4 students."""
    if context is None:
        context = {}
    s = students  # s[0]=S1, s[1]=S2, s[2]=S3, s[3]=S4

    # Sheet 1: Inside spread (Pages 2 and 3)
    # Row 1: S1P2 | S1P3 | S2P2 | S2P3
    # Row 2: S3P2 | S3P3 | S4P2 | S4P3
    sheet1_pages = []
    for row_students in [(s[0], s[1]), (s[2], s[3])]:
        for st in row_students:
            for p in [2, 3]:
                sheet1_pages.append(render_single_id_page(p, st, school, context))

    # Sheet 2: Cover and back (Pages 1 and 4) - reversed for booklet folding
    # Row 1: S2P4 | S2P1 | S1P4 | S1P1
    # Row 2: S4P4 | S4P1 | S3P4 | S3P1
    sheet2_pages = []
    for pair in [(s[1], s[0]), (s[3], s[2])]:
        st1, st2 = pair
        sheet2_pages.append(render_single_id_page(4, st1, school, context))
        sheet2_pages.append(render_single_id_page(1, st1, school, context))
        sheet2_pages.append(render_single_id_page(4, st2, school, context))
        sheet2_pages.append(render_single_id_page(1, st2, school, context))

    return render_to_string("reports/student_id_full.html", {
        "sheet1_pages": sheet1_pages,
        "sheet2_pages": sheet2_pages,
    })

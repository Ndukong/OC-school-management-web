from collections import defaultdict
from datetime import date as date_cls
from decimal import Decimal

from core.models import (
    AttendanceRegister,
    ConductThreshold,
    DisciplineSummary,
    Punishment,
    Student,
)

# Each absent/permission period counts as one absence hour on the report card.
HOURS_PER_PERIOD = Decimal("1.0")

CONDUCT_ORDER = ["warning", "reprimand", "suspension", "dismissal"]


def _term_date_range(term) -> tuple:
    # Academic years run September (year_start) to August (year_end).
    return (date_cls(term.year_start, 9, 1), date_cls(term.year_end, 8, 31))


def _conduct_decision(values: dict, thresholds: dict) -> str:
    """Return the most severe conduct decision whose threshold is fully met."""
    decision = ""
    for conduct_type in CONDUCT_ORDER:
        threshold = thresholds.get(conduct_type)
        if threshold is None:
            continue
        if (
            values["unjustified_abs_hours"] >= threshold.min_unjustified_abs
            and values["justified_abs_hours"] >= threshold.min_justified_abs
            and values["lateness_count"] >= threshold.min_lateness
            and values["punishment_hours"] >= threshold.min_punishment_hours
        ):
            decision = conduct_type
    return decision


def compute_discipline_summaries(school_class, term) -> dict:
    """Aggregate attendance + punishments for a class/term into DisciplineSummary rows.

    Attendance is recorded per period; each period is one attendance session.
    "A" (absent) counts as unjustified, "PRM" (permission) as justified absence,
    each worth HOURS_PER_PERIOD. Registers are matched to the term by the
    September-to-August window of its academic year.
    """
    students = list(
        Student.objects.filter(
            enrollments__school_class=school_class,
            enrollments__academic_term=term,
            is_active=True,
        )
    )
    start, end = _term_date_range(term)
    registers = AttendanceRegister.objects.filter(
        school_class=school_class, date__range=(start, end)
    ).prefetch_related("records")

    counts: dict = defaultdict(lambda: {"A": 0, "PRM": 0, "L": 0})
    for register in registers:
        for record in register.records.all():
            if record.status in counts[record.student_id]:
                counts[record.student_id][record.status] += 1

    punishment_hours: dict = defaultdict(lambda: Decimal(0))
    for punishment in Punishment.objects.filter(
        student__in=students, academic_term=term
    ):
        punishment_hours[punishment.student_id] += punishment.hours

    thresholds = {
        t.conduct_type: t
        for t in ConductThreshold.objects.filter(school=school_class.school)
    }

    rows = []
    for student in students:
        count = counts.get(student.id, {"A": 0, "PRM": 0, "L": 0})
        values = {
            "unjustified_abs_hours": Decimal(count["A"]) * HOURS_PER_PERIOD,
            "justified_abs_hours": Decimal(count["PRM"]) * HOURS_PER_PERIOD,
            "lateness_count": count["L"],
            "punishment_hours": punishment_hours[student.id],
        }
        summary, _ = DisciplineSummary.objects.update_or_create(
            student=student,
            academic_term=term,
            defaults={
                **values,
                "conduct_decision": _conduct_decision(values, thresholds),
            },
        )
        rows.append({"student": student, "summary": summary})

    return {"school_class": school_class, "term": term, "rows": rows}

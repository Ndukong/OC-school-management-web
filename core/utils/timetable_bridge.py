"""Bridge between Django ORM and the pure-Python timetable solver."""

from core.models import (
    Room,
    SchoolClass,
    Subject,
    SubjectConstraint,
    SubjectPeriodRequirement,
    Teacher,
    TeacherAssignment,
    TeacherAvailability,
    TeacherPreference,
    Timetable,
    TimetableConfig,
    TimetableEntry,
)
from core.solver.problem import (
    ClassInfo,
    Requirement,
    RoomInfo,
    ScheduleEntry,
    SlotInfo,
    SoftConstraint,
    SubjectInfo,
    TeacherInfo,
    TimetableProblem,
    Unavailability,
)


def build_problem(
    config: TimetableConfig, locked_timetable: Timetable | None = None
) -> TimetableProblem:
    """Convert a TimetableConfig and its related ORM data into a TimetableProblem.

    If locked_timetable is provided, its locked entries are passed to the solver
    as immovable placements (for mid-year re-generation).
    """
    school = config.school

    slots = [
        SlotInfo(
            slot_id=ps.pk,
            slot_number=ps.slot_number,
            label=ps.label,
            can_start_double=ps.can_start_double,
            start_time=ps.start_time.strftime("%H:%M"),
            end_time=ps.end_time.strftime("%H:%M"),
        )
        for ps in config.period_slots.filter(slot_type="teaching").order_by(
            "slot_number"
        )
    ]

    classes = [
        ClassInfo(
            class_id=sc.pk,
            name=str(sc),
            form_level=sc.form_level,
            sort_order=sc.sort_order,
        )
        for sc in SchoolClass.objects.filter(school=school).order_by("sort_order")
    ]

    teachers = [
        TeacherInfo(teacher_id=t.pk, name=str(t))
        for t in Teacher.objects.filter(school=school, is_active=True)
    ]

    subjects = [
        SubjectInfo(subject_id=s.pk, code=s.code, name=s.name)
        for s in Subject.objects.filter(school=school)
    ]

    rooms = [
        RoomInfo(room_id=r.pk, name=r.name, room_type=r.room_type, capacity=r.capacity)
        for r in Room.objects.filter(school=school, is_active=True)
    ]

    requirements = []
    for req in SubjectPeriodRequirement.objects.filter(config=config).select_related(
        "school_class", "subject", "preferred_room"
    ):
        assignment = TeacherAssignment.objects.filter(
            school_class=req.school_class,
            subject=req.subject,
            is_active=True,
        ).first()
        if assignment is None:
            continue
        requirements.append(
            Requirement(
                class_id=req.school_class_id,
                subject_id=req.subject_id,
                teacher_id=assignment.teacher_id,
                periods_per_week=req.periods_per_week,
                doubles_per_week=req.doubles_per_week,
                room_id=req.preferred_room_id,
            )
        )

    unavailabilities = [
        Unavailability(
            teacher_id=ua.teacher_id,
            day=ua.day,
            slot_id=ua.period_slot_id,
        )
        for ua in TeacherAvailability.objects.filter(config=config)
    ]

    soft_constraints = []
    for tp in TeacherPreference.objects.filter(config=config):
        soft_constraints.append(
            SoftConstraint(
                constraint_type=tp.preference_type,
                target_type="teacher",
                target_id=tp.teacher_id,
                value=tp.value,
                weight=tp.weight,
            )
        )
    for sc_c in SubjectConstraint.objects.filter(config=config):
        soft_constraints.append(
            SoftConstraint(
                constraint_type=sc_c.constraint_type,
                target_type="subject",
                target_id=sc_c.subject_id,
                value=sc_c.value,
                weight=sc_c.weight,
            )
        )

    locked = []
    if locked_timetable:
        for e in TimetableEntry.objects.filter(
            timetable=locked_timetable, is_locked=True
        ).select_related("period_slot"):
            locked.append(
                ScheduleEntry(
                    class_id=e.school_class_id,
                    subject_id=e.subject_id,
                    teacher_id=e.teacher_id,
                    room_id=e.room_id,
                    day=e.day,
                    slot_id=e.period_slot_id,
                    is_double_start=e.is_double_start,
                    is_double_end=e.is_double_end,
                    is_locked=True,
                )
            )

    return TimetableProblem(
        days=config.days,
        slots_per_day=slots,
        assembly_day=config.assembly_day,
        assembly_lost_slots=config.assembly_duration_periods,
        classes=classes,
        teachers=teachers,
        subjects=subjects,
        rooms=rooms,
        requirements=requirements,
        unavailabilities=unavailabilities,
        soft_constraints=soft_constraints,
        locked_entries=locked,
    )


def save_result_to_db(
    config: TimetableConfig,
    result,
    name: str = "Generated",
) -> Timetable:
    """Persist a SolverResult as a Timetable + TimetableEntry rows."""
    from django.db import transaction

    with transaction.atomic():
        timetable = Timetable.objects.create(
            config=config,
            name=name,
            status="completed" if result.success else "failed",
            fitness_score=result.fitness_score,
            hard_violations=len(result.hard_violations),
            soft_violation_count=len(result.soft_violations),
            generation_time_seconds=result.generation_time_seconds,
            solver_log=result.solver_log,
        )
        entries = [
            TimetableEntry(
                timetable=timetable,
                day=e.day,
                period_slot_id=e.slot_id,
                school_class_id=e.class_id,
                subject_id=e.subject_id,
                teacher_id=e.teacher_id,
                room_id=e.room_id,
                is_double_start=e.is_double_start,
                is_double_end=e.is_double_end,
                is_locked=e.is_locked,
            )
            for e in result.schedule
        ]
        TimetableEntry.objects.bulk_create(entries)
    return timetable

"""Per-school data export/import using natural keys.

Exports one school's configuration and people (profile, terms, classes,
subjects, competencies, class-subjects, teachers, assignments, students,
enrollments) as portable JSON. Binary media (photos/signatures/logos) and
computed results are intentionally excluded from this MVP schema.
"""

SCHEMA_NAME = "oc-school-export"
SCHEMA_VERSION = 1


def _term_key(term) -> str:
    return f"{term.year_start}/{term.year_end}/T{term.term_number}"


def _class_key(cls) -> str:
    return cls.code if not cls.stream else f"{cls.code}-{cls.stream}"


def _teacher_key(teacher) -> str:
    return (
        teacher.teacher_code
        or teacher.email
        or f"{teacher.first_name}.{teacher.last_name}".lower().replace(" ", "")
    )


def build_school_export(school) -> dict:
    from core.models import (
        AcademicTerm,
        ClassSubject,
        Competency,
        SchoolClass,
        Student,
        StudentEnrollment,
        Subject,
        Teacher,
        TeacherAssignment,
    )

    terms = list(AcademicTerm.objects.filter(school=school).order_by("year_start", "term_number"))
    classes = list(SchoolClass.objects.filter(school=school).order_by("sort_order"))
    subjects = list(Subject.objects.filter(school=school).order_by("sort_order"))

    return {
        "schema": SCHEMA_NAME,
        "version": SCHEMA_VERSION,
        "exported_at": school.updated_at.date().isoformat()
        if school.updated_at
        else None,
        "school": {
            "name_en": school.name_en,
            "name_fr": school.name_fr,
            "matricule": school.matricule,
            "phone": school.phone,
            "region_en": school.region_en,
            "region_fr": school.region_fr,
            "division_en": school.division_en,
            "division_fr": school.division_fr,
            "motto_en": school.motto_en,
            "motto_fr": school.motto_fr,
            "periods_per_day": school.periods_per_day,
        },
        "terms": [
            {
                "key": _term_key(t),
                "term_number": t.term_number,
                "year_start": t.year_start,
                "year_end": t.year_end,
                "is_current": t.is_current,
            }
            for t in terms
        ],
        "classes": [
            {
                "key": _class_key(c),
                "name": c.name,
                "code": c.code,
                "stream": c.stream,
                "cycle": c.cycle,
                "form_level": c.form_level,
                "promotion_mark": c.promotion_mark,
                "dismissal_mark": c.dismissal_mark,
                "sort_order": c.sort_order,
            }
            for c in classes
        ],
        "subjects": [
            {"key": s.code, "name": s.name, "code": s.code, "sort_order": s.sort_order}
            for s in subjects
        ],
        "competencies": [
            {
                "subject": comp.subject.code,
                "term": _term_key(comp.term),
                "form_level": comp.form_level,
                "description": comp.description,
                "sort_order": comp.sort_order,
            }
            for comp in Competency.objects.filter(
                subject__school=school
            ).select_related("subject", "term")
        ],
        "class_subjects": [
            {
                "class": _class_key(cs.school_class),
                "subject": cs.subject.code,
                "coefficient": cs.coefficient,
                "sort_order": cs.sort_order,
            }
            for cs in ClassSubject.objects.filter(
                school_class__school=school
            ).select_related("school_class", "subject")
        ],
        "teachers": [
            {
                "key": _teacher_key(t),
                "first_name": t.first_name,
                "last_name": t.last_name,
                "teacher_code": t.teacher_code,
                "email": t.email,
                "phone": t.phone,
                "is_active": t.is_active,
            }
            for t in Teacher.objects.filter(school=school)
        ],
        "assignments": [
            {
                "teacher": _teacher_key(a.teacher),
                "class": _class_key(a.school_class),
                "subject": a.subject.code,
                "is_class_master": a.is_class_master,
                "is_active": a.is_active,
            }
            for a in TeacherAssignment.objects.filter(
                teacher__school=school
            ).select_related("teacher", "school_class", "subject")
        ],
        "students": [
            {
                "unique_id": s.unique_id,
                "first_name": s.first_name,
                "other_names": s.other_names,
                "sex": s.sex,
                "repeater": s.repeater,
                "date_of_birth": s.date_of_birth.isoformat(),
                "place_of_birth": s.place_of_birth,
                "guardian_name": s.guardian_name,
                "guardian_contact": s.guardian_contact,
                "guardian_address": s.guardian_address,
                "division_of_origin": s.division_of_origin,
                "sub_division_of_origin": s.sub_division_of_origin,
                "region_of_origin": s.region_of_origin,
                "father_name": s.father_name,
                "mother_name": s.mother_name,
                "parent_contact": s.parent_contact,
                "is_active": s.is_active,
            }
            for s in Student.objects.filter(school=school)
        ],
        "enrollments": [
            {
                "student": e.student.unique_id,
                "term": _term_key(e.academic_term),
                "class": _class_key(e.school_class),
            }
            for e in StudentEnrollment.objects.filter(
                student__school=school
            ).select_related("student", "academic_term", "school_class")
        ],
    }


def restore_school_export(data: dict, school) -> dict:
    """Import an export payload into ``school``. Create-missing-only."""
    from django.db import IntegrityError

    from core.models import (
        AcademicTerm,
        ClassSubject,
        Competency,
        SchoolClass,
        Student,
        StudentEnrollment,
        Subject,
        Teacher,
        TeacherAssignment,
    )

    if data.get("schema") != SCHEMA_NAME:
        raise ValueError("Unrecognised export file (bad schema).")
    if int(data.get("version", 0)) > SCHEMA_VERSION:
        raise ValueError("Export file is from a newer app version.")

    counts = {
        "terms": 0,
        "classes": 0,
        "subjects": 0,
        "competencies": 0,
        "class_subjects": 0,
        "teachers": 0,
        "assignments": 0,
        "students": 0,
        "enrollments": 0,
        "student_conflicts": 0,
        "skipped": 0,
    }

    term_map = {}
    for item in data.get("terms", []):
        try:
            obj, created = AcademicTerm.objects.get_or_create(
                school=school,
                term_number=item["term_number"],
                year_start=item["year_start"],
                year_end=item["year_end"],
                defaults={"is_current": bool(item.get("is_current"))},
            )
        except (KeyError, TypeError, ValueError):
            counts["skipped"] += 1
            continue
        term_map[item.get("key") or _term_key(obj)] = obj
        counts["terms"] += int(created)

    class_map = {}
    for item in data.get("classes", []):
        try:
            obj, created = SchoolClass.objects.get_or_create(
                school=school,
                code=item["code"],
                stream=item.get("stream", ""),
                defaults={
                    "name": item.get("name", item["code"]),
                    "cycle": item.get("cycle", "first"),
                    "form_level": item.get("form_level", 1),
                    "promotion_mark": item.get("promotion_mark", 10.0),
                    "dismissal_mark": item.get("dismissal_mark", 6.0),
                    "sort_order": item.get("sort_order", 0),
                },
            )
        except (KeyError, TypeError, ValueError):
            counts["skipped"] += 1
            continue
        class_map[item.get("key") or _class_key(obj)] = obj
        counts["classes"] += int(created)

    subject_map = {}
    for item in data.get("subjects", []):
        try:
            obj, created = Subject.objects.get_or_create(
                school=school,
                code=item["code"],
                defaults={
                    "name": item.get("name", item["code"]),
                    "sort_order": item.get("sort_order", 0),
                },
            )
        except (KeyError, TypeError, ValueError):
            counts["skipped"] += 1
            continue
        subject_map[item.get("key") or obj.code] = obj
        counts["subjects"] += int(created)

    for item in data.get("competencies", []):
        subject = subject_map.get(item.get("subject"))
        term = term_map.get(item.get("term"))
        if not subject or not term:
            counts["skipped"] += 1
            continue
        _, created = Competency.objects.get_or_create(
            subject=subject,
            term=term,
            form_level=item.get("form_level", 1),
            sort_order=item.get("sort_order", 0),
            defaults={"description": item.get("description", "")},
        )
        counts["competencies"] += int(created)

    for item in data.get("class_subjects", []):
        school_class = class_map.get(item.get("class"))
        subject = subject_map.get(item.get("subject"))
        if not school_class or not subject:
            counts["skipped"] += 1
            continue
        _, created = ClassSubject.objects.get_or_create(
            school_class=school_class,
            subject=subject,
            defaults={
                "coefficient": item.get("coefficient", 1),
                "sort_order": item.get("sort_order", 0),
            },
        )
        counts["class_subjects"] += int(created)

    teacher_map = {}
    for item in data.get("teachers", []):
        key = item.get("key") or item.get("teacher_code")
        if not key or not item.get("first_name"):
            counts["skipped"] += 1
            continue
        obj, created = Teacher.objects.get_or_create(
            school=school,
            teacher_code=key,
            defaults={
                "first_name": item["first_name"],
                "last_name": item.get("last_name", ""),
                "email": item.get("email", ""),
                "phone": item.get("phone", ""),
                "is_active": item.get("is_active", True),
            },
        )
        teacher_map[key] = obj
        counts["teachers"] += int(created)

    for item in data.get("assignments", []):
        teacher = teacher_map.get(item.get("teacher"))
        school_class = class_map.get(item.get("class"))
        subject = subject_map.get(item.get("subject"))
        if not teacher or not school_class or not subject:
            counts["skipped"] += 1
            continue
        _, created = TeacherAssignment.objects.get_or_create(
            teacher=teacher,
            school_class=school_class,
            subject=subject,
            defaults={
                "is_class_master": item.get("is_class_master", False),
                "is_active": item.get("is_active", True),
            },
        )
        counts["assignments"] += int(created)

    student_map = {}
    for item in data.get("students", []):
        uid = item.get("unique_id")
        if not uid or not item.get("first_name"):
            counts["skipped"] += 1
            continue
        try:
            obj, created = Student.objects.get_or_create(
                school=school,
                unique_id=uid,
                defaults={
                    "first_name": item["first_name"],
                    "other_names": item.get("other_names", ""),
                    "sex": item.get("sex", "M"),
                    "repeater": item.get("repeater", False),
                    "date_of_birth": item.get("date_of_birth"),
                    "place_of_birth": item.get("place_of_birth", ""),
                    "guardian_name": item.get("guardian_name", ""),
                    "guardian_contact": item.get("guardian_contact", ""),
                    "guardian_address": item.get("guardian_address", ""),
                    "division_of_origin": item.get("division_of_origin", ""),
                    "sub_division_of_origin": item.get("sub_division_of_origin", ""),
                    "region_of_origin": item.get("region_of_origin", ""),
                    "father_name": item.get("father_name", ""),
                    "mother_name": item.get("mother_name", ""),
                    "parent_contact": item.get("parent_contact", ""),
                    "is_active": item.get("is_active", True),
                },
            )
        except (TypeError, ValueError, IntegrityError):
            counts["student_conflicts"] += 1
            continue
        student_map[uid] = obj
        counts["students"] += int(created)

    for item in data.get("enrollments", []):
        student = student_map.get(item.get("student")) or Student.objects.filter(
            school=school, unique_id=item.get("student")
        ).first()
        term = term_map.get(item.get("term"))
        school_class = class_map.get(item.get("class"))
        if not student or not term or not school_class:
            counts["skipped"] += 1
            continue
        _, created = StudentEnrollment.objects.get_or_create(
            student=student,
            academic_term=term,
            defaults={"school_class": school_class},
        )
        counts["enrollments"] += int(created)

    return counts

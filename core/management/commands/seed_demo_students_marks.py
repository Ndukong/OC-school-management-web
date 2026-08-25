"""Seed demo data: 35 Form 1 students and randomized marks for F1-F5.

    python manage.py seed_demo_students_marks

Creates Form 1 students (only the shortfall up to 35) with North West
Cameroon names and fake personal info, enrolls every F1-F5 student in all
three terms of the current academic year, generates randomized competency
scores (1 to 3 per subject per student) for the class-selected subjects,
then computes subject averages, term results and ranks.

Idempotent: re-running regenerates the 2026/2027 scores deterministically
(same seed) and recomputes results.
"""

import random
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import (
    AcademicTerm,
    ClassSubject,
    Competency,
    CompetencyScore,
    SchoolClass,
    Student,
    StudentEnrollment,
    SubjectAverage,
    TermResult,
)
from core.utils.compute_results import compute_term_results

SEED = 20260814
FORM1_TARGET = 35

SURNAMES = [
    "Nfor", "Ngwa", "Fon", "Nkem", "Babila", "Mbah", "Tanyi", "Che",
    "Niba", "Fongang", "Kongnyuy", "Baleguel", "Fobuzie", "Awa", "Tanko",
    "Tifuh", "Ngu", "Kimbi", "Tabe", "Ayuk", "Enow", "Tabi", "Fusi",
    "Nsah", "Folem", "Bih", "Ngang", "Njei", "Yuni", "Nde", "Nkwi",
    "Toh", "Nsoh", "Fuo", "Ngam", "Fuam", "Fokum", "Mbang", "Ndikum",
    "Nchifor", "Tasi", "Nkweti", "Tah", "Waindim", "Fonyuy", "Nkwain",
]

MALE_NAMES = [
    "Jude", "Anthony", "Desmond", "Elvis", "Collins", "Divine", "Fuh",
    "Berinyuy", "Wirba", "Sunjo", "Bernards", "Roland", "Ebenezer",
    "Christopher", "Michael", "Daniel", "Samuel", "Peter", "Emmanuel",
    "George", "Francis", "Henry", "Isaac", "Joseph", "Patrick", "Vincent",
    "William", "Ndze", "Fuinya", "Fru", "Akah", "Tabenyang", "Balep",
    "Nkemnji", "Sama", "Chefor", "Ngong", "Sang", "Njah", "Suh",
]

FEMALE_NAMES = [
    "Noela", "Manka", "Yvonne", "Fridoline", "Ngum", "Nkemngu",
    "Ngalim", "Ruh", "Ngassa", "Fobellah", "Ngufor", "Achiri", "Precious",
    "Blessing", "Glory", "Doris", "Cynthia", "Bernice", "Edith", "Esther",
    "Faith", "Grace", "Joy", "Lucy", "Mary", "Naomi", "Patricia",
    "Rebecca", "Rose", "Ruth", "Sandra", "Tina", "Vanessa", "Wilma",
    "Nchang", "Siani", "Wanki", "Fonkeng", "Yungong", "Anye",
]

TOWNS = [
    "Bamenda", "Bafut", "Bali", "Ndop", "Kumbo", "Wum", "Fundong",
    "Ndu", "Batibo", "Mbengwi", "Nkambe", "Banso", "Oku", "Mbiame",
    "Santa", "Jakiri", "Belo", "Njinikom", "Awing", "Babanki", "Mbatu",
    "Nkwen", "Mankon", "Mendankwe", "Bambili", "Bambui", "Bamali",
    "Binka", "Guzang", "Chomba",
]

DIVISIONS = {
    "Mezam": ["Bamenda I", "Bamenda II", "Bamenda III", "Bafut", "Santa", "Bali", "Tubah"],
    "Bui": ["Kumbo", "Mbven", "Jakiri", "Nkum", "Noni"],
    "Momo": ["Mbengwi", "Batibo", "Widikum", "Njikwa"],
    "Ngoketunjia": ["Ndop", "Babessi", "Balikumbat"],
    "Boyo": ["Fundong", "Njinikom", "Belo", "Bum"],
    "Donga-Mantung": ["Ndu", "Nkambe", "Ako", "Nwa"],
    "Menchum": ["Wum", "Fungom", "Zhoa"],
}


class Command(BaseCommand):
    help = "Seed demo Form 1 students and randomized F1-F5 marks for all terms."

    def add_arguments(self, parser):
        parser.add_argument(
            "--form1",
            type=int,
            default=FORM1_TARGET,
            help=f"Number of Form 1 students to ensure (default {FORM1_TARGET}).",
        )
        parser.add_argument(
            "--seed", type=int, default=SEED, help="Random seed (default 20260814)."
        )

    def handle(self, *args, **options):
        target = options["form1"]
        rng = random.Random(options["seed"])
        # Independent stream so score generation is stable across re-runs even
        # when the "people" RNG is advanced by different amounts.
        score_rng = random.Random(options["seed"] + 1000)

        school = SchoolClass.objects.first().school
        terms = list(
            AcademicTerm.objects.filter(school=school, year_start=2026, year_end=2027)
            .order_by("term_number")
        )
        if len(terms) < 3:
            self.stdout.write(self.style.ERROR("Need 3 terms for 2026/2027; aborting."))
            return
        term_by_number = {t.term_number: t for t in terms}

        classes = {
            c.code: c
            for c in SchoolClass.objects.filter(school=school)
            .exclude(form_level__in=(6, 7))
            .order_by("sort_order")
        }
        self.stdout.write(
            self.style.SUCCESS(
                f"School: {school.name_en} | Terms: "
                + ", ".join(f"T{t.term_number}" for t in terms)
            )
        )

        with transaction.atomic():
            # ---------- 1. Form 1 students ----------
            f1 = classes["F1"]
            t1 = term_by_number[1]
            existing = Student.objects.filter(
                enrollments__school_class=f1,
                enrollments__academic_term=t1,
                is_active=True,
            ).count()
            to_create = max(0, target - existing)
            if to_create:
                students = self._create_form1_students(
                    f1, to_create, term_by_number[1], rng
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Created {len(students)} Form 1 students.")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Form 1 already has {existing} students this term; none created."
                    )
                )

            # ---------- 2. Enroll everyone in all terms ----------
            enrolled_total = 0
            for code in ("F1", "F2", "F3", "F4", "F5"):
                cls = classes[code]
                student_ids = list(
                    Student.objects.filter(
                        enrollments__school_class=cls,
                        enrollments__academic_term=t1,
                        is_active=True,
                    )
                    .values_list("id", flat=True)
                    .distinct()
                )
                for term in terms:
                    existing_ids = set(
                        StudentEnrollment.objects.filter(
                            academic_term=term, student_id__in=student_ids
                        ).values_list("student_id", flat=True)
                    )
                    missing = [
                        StudentEnrollment(student_id=sid, school_class=cls, academic_term=term)
                        for sid in student_ids
                        if sid not in existing_ids
                    ]
                    StudentEnrollment.objects.bulk_create(missing)
                    enrolled_total += len(missing)
            self.stdout.write(
                self.style.SUCCESS(f"Created {enrolled_total} new enrollments.")
            )

            # ---------- 3. Reset 2026/2027 results ----------
            deleted = 0
            for model in (CompetencyScore, SubjectAverage, TermResult):
                deleted += model.objects.filter(
                    academic_term__in=terms
                ).delete()[0]
            self.stdout.write(
                self.style.WARNING(f"Cleared {deleted} existing 2026/2027 score/result rows.")
            )

            # ---------- 4. Generate competency scores ----------
            n_scores = self._generate_scores(classes, term_by_number, score_rng)
            self.stdout.write(
                self.style.SUCCESS(f"Generated {n_scores} competency scores.")
            )

            # ---------- 5. Compute results per class & term ----------
            for code in ("F1", "F2", "F3", "F4", "F5"):
                for term in terms:
                    compute_term_results(classes[code], term)
            self.stdout.write(
                self.style.SUCCESS("Computed subject averages, term results and ranks.")
            )

        self.stdout.write(self.style.SUCCESS("Demo data seeding complete."))

    def _create_form1_students(
        self,
        f1: SchoolClass,
        count: int,
        t1: AcademicTerm,
        rng,
    ) -> list[Student]:
        """Create ``count`` Form 1 students with North West names and fake info."""
        used_ids = set(Student.objects.values_list("unique_id", flat=True))
        divisions = list(DIVISIONS.items())
        students: list[Student] = []

        for _ in range(count):
            sex = "F" if rng.random() < 0.52 else "M"
            names_pool = FEMALE_NAMES if sex == "F" else MALE_NAMES
            first = rng.choice(SURNAMES)
            given = rng.sample(names_pool, 2)
            other = " ".join(given)

            # 9-digit unique state ID
            uid = None
            while uid is None or uid in used_ids:
                uid = f"{rng.randint(10_000_000, 99_999_999):09d}"
            used_ids.add(uid)

            division, subs = rng.choice(divisions)
            sub_division = rng.choice(subs)
            town = rng.choice(TOWNS)
            # Form 1 pupils are roughly 11-13 years old in 2026.
            year = rng.choice((2013, 2014, 2014, 2015))
            dob = date(year, rng.randint(1, 12), rng.randint(1, 28))
            contact = self._phone(rng)
            guardian = self._guardian_name(first, sex, rng)

            students.append(
                Student(
                    school=f1.school,
                    first_name=first,
                    other_names=other,
                    sex=sex,
                    unique_id=uid,
                    repeater=rng.random() < 0.12,
                    date_of_birth=dob,
                    place_of_birth=town,
                    guardian_name=guardian,
                    guardian_contact=contact,
                    guardian_address=f"P.O. Box {rng.randint(1, 500)}, {town}",
                    division_of_origin=division,
                    sub_division_of_origin=sub_division,
                    region_of_origin="North West",
                    father_name=self._guardian_name(first, "M", rng),
                    mother_name=self._guardian_name(first, "F", rng),
                    parent_contact=self._phone(rng),
                    is_active=True,
                )
            )
        created = Student.objects.bulk_create(students)
        StudentEnrollment.objects.bulk_create(
            [StudentEnrollment(student=s, school_class=f1, academic_term=t1) for s in created]
        )
        return created

    def _phone(self, rng) -> str:
        # Cameroon mobile: 6 or 7 then 8 digits (9 total).
        return f"{rng.choice(('6', '7'))}{rng.randint(10_000_000, 99_999_999)}"

    def _guardian_name(self, family: str, sex: str, rng) -> str:
        pool = FEMALE_NAMES if sex == "F" else MALE_NAMES
        given = rng.choice(pool)
        title = "Mrs." if sex == "F" else "Mr."
        return f"{title} {given} {family}"

    def _generate_scores(self, classes: dict, term_by_number: dict, rng) -> int:
        """Assign 1-3 competency scores per subject/student for each term."""
        scores: list[CompetencyScore] = []
        seen = set()
        count = 0

        for code in ("F1", "F2", "F3", "F4", "F5"):
            cls = classes[code]
            class_subjects = list(
                ClassSubject.objects.filter(school_class=cls).select_related("subject")
            )
            students = list(
                Student.objects.filter(
                    enrollments__school_class=cls,
                    enrollments__academic_term__in=term_by_number.values(),
                    is_active=True,
                ).distinct()
            )
            for term in term_by_number.values():
                comp_map = {
                    c.subject_id: list(
                        Competency.objects.filter(
                            subject_id=c.subject_id,
                            term=term,
                            form_level=cls.form_level,
                        ).order_by("sort_order")
                    )
                    for c in class_subjects
                }
                for student in students:
                    tilt = 0
                    roll = rng.random()
                    if roll < 0.06:
                        tilt = -5  # weak pupil (dismissal/repeat candidates)
                    elif roll < 0.12:
                        tilt = 5  # strong pupil
                    for cs in class_subjects:
                        comps = comp_map.get(cs.subject_id) or []
                        if not comps:
                            continue
                        k = rng.randint(1, min(3, len(comps)))
                        picked = rng.sample(comps, k)
                        for comp in picked:
                            key = (student.id, comp.id, term.id)
                            if key in seen:
                                continue
                            seen.add(key)
                            raw = rng.randint(3, 19) + tilt + rng.randint(-1, 1)
                            raw = max(3, min(19, raw))
                            scores.append(
                                CompetencyScore(
                                    student_id=student.id,
                                    competency_id=comp.id,
                                    academic_term_id=term.id,
                                    score=Decimal(raw),
                                )
                            )
                            count += 1
                            if len(scores) >= 500:
                                CompetencyScore.objects.bulk_create(scores)
                                scores.clear()
        if scores:
            CompetencyScore.objects.bulk_create(scores)
        return count

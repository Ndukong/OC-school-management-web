"""Seed demo Form 1-5 structure: classes, subjects, teachers and students.

    python manage.py seed_demo_forms [--school <id>] [--seed N]

Creates (idempotently) for the target school:
- Classes Form 1 to Form 5 (first cycle)
- Three terms for 2026/2027 with First Term current (what
  ``seed_demo_students_marks`` expects)
- The Form 1-5 subject scheme with coefficients in display order:
  F1/F2: FRE(4) LIT(2) ENL(4) CTZ(2) GEO(2) HIS(2) BIO(2) CHE(2) MAT(4)
  PHY(2) SPO(2) MLA(1); F3 adds ECO(2) between HIS and BIO; F4/F5 use
  FRE(4) LIT(2) ENL(4) CTZ(3) GEO(3) HIS(3) BIO(3) HBI(3) CHE(3) MAT(4)
  PHY(3) COM(3) SPO(2) MLA(1)
- 11 teachers with anglophone Cameroonian names, subject assignments that
  pair related subjects (MAT/PHY, ECO/COM) across several classes, and one
  class master per class. Sample signature files are attached where they
  exist in ``media/teachers/signatures/``; the rest stay blank for manual
  samples.
- 21-50 students per form (North West / South West names with full
  registration details), enrolled in the current term.

Re-running fills only shortfalls; existing rows are never duplicated.
"""

import os
import random
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import (
    AcademicTerm,
    ClassSubject,
    School,
    SchoolClass,
    Student,
    StudentEnrollment,
    Subject,
    Teacher,
    TeacherAssignment,
)

SEED = 20260815

SUBJECT_NAMES = {
    "FRE": "French",
    "LIT": "Literature in English",
    "ENL": "English Language",
    "CTZ": "Citizenship Education",
    "GEO": "Geography",
    "HIS": "History",
    "ECO": "Economics",
    "BIO": "Biology",
    "HBI": "Human Biology",
    "CHE": "Chemistry",
    "MAT": "Mathematics",
    "PHY": "Physics",
    "COM": "Commerce",
    "SPO": "Sports & Physical Ed.",
    "MLA": "Manual Labour",
}

_JUNIOR = [
    ("FRE", 4),
    ("LIT", 2),
    ("ENL", 4),
    ("CTZ", 2),
    ("GEO", 2),
    ("HIS", 2),
    ("BIO", 2),
    ("CHE", 2),
    ("MAT", 4),
    ("PHY", 2),
    ("SPO", 2),
    ("MLA", 1),
]
_FORM3 = _JUNIOR[:6] + [("ECO", 2)] + _JUNIOR[6:]
_SENIOR = [
    ("FRE", 4),
    ("LIT", 2),
    ("ENL", 4),
    ("CTZ", 3),
    ("GEO", 3),
    ("HIS", 3),
    ("BIO", 3),
    ("HBI", 3),
    ("CHE", 3),
    ("MAT", 4),
    ("PHY", 3),
    ("COM", 3),
    ("SPO", 2),
    ("MLA", 1),
]
FORM_SUBJECTS = {1: _JUNIOR, 2: _JUNIOR, 3: _FORM3, 4: _SENIOR, 5: _SENIOR}

TEACHERS = [
    ("Emmanuel", "Ndukong", "T001", ""),
    ("Gerald", "Ndimbo", "T002", "Ndimbo.png"),
    ("Pierre", "Sandjong", "T003", "Sandjong.png"),
    ("Delphis", "Tamnjong", "T004", "Tamnjong.png"),
    ("Honorine", "Tangiri", "T005", "Tangiri.png"),
    ("Vitalis", "Tantoh", "T006", "Tantoh.png"),
    ("Carine", "Vachia", "T007", "Vachia.png"),
    ("Solange", "Egbe", "T008", ""),
    ("Claudia", "Ngeh", "T009", "claudia.png"),
    ("Nelson", "Mokwe", "T010", ""),
    ("Brendaline", "Ateh", "T011", ""),
]

ASSIGNMENTS = {
    "T001": [
        ("F1", "MAT"),
        ("F1", "PHY"),
        ("F2", "MAT"),
        ("F2", "PHY"),
        ("F3", "MAT"),
        ("F3", "PHY"),
        ("F4", "MAT"),
        ("F4", "PHY"),
        ("F5", "MAT"),
        ("F5", "PHY"),
    ],
    "T002": [("F1", "FRE"), ("F2", "FRE"), ("F3", "FRE"), ("F4", "FRE"), ("F5", "FRE")],
    "T003": [("F1", "LIT"), ("F1", "ENL"), ("F2", "LIT"), ("F2", "ENL"), ("F5", "ENL")],
    "T004": [("F3", "ENL"), ("F4", "ENL"), ("F3", "LIT"), ("F4", "LIT"), ("F5", "LIT")],
    "T005": [("F1", "GEO"), ("F2", "GEO"), ("F1", "HIS"), ("F2", "HIS"), ("F3", "HIS")],
    "T006": [("F1", "CTZ"), ("F2", "CTZ"), ("F3", "CTZ"), ("F4", "HIS"), ("F5", "HIS")],
    "T007": [("F1", "BIO"), ("F2", "BIO"), ("F3", "BIO"), ("F1", "CHE"), ("F2", "CHE")],
    "T008": [
        ("F3", "CHE"),
        ("F4", "CHE"),
        ("F5", "CHE"),
        ("F4", "BIO"),
        ("F5", "BIO"),
        ("F4", "HBI"),
        ("F5", "HBI"),
    ],
    "T009": [("F3", "GEO"), ("F3", "ECO"), ("F4", "COM"), ("F5", "COM")],
    "T010": [("F4", "CTZ"), ("F5", "CTZ"), ("F4", "GEO"), ("F5", "GEO")],
    "T011": [
        ("F1", "SPO"),
        ("F2", "SPO"),
        ("F3", "SPO"),
        ("F4", "SPO"),
        ("F5", "SPO"),
        ("F1", "MLA"),
        ("F2", "MLA"),
        ("F3", "MLA"),
        ("F4", "MLA"),
        ("F5", "MLA"),
    ],
}

CLASS_MASTERS = {"F1": "T007", "F2": "T005", "F3": "T008", "F4": "T001", "F5": "T004"}

STUDENT_TARGETS = {1: 48, 2: 45, 3: 41, 4: 36, 5: 31}

NW_SURNAMES = [
    "Nfor",
    "Ngwa",
    "Fon",
    "Nkem",
    "Babila",
    "Mbah",
    "Tanyi",
    "Che",
    "Niba",
    "Fongang",
    "Kongnyuy",
    "Baleguel",
    "Fobuzie",
    "Awa",
    "Tanko",
    "Tifuh",
    "Ngu",
    "Kimbi",
    "Tabe",
    "Fusi",
    "Nsah",
    "Folem",
    "Bih",
    "Ngang",
    "Njei",
    "Yuni",
    "Nde",
    "Nkwi",
    "Toh",
    "Nsoh",
    "Fuo",
    "Ngam",
    "Fuam",
    "Fokum",
    "Mbang",
    "Ndikum",
    "Nchifor",
    "Tasi",
    "Nkweti",
    "Tah",
    "Waindim",
    "Fonyuy",
    "Nkwain",
    "Ndifor",
    "Anye",
    "Fru",
]
SW_SURNAMES = [
    "Egbe",
    "Mbella",
    "Njie",
    "Monono",
    "Ewane",
    "Ewusi",
    "Effiom",
    "Manga",
    "Namondo",
    "Mokwe",
    "Besong",
    "Elangwe",
    "Ekema",
    "Ndoko",
    "Nalova",
    "Efite",
    "Ngale",
    "Ayuk",
    "Takang",
    "Nkeng",
    "Metuge",
    "Eneke",
    "Anja",
    "Mokun",
    "Eno",
    "Bokwe",
    "Ndeley",
    "Oru",
]

GIVEN_MALE = [
    "Jude",
    "Anthony",
    "Desmond",
    "Elvis",
    "Collins",
    "Divine",
    "Bernards",
    "Roland",
    "Ebenezer",
    "Christopher",
    "Michael",
    "Daniel",
    "Samuel",
    "Peter",
    "Emmanuel",
    "George",
    "Francis",
    "Henry",
    "Isaac",
    "Joseph",
    "Patrick",
    "Vincent",
    "William",
    "Kingsley",
    "Blaise",
    "Clovis",
    "Bertrand",
    "Yannick",
    "Atem",
    "Arrey",
    "Eyong",
    "Ebot",
]
GIVEN_FEMALE = [
    "Noela",
    "Manka",
    "Yvonne",
    "Fridoline",
    "Brendaline",
    "Ngalim",
    "Precious",
    "Blessing",
    "Glory",
    "Doris",
    "Cynthia",
    "Bernice",
    "Edith",
    "Esther",
    "Faith",
    "Grace",
    "Joy",
    "Lucy",
    "Mary",
    "Naomi",
    "Patricia",
    "Rebecca",
    "Rose",
    "Ruth",
    "Sandra",
    "Tina",
    "Vanessa",
    "Emmanuella",
    "Carine",
    "Solange",
    "Honorine",
    "Delphine",
]

NW_DIVISIONS = {
    "Mezam": [
        "Bamenda I",
        "Bamenda II",
        "Bamenda III",
        "Bafut",
        "Santa",
        "Bali",
        "Tubah",
    ],
    "Bui": ["Kumbo", "Mbven", "Jakiri", "Nkum", "Noni"],
    "Momo": ["Mbengwi", "Batibo", "Widikum", "Njikwa"],
    "Ngoketunjia": ["Ndop", "Babessi", "Balikumbat"],
    "Boyo": ["Fundong", "Njinikom", "Belo", "Bum"],
    "Donga-Mantung": ["Ndu", "Nkambe", "Ako", "Nwa"],
    "Menchum": ["Wum", "Fungom", "Zhoa"],
}
SW_DIVISIONS = {
    "Fako": ["Buea", "Limbe", "Tiko", "Muyuka", "Idenau"],
    "Meme": ["Kumba", "Mbonge", "Konye", "Ekondo-Titi"],
    "Manyu": ["Mamfe", "Eyumojock", "Upper Bayang", "Akwaya"],
    "Ndian": ["Mundemba", "Bakassi", "Isangele"],
    "Kupe-Manengouba": ["Bangem", "Tombel"],
    "Lebialem": ["Menji", "Alou", "Wabane"],
}
NW_TOWNS = [
    "Bamenda",
    "Bafut",
    "Bali",
    "Ndop",
    "Kumbo",
    "Wum",
    "Fundong",
    "Ndu",
    "Batibo",
    "Mbengwi",
    "Nkambe",
    "Santa",
    "Jakiri",
    "Belo",
    "Njinikom",
    "Awing",
    "Bambili",
    "Bambui",
    "Nkwen",
    "Mankon",
]
SW_TOWNS = [
    "Buea",
    "Limbe",
    "Kumba",
    "Mamfe",
    "Tiko",
    "Muyuka",
    "Mbonge",
    "Mundemba",
    "Bangem",
    "Tombel",
    "Menji",
    "Ekondo-Titi",
    "Konye",
    "Mutengene",
]

BIRTH_YEAR_BASE = {1: 2013, 2: 2012, 3: 2011, 4: 2010, 5: 2009}


class Command(BaseCommand):
    help = (
        "Seed demo Form 1-5 classes, subject scheme, teachers and students "
        "(idempotent)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--school",
            type=int,
            default=None,
            help="Target school id. Defaults to the only school.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=SEED,
            help=f"Random seed (default {SEED}).",
        )

    def handle(self, *args, **options):
        if options["school"]:
            school = School.objects.filter(pk=options["school"]).first()
            if not school:
                raise CommandError(f"No school with id {options['school']}.")
        else:
            schools = School.objects.all()
            if schools.count() != 1:
                raise CommandError("Expected exactly one school; pass --school <id>.")
            school = schools.get()
        rng = random.Random(options["seed"])

        with transaction.atomic():
            classes = self._ensure_classes(school)
            terms = self._ensure_terms(school)
            current_term = terms[0]
            subjects = self._ensure_subjects(school)
            n_class_subjects = self._ensure_class_subjects(classes, subjects)
            teachers = self._ensure_teachers(school, rng)
            n_assignments, _masters = self._ensure_assignments(
                classes, subjects, teachers
            )
            n_students = self._ensure_students(school, classes, current_term, rng)

        self.stdout.write(self.style.SUCCESS(f"School: {school.name_en}"))
        self.stdout.write(
            self.style.SUCCESS(
                "Classes: " + ", ".join(str(c) for c in classes.values())
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Terms: "
                + ", ".join(str(t) for t in terms)
                + f" (current: {current_term})"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(f"Subjects: {len(subjects)} in catalogue.")
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Class-subject pairs: {n_class_subjects} new "
                f"({sum(len(v) for v in FORM_SUBJECTS.values())} total)."
            )
        )
        self.stdout.write(self.style.SUCCESS(f"Teachers: {len(teachers)}."))
        self.stdout.write(
            self.style.SUCCESS(
                f"Assignments: {n_assignments} new "
                f"({sum(len(v) for v in ASSIGNMENTS.values())} total)."
            )
        )
        for code, teacher_code in CLASS_MASTERS.items():
            t = teachers[teacher_code]
            self.stdout.write(f"  Class master {code}: {t}")
        self.stdout.write(self.style.SUCCESS(f"Students created: {n_students}."))
        for level in (1, 2, 3, 4, 5):
            count = Student.objects.filter(
                enrollments__school_class=classes[f"F{level}"],
                enrollments__academic_term=current_term,
                is_active=True,
            ).count()
            self.stdout.write(f"  F{level}: {count} students this term.")
        self.stdout.write(self.style.SUCCESS("Demo seeding complete."))

    def _ensure_classes(self, school) -> dict[str, SchoolClass]:
        classes = {}
        for level in (1, 2, 3, 4, 5):
            cls, _ = SchoolClass.objects.get_or_create(
                school=school,
                code=f"F{level}",
                stream="",
                defaults={
                    "name": f"Form {level}",
                    "cycle": "first",
                    "form_level": level,
                    "promotion_mark": 10.0,
                    "dismissal_mark": 6.0,
                    "sort_order": level,
                },
            )
            classes[f"F{level}"] = cls
        return classes

    def _ensure_terms(self, school) -> list[AcademicTerm]:
        terms = []
        for number in (1, 2, 3):
            term, _ = AcademicTerm.objects.get_or_create(
                school=school,
                term_number=number,
                year_start=2026,
                year_end=2027,
                defaults={"is_current": number == 1},
            )
            terms.append(term)
        if not AcademicTerm.objects.filter(school=school, is_current=True).exists():
            terms[0].is_current = True
            terms[0].save()
        return terms

    def _ensure_subjects(self, school) -> dict[str, Subject]:
        order = [
            "FRE",
            "LIT",
            "ENL",
            "CTZ",
            "GEO",
            "HIS",
            "ECO",
            "BIO",
            "HBI",
            "CHE",
            "MAT",
            "PHY",
            "COM",
            "SPO",
            "MLA",
        ]
        subjects = {}
        for index, code in enumerate(order, start=1):
            subject, _ = Subject.objects.get_or_create(
                school=school,
                code=code,
                defaults={"name": SUBJECT_NAMES[code], "sort_order": index},
            )
            subjects[code] = subject
        return subjects

    def _ensure_class_subjects(self, classes, subjects) -> int:
        created = 0
        for level in (1, 2, 3, 4, 5):
            for order, (code, coefficient) in enumerate(FORM_SUBJECTS[level], 1):
                _, was_created = ClassSubject.objects.get_or_create(
                    school_class=classes[f"F{level}"],
                    subject=subjects[code],
                    defaults={"coefficient": coefficient, "sort_order": order},
                )
                created += was_created
        return created

    def _ensure_teachers(self, school, rng) -> dict[str, Teacher]:
        teachers = {}
        for first, last, code, signature_file in TEACHERS:
            teacher, _ = Teacher.objects.get_or_create(
                school=school,
                teacher_code=code,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "email": f"{first.lower()}.{last.lower()}@gmail.com",
                    "phone": f"6{rng.randint(10_000_000, 99_999_999)}",
                },
            )
            if (
                signature_file
                and not teacher.signature
                and os.path.exists(
                    os.path.join(
                        settings.MEDIA_ROOT,
                        "teachers",
                        "signatures",
                        signature_file,
                    )
                )
            ):
                teacher.signature = f"teachers/signatures/{signature_file}"
                teacher.save()
            teachers[code] = teacher
        return teachers

    def _ensure_assignments(self, classes, subjects, teachers):
        created = 0
        for code, pairs in ASSIGNMENTS.items():
            teacher = teachers[code]
            for form_code, subject_code in pairs:
                _, was_created = TeacherAssignment.objects.get_or_create(
                    teacher=teacher,
                    school_class=classes[form_code],
                    subject=subjects[subject_code],
                    defaults={"is_class_master": False, "is_active": True},
                )
                created += was_created
        # Reset flags for these classes, then flag exactly one assignment
        # row per class so the class-master dashboard lists each class once.
        TeacherAssignment.objects.filter(school_class__in=classes.values()).update(
            is_class_master=False
        )
        for form_code, teacher_code in CLASS_MASTERS.items():
            row = (
                TeacherAssignment.objects.filter(
                    teacher=teachers[teacher_code],
                    school_class=classes[form_code],
                )
                .order_by("subject__sort_order")
                .first()
            )
            if row:
                row.is_class_master = True
                row.save()
        return created, CLASS_MASTERS

    def _ensure_students(self, school, classes, current_term, rng) -> int:
        created = 0
        for level in (1, 2, 3, 4, 5):
            cls = classes[f"F{level}"]
            enrolled = Student.objects.filter(
                enrollments__school_class=cls,
                enrollments__academic_term=current_term,
                is_active=True,
            ).count()
            shortfall = max(0, STUDENT_TARGETS[level] - enrolled)
            for _ in range(shortfall):
                student = self._make_student(school, level, rng)
                student.save()
                StudentEnrollment.objects.get_or_create(
                    student=student,
                    academic_term=current_term,
                    defaults={"school_class": cls},
                )
                created += 1
        return created

    def _make_student(self, school, level: int, rng) -> Student:
        is_south_west = rng.random() >= 0.55
        if is_south_west:
            region = "South West"
            surnames, divisions, towns = (
                SW_SURNAMES,
                SW_DIVISIONS,
                SW_TOWNS,
            )
        else:
            region = "North West"
            surnames, divisions, towns = (
                NW_SURNAMES,
                NW_DIVISIONS,
                NW_TOWNS,
            )
        sex = "F" if rng.random() < 0.52 else "M"
        given_pool = GIVEN_FEMALE if sex == "F" else GIVEN_MALE
        family = rng.choice(surnames)
        given = rng.sample(given_pool, 2)
        other_names = " ".join(given)
        unique_id = self._unique_id(rng)
        division, sub_divisions = rng.choice(list(divisions.items()))
        base_year = BIRTH_YEAR_BASE[level]
        year = rng.choice((base_year, base_year + 1, base_year + 1))
        town = rng.choice(towns)
        return Student(
            school=school,
            first_name=family,
            other_names=other_names,
            sex=sex,
            unique_id=unique_id,
            repeater=rng.random() < 0.12,
            date_of_birth=date(year, rng.randint(1, 12), rng.randint(1, 28)),
            place_of_birth=town,
            guardian_name=self._adult_name(family, sex, rng),
            guardian_contact=self._phone(rng),
            guardian_address=f"P.O. Box {rng.randint(1, 500)}, {town}",
            division_of_origin=division,
            sub_division_of_origin=rng.choice(sub_divisions),
            region_of_origin=region,
            father_name=self._adult_name(family, "M", rng),
            mother_name=self._adult_name(family, "F", rng),
            parent_contact=self._phone(rng),
            is_active=True,
        )

    def _unique_id(self, rng) -> str:
        used = set(Student.objects.values_list("unique_id", flat=True))
        unique_id = None
        while unique_id is None or unique_id in used:
            unique_id = f"{rng.randint(10_000_000, 99_999_999):09d}"
        return unique_id

    def _phone(self, rng) -> str:
        # Cameroon mobile: 9 digits starting with 6 (65/67/68/69 ranges).
        return (
            f"6{rng.choice(('5', '7', '8', '9'))}{rng.randint(1_000_000, 9_999_999)}"
        )

    def _adult_name(self, family: str, sex: str, rng) -> str:
        pool = GIVEN_FEMALE if sex == "F" else GIVEN_MALE
        title = "Mrs." if sex == "F" else "Mr."
        return f"{title} {rng.choice(pool)} {family}"

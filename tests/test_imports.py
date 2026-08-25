from datetime import date
from io import BytesIO

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from openpyxl import Workbook

from core.models import (
    AcademicTerm,
    School,
    SchoolClass,
    Student,
    StudentEnrollment,
    UserProfile,
)


def make_xlsx(rows):
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return SimpleUploadedFile(
        "students.xlsx",
        buf.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


HEADER = [
    "Register",
    "Name",
    "Sex",
    "Date of Birth",
    "Place of Birth",
    "Class",
    "Sub-Division",
]


@pytest.fixture
def import_data():
    school = School.objects.create(
        name_en="Test School",
        matricule="TEST001",
        region_en="South West",
        division_en="Fako",
    )
    SchoolClass.objects.create(school=school, name="Form 1", code="F1", form_level=1)
    term = AcademicTerm.objects.create(
        school=school, term_number=1, year_start=2025, year_end=2026, is_current=True
    )
    user = User.objects.create_user(username="admin", password="pass", is_staff=True)
    UserProfile.objects.create(user=user, school=school, role="admin")
    client = Client()
    client.login(username="admin", password="pass")
    return {"school": school, "term": term, "client": client}


def post_file(data, rows, term_id=""):
    return data["client"].post(
        reverse("import_students"),
        {
            "school": data["school"].id,
            "term": term_id,
            "file": make_xlsx([HEADER] + rows),
        },
    )


@pytest.mark.django_db
class TestImportPreview:
    def test_upload_shows_preview_without_committing(self, import_data):
        response = post_file(
            import_data,
            [
                ["100000001", "Efande Prisca", "F", "12/01/2010", "Buea", "F1", "Buea"],
                ["100000002", "Mbah Derick", "M", "05/06/2009", "Buea", "F1", "Buea"],
            ],
        )

        assert response.status_code == 200
        assert "Preview" in response.content.decode()
        assert Student.objects.count() == 0
        assert StudentEnrollment.objects.count() == 0

    def test_confirm_commits_from_preview(self, import_data):
        data = import_data
        post_file(
            data,
            [
                ["100000001", "Efande Prisca", "F", "12/01/2010", "Buea", "F1", "Buea"],
                ["100000002", "Mbah Derick", "M", "05/06/2009", "Buea", "F1", "Buea"],
            ],
        )

        response = data["client"].post(reverse("import_students"), {"confirm": "1"})

        assert response.status_code == 302
        assert Student.objects.count() == 2
        assert StudentEnrollment.objects.count() == 2
        student = Student.objects.get(unique_id="100000001")
        assert student.first_name == "Efande"
        assert student.sex == "F"

    def test_skipped_rows_reported_and_not_imported(self, import_data):
        data = import_data
        response = post_file(
            data,
            [
                ["100000001", "Efande Prisca", "F", "12/01/2010", "Buea", "F1", "Buea"],
                ["100000002", "Bad Sex", "X", "12/01/2010", "Buea", "F1", "Buea"],
                ["100000003", "Bad DOB", "M", "not-a-date", "Buea", "F1", "Buea"],
                [
                    "100000001",
                    "Duplicate Register",
                    "M",
                    "12/01/2010",
                    "Buea",
                    "F1",
                    "Buea",
                ],
            ],
        )

        html = response.content.decode()
        assert "skipped" in html
        assert "Invalid sex" in html
        assert "Invalid date of birth" in html
        assert "Duplicate register" in html

        data["client"].post(reverse("import_students"), {"confirm": "1"})
        assert Student.objects.count() == 1

    def test_cancel_discards_preview(self, import_data):
        data = import_data
        post_file(
            data,
            [
                ["100000001", "Efande Prisca", "F", "12/01/2010", "Buea", "F1", "Buea"],
            ],
        )

        data["client"].get(reverse("import_students") + "?cancel=1")
        response = data["client"].post(reverse("import_students"), {"confirm": "1"})

        assert response.status_code == 302
        assert Student.objects.count() == 0

    def test_existing_student_marked_in_preview(self, import_data):
        data = import_data
        Student.objects.create(
            school=data["school"],
            first_name="Old",
            sex="M",
            unique_id="100000001",
            date_of_birth=date(2010, 1, 1),
            place_of_birth="X",
            guardian_name="G",
            division_of_origin="D",
            region_of_origin="R",
        )

        response = post_file(
            data,
            [
                ["100000001", "Old Student", "M", "01/01/2010", "Buea", "F1", "Buea"],
            ],
        )

        html = response.content.decode()
        assert "Existing" in html
        assert "New" not in html.replace("New students", "")

    def test_unknown_class_shows_note(self, import_data):
        data = import_data
        response = post_file(
            data,
            [
                ["100000001", "Efande Prisca", "F", "12/01/2010", "Buea", "Z9", "Buea"],
            ],
        )

        html = response.content.decode()
        assert "not found" in html

        data["client"].post(reverse("import_students"), {"confirm": "1"})
        assert Student.objects.count() == 1
        assert StudentEnrollment.objects.count() == 0

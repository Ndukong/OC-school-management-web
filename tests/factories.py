"""Shared test data factories.

Import these directly in test modules::

    from tests.factories import make_admin, make_student, login_client

They replace the near-identical helper blocks that were copy-pasted across
test files. Prefer them over writing new local helpers.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import Client

from core.models import (
    AcademicTerm,
    License,
    School,
    SchoolClass,
    Student,
    UserProfile,
)

PASSWORD = "factory-pass"


def make_school(
    name: str = "Factory High", matricule: str = "FAC-001", **kwargs
) -> School:
    defaults = {
        "name_en": name,
        "matricule": matricule,
        "region_en": "North West",
        "division_en": "Mezam",
    }
    defaults.update(kwargs)
    return School.objects.create(**defaults)


def make_license(
    school: School,
    days: int = 365,
    max_students: int = 500,
    status: str = "active",
    product_key: str | None = None,
) -> License:
    return License.objects.create(
        product_key=product_key or f"OC-factory-{school.matricule}",
        school=school,
        school_name=school.name_en,
        max_students=max_students,
        expires_at=date.today() + timedelta(days=days),
        status=status,
    )


def make_school_with_license(name: str, matricule: str, **license_kwargs):
    """Return (school, license) with an active license attached."""
    school = make_school(name, matricule)
    return school, make_license(school, **license_kwargs)


def make_class(
    school: School,
    name: str = "Form 1",
    code: str = "F1",
    form_level: int = 1,
    **kwargs,
) -> SchoolClass:
    defaults = {
        "school": school,
        "name": name,
        "code": code,
        "form_level": form_level,
    }
    defaults.update(kwargs)
    return SchoolClass.objects.create(**defaults)


def make_term(
    school: School,
    term_number: int = 1,
    year_start: int = 2025,
    year_end: int = 2026,
    is_current: bool = True,
    **kwargs,
) -> AcademicTerm:
    defaults = {
        "school": school,
        "term_number": term_number,
        "year_start": year_start,
        "year_end": year_end,
        "is_current": is_current,
    }
    defaults.update(kwargs)
    return AcademicTerm.objects.create(**defaults)


def make_student(
    school: School,
    unique_id: str,
    first_name: str = "Testy",
    sex: str = "M",
    **kwargs,
) -> Student:
    defaults = {
        "school": school,
        "first_name": first_name,
        "sex": sex,
        "unique_id": unique_id,
        "date_of_birth": date(2010, 5, 5),
        "place_of_birth": "Bamenda",
        "guardian_name": "Guardian",
        "guardian_contact": "600000000",
        "division_of_origin": "Mezam",
        "region_of_origin": "North West",
    }
    defaults.update(kwargs)
    return Student.objects.create(**defaults)


def make_user(
    username: str,
    password: str = PASSWORD,
    school: School | None = None,
    role: str = "teacher",
    is_superuser: bool = False,
) -> User:
    """Create a user; attach a UserProfile when a school (or role) is given."""
    if is_superuser:
        user = User.objects.create_superuser(
            username=username, email=f"{username}@example.com", password=password
        )
        return user
    user = User.objects.create_user(username=username, password=password)
    if school is not None:
        UserProfile.objects.create(user=user, school=school, role=role)
    return user


def make_admin(username: str, school: School, role: str = "admin") -> User:
    return make_user(username, school=school, role=role)


def login_client(username: str, password: str = PASSWORD) -> Client:
    client = Client()
    assert client.login(username=username, password=password)
    return client

import pytest
from django.contrib.auth.models import User
from django.test import Client

from core.models import School, SchoolClass, Student, UserProfile


@pytest.fixture
def admin_user(db, school):
    u = User.objects.create_superuser("admin", "admin@example.com", "pass")
    UserProfile.objects.create(user=u, school=school, role="admin")
    return u


@pytest.fixture
def school(db):
    return School.objects.create(
        name_en="Test School", matricule="TEST", region_en="SW", division_en="Fako"
    )


@pytest.fixture
def school_class(db, school):
    return SchoolClass.objects.create(
        school=school, name="Form 1", code="F1", form_level=1, promotion_mark=8
    )


def make_student(school, i):
    return Student.objects.create(
        school=school,
        first_name=f"Student{i}",
        sex="M",
        unique_id=f"{i:09d}",
        date_of_birth="2010-01-01",
        place_of_birth="Buea",
        guardian_name="G",
        division_of_origin="Fako",
        region_of_origin="SW",
    )


@pytest.mark.django_db
def test_pagination_no_none_params(admin_user, school, school_class):
    for i in range(30):
        make_student(school, i)
    client = Client()
    client.force_login(admin_user)

    # The exact failing URL from the traceback
    resp = client.get(
        "/students/?page=6&q=&class=None&sex=None&per_page=25"
    )
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "class=None" not in html
    assert "sex=None" not in html

    # page 2 plain
    resp = client.get("/students/?page=2&per_page=25")
    assert resp.status_code == 200
    assert "class=None" not in resp.content.decode()


@pytest.mark.django_db
def test_pagination_class_filter(admin_user, school, school_class):
    make_student(school, 1)
    client = Client()
    client.force_login(admin_user)
    resp = client.get(f"/students/?page=1&class={school_class.id}&per_page=25")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_search_single_token_matches_any_field(admin_user, school):
    Student.objects.create(
        school=school, first_name="ADAMU", other_names="NOELA NSHINEH",
        sex="F", unique_id="100000001", date_of_birth="2010-01-01",
        place_of_birth="Buea", guardian_name="G", division_of_origin="Fako",
        region_of_origin="SW",
    )
    Student.objects.create(
        school=school, first_name="MAIRAMU", other_names="ADAMU FEKA",
        sex="M", unique_id="100000002", date_of_birth="2010-01-01",
        place_of_birth="Buea", guardian_name="G", division_of_origin="Fako",
        region_of_origin="SW",
    )
    Student.objects.create(
        school=school, first_name="KAMGA", sex="M", unique_id="100000003",
        date_of_birth="2010-01-01", place_of_birth="Buea", guardian_name="G",
        division_of_origin="Fako", region_of_origin="SW",
    )
    client = Client()
    client.force_login(admin_user)

    resp = client.get("/students/?q=adamu&per_page=25")
    html = resp.content.decode()
    assert "ADAMU NOELA NSHINEH" in html
    assert "MAIRAMU ADAMU FEKA" in html
    assert "KAMGA" not in html


@pytest.mark.django_db
def test_search_full_name_across_fields(admin_user, school):
    """Searching a full name spanning first_name + other_names must match."""
    Student.objects.create(
        school=school, first_name="ADAMU", other_names="NOELA NSHINEH",
        sex="F", unique_id="100000001", date_of_birth="2010-01-01",
        place_of_birth="Buea", guardian_name="G", division_of_origin="Fako",
        region_of_origin="SW",
    )
    Student.objects.create(
        school=school, first_name="MAIRAMU", other_names="ADAMU FEKA",
        sex="M", unique_id="100000002", date_of_birth="2010-01-01",
        place_of_birth="Buea", guardian_name="G", division_of_origin="Fako",
        region_of_origin="SW",
    )
    client = Client()
    client.force_login(admin_user)

    for q, expect in [
        ("ADAMU NOELA", "ADAMU NOELA NSHINEH"),
        ("FEKA ADAMU", "MAIRAMU ADAMU FEKA"),
        ("adamu noela nshineh", "ADAMU NOELA NSHINEH"),
    ]:
        resp = client.get(f"/students/?q={q.replace(' ', '+')}&per_page=25")
        html = resp.content.decode()
        assert expect in html, f"query {q!r} should match {expect!r}"
        assert "All Students" in html


@pytest.mark.django_db
def test_search_guardian_name(admin_user, school):
    Student.objects.create(
        school=school, first_name="BEN", sex="M", unique_id="100000001",
        date_of_birth="2010-01-01", place_of_birth="Buea",
        guardian_name="ADAMU MOUSSA", division_of_origin="Fako",
        region_of_origin="SW",
    )
    client = Client()
    client.force_login(admin_user)
    resp = client.get("/students/?q=MOUSSA&per_page=25")
    assert "BEN" in resp.content.decode()


@pytest.mark.django_db
def test_search_htmx_partial(admin_user, school):
    Student.objects.create(
        school=school, first_name="ADAMU", other_names="NOELA NSHINEH",
        sex="F", unique_id="100000001", date_of_birth="2010-01-01",
        place_of_birth="Buea", guardian_name="G", division_of_origin="Fako",
        region_of_origin="SW",
    )
    client = Client()
    client.force_login(admin_user)
    resp = client.get("/students/?q=ADAMU&per_page=25", HTTP_HX_REQUEST="true")
    html = resp.content.decode()
    assert 'id="students-results"' in html
    assert 'id="students-count" hx-swap-oob="outerHTML">1</span>' in html
    assert "ADAMU NOELA NSHINEH" in html


@pytest.mark.django_db
def test_teacher_pagination_robust(admin_user, school):
    from core.models import Teacher

    for i in range(30):
        Teacher.objects.create(
            school=school,
            first_name=f"Teach{i}",
            last_name="X",
            teacher_code=f"T{i:03d}",
        )
    client = Client()
    client.force_login(admin_user)

    for url in [
        "/teachers/?page=2&per_page=25",
        "/teachers/?page=abc&per_page=25",
        "/teachers/?page=999&per_page=25",
        "/teachers/?page=2&q=Teach&per_page=10",
    ]:
        resp = client.get(url)
        assert resp.status_code == 200
        html = resp.content.decode()
        assert "None" not in html.replace("None of", "")

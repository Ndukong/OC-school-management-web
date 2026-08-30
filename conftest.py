import os

import pytest

os.environ.pop("DATABASE_URL", None)
os.environ.setdefault("DJANGO_DEBUG", "False")
os.environ.setdefault("DJANGO_SECRET_KEY", "pytest-only-django-secret-key")
os.environ.setdefault("LICENSE_SECRET_KEY", "pytest-only-license-secret")
os.environ.setdefault("ALLOWED_HOSTS", "testserver,localhost,127.0.0.1")


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """Throttle counters live in the cache; clear them between tests."""
    yield
    from django.core.cache import cache

    cache.clear()


@pytest.fixture
def school(db):
    """A bare school."""
    from tests.factories import make_school

    return make_school()


@pytest.fixture
def licensed_school(db):
    """A school with an active license attached."""
    from tests.factories import make_school_with_license

    return make_school_with_license("Fixture High", "FIX-001")[0]

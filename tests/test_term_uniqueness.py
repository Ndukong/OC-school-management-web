"""One current term per school: save-guard + DB constraint."""


from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase

from core.models import AcademicTerm, School


class TermUniquenessTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name_en="Term School", matricule="TU-1", region_en="SW", division_en="Fako"
        )

    def _make(self, number, year_start, year_end, current):
        return AcademicTerm.objects.create(
            school=self.school,
            term_number=number,
            year_start=year_start,
            year_end=year_end,
            is_current=current,
        )

    def test_saving_current_term_unsets_the_previous_one(self):
        first = self._make(1, 2025, 2026, True)
        second = self._make(1, 2026, 2027, True)

        first.refresh_from_db()
        self.assertFalse(first.is_current)
        self.assertTrue(second.is_current)

    def test_only_one_current_term_remains(self):
        self._make(1, 2025, 2026, True)
        self._make(2, 2025, 2026, True)
        self._make(3, 2025, 2026, True)

        current = AcademicTerm.objects.filter(school=self.school, is_current=True)
        self.assertEqual(current.count(), 1)


class TermConstraintTests(TransactionTestCase):
    def test_database_constraint_blocks_two_current_terms(self):
        school = School.objects.create(
            name_en="Constraint School",
            matricule="TU-2",
            region_en="SW",
            division_en="Fako",
        )
        AcademicTerm.objects.create(
            school=school,
            term_number=1,
            year_start=2025,
            year_end=2026,
            is_current=True,
        )
        second = AcademicTerm.objects.create(
            school=school,
            term_number=1,
            year_start=2026,
            year_end=2027,
            is_current=False,
        )
        # .update() bypasses save() and its guard - the DB constraint is the
        # last line of defense for raw/bulk paths.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AcademicTerm.objects.filter(pk=second.pk).update(is_current=True)

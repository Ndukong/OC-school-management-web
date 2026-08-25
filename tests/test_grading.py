from decimal import Decimal

from core.utils.grading import (
    compute_grade,
    compute_promotion_decision,
    compute_remark,
    compute_subject_average,
    compute_term_remark,
    compute_term_total,
    is_pass,
)


class TestGrading:
    def test_compute_grade_a_plus(self):
        assert compute_grade(Decimal(18)) == "A+"
        assert compute_grade(Decimal("19.5")) == "A+"
        assert compute_grade(Decimal(20)) == "A+"

    def test_compute_grade_a(self):
        assert compute_grade(Decimal(16)) == "A"
        assert compute_grade(Decimal(17)) == "A"

    def test_compute_grade_b_plus(self):
        assert compute_grade(Decimal(15)) == "B+"
        assert compute_grade(Decimal("15.5")) == "B+"

    def test_compute_grade_b(self):
        assert compute_grade(Decimal(14)) == "B"
        assert compute_grade(Decimal("14.9")) == "B"

    def test_compute_grade_c_plus(self):
        assert compute_grade(Decimal(12)) == "C+"
        assert compute_grade(Decimal(13)) == "C+"

    def test_compute_grade_c(self):
        assert compute_grade(Decimal(10)) == "C"
        assert compute_grade(Decimal(11)) == "C"

    def test_compute_grade_d(self):
        assert compute_grade(Decimal(0)) == "D"
        assert compute_grade(Decimal(5)) == "D"
        assert compute_grade(Decimal("9.99")) == "D"

    def test_compute_remark_cvwa(self):
        assert compute_remark(Decimal(16)) == "CVWA"
        assert compute_remark(Decimal(18)) == "CVWA"

    def test_compute_remark_cwa(self):
        assert compute_remark(Decimal(14)) == "CWA"
        assert compute_remark(Decimal(15)) == "CWA"

    def test_compute_remark_ca(self):
        assert compute_remark(Decimal(12)) == "CA"
        assert compute_remark(Decimal(13)) == "CA"

    def test_compute_remark_caa(self):
        assert compute_remark(Decimal(10)) == "CAA"
        assert compute_remark(Decimal(11)) == "CAA"

    def test_compute_remark_cna(self):
        assert compute_remark(Decimal(0)) == "CNA"
        assert compute_remark(Decimal("9.99")) == "CNA"

    def test_is_pass(self):
        assert is_pass(Decimal(10))
        assert is_pass(Decimal(15))
        assert not is_pass(Decimal("9.99"))
        assert not is_pass(Decimal(0))

    def test_compute_term_remark(self):
        assert compute_term_remark(Decimal(10)) == "P"
        assert compute_term_remark(Decimal(15)) == "P"
        assert compute_term_remark(Decimal("9.99")) == "F"
        assert compute_term_remark(Decimal(0)) == "F"

    def test_compute_subject_average(self):
        scores = [Decimal(12), Decimal(14), Decimal(16)]
        avg = compute_subject_average(scores)
        assert avg == Decimal("14.00")

    def test_compute_subject_average_empty(self):
        assert compute_subject_average([]) is None

    def test_compute_subject_average_single(self):
        assert compute_subject_average([Decimal(15)]) == Decimal("15.00")

    def test_compute_term_total(self):
        data = [(Decimal(12), 2), (Decimal(14), 3), (Decimal(16), 1)]
        weighted, coef, avg = compute_term_total(data)
        assert weighted == Decimal(12) * 2 + Decimal(14) * 3 + Decimal(16) * 1
        assert coef == 6
        assert avg == (weighted / Decimal(coef)).quantize(Decimal("0.01"))

    def test_compute_term_total_empty(self):
        weighted, coef, avg = compute_term_total([])
        assert weighted == Decimal(0)
        assert coef == 0
        assert avg == Decimal(0)

    def test_compute_promotion_promoted(self):
        assert compute_promotion_decision(Decimal(12), Decimal(10)) == "PROMOTED"

    def test_compute_promotion_by_clemency(self):
        decision = compute_promotion_decision(Decimal("9.5"), Decimal(8))
        assert decision == "PROMOTED BY CLEMENCY OF COUNCIL"

    def test_compute_promotion_repeat(self):
        decision = compute_promotion_decision(Decimal(7), Decimal(8))
        assert decision == "REPEAT"

    def test_compute_promotion_external_exam_class(self):
        assert compute_promotion_decision(Decimal(5), Decimal(10), is_external_exam_class=True) == ""

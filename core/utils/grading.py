from decimal import Decimal

MIN_SCORE = Decimal(0)
MAX_SCORE = Decimal(20)
PASS_MARK = Decimal(10)


def compute_grade(average: Decimal) -> str:
    if average >= Decimal(18):
        return "A+"
    elif average >= Decimal(16):
        return "A"
    elif average >= Decimal(15):
        return "B+"
    elif average >= Decimal(14):
        return "B"
    elif average >= Decimal(12):
        return "C+"
    elif average >= Decimal(10):
        return "C"
    else:
        return "D"


def compute_remark(average: Decimal) -> str:
    if average >= Decimal(16):
        return "CVWA"
    elif average >= Decimal(14):
        return "CWA"
    elif average >= Decimal(12):
        return "CA"
    elif average >= Decimal(10):
        return "CAA"
    else:
        return "CNA"


def is_pass(average: Decimal) -> bool:
    return average >= PASS_MARK


def compute_term_remark(average: Decimal) -> str:
    return "P" if is_pass(average) else "F"


def compute_promotion_decision(
    average: Decimal,
    promotion_mark: Decimal,
    is_external_exam_class: bool = False,
    dismissal_mark: Decimal | None = None,
) -> str:
    if is_external_exam_class:
        return ""
    if average >= PASS_MARK:
        return "PROMOTED"
    elif average >= promotion_mark:
        return "PROMOTED BY CLEMENCY OF COUNCIL"
    elif dismissal_mark is not None and average < dismissal_mark:
        return "DISMISSED"
    else:
        return "REPEAT"


def compute_subject_average(
    competency_scores: list[Decimal],
) -> Decimal | None:
    if not competency_scores:
        return None
    total = sum(competency_scores, Decimal(0))
    return (total / len(competency_scores)).quantize(Decimal("0.01"))


def compute_term_total(
    subject_averages: list[tuple[Decimal, int]]
) -> tuple[Decimal, int, Decimal]:
    total_weighted = Decimal(0)
    total_coef = 0
    for avg, coef in subject_averages:
        if avg is not None:
            total_weighted += avg * Decimal(coef)
            total_coef += coef
    overall = (
        (total_weighted / Decimal(total_coef)).quantize(Decimal("0.01"))
        if total_coef > 0
        else Decimal(0)
    )
    return total_weighted, total_coef, overall

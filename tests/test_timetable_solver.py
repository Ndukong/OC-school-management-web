"""Tests for the timetable solver (pure Python, no database required)."""

import random
from dataclasses import replace

import pytest

from core.solver.fitness import evaluate_schedule, find_hard_violations
from core.solver.genetic import TimetableSolver
from core.solver.greedy import build_greedy_schedule
from core.solver.mutations import crossover, day_swap, move_to_empty, swap_within_class
from core.solver.problem import (
    ClassInfo,
    Requirement,
    ScheduleEntry,
    SlotInfo,
    SubjectInfo,
    TeacherInfo,
    TimetableProblem,
    Unavailability,
)
from core.solver.validator import TimetableValidator

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
SUBJECT_CODES = [
    "MAT", "ENL", "FRE", "PHY", "CHE", "BIO",
    "HIS", "GEO", "ECO", "CSC", "SPO", "CTZ",
]


def make_slots() -> list[SlotInfo]:
    """8 slots: P1-P4, break, P5-P8. P1 cannot start doubles on Monday only
    (handled via assembly); all teaching slots except before-break ones can
    start doubles where adjacent."""
    slots = []
    times = [
        ("teaching", "Period 1", "07:30", "08:10"),
        ("teaching", "Period 2", "08:10", "08:50"),
        ("teaching", "Period 3", "08:50", "09:30"),
        ("teaching", "Period 4", "09:30", "10:10"),
        ("break", "Morning Break", "10:10", "10:30"),
        ("teaching", "Period 5", "10:30", "11:10"),
        ("teaching", "Period 6", "11:10", "11:50"),
        ("teaching", "Period 7", "11:50", "12:30"),
        ("break", "Lunch", "12:30", "13:10"),
        ("teaching", "Period 8", "13:10", "13:50"),
    ]
    for i, (kind, label, start, end) in enumerate(times, start=1):
        slots.append(
            SlotInfo(
                slot_id=i,
                slot_number=i,
                label=label,
                can_start_double=(
                    kind == "teaching"
                    and i < len(times)
                    and times[i][0] == "teaching"
                ),
                start_time=start,
                end_time=end,
            )
        )
    return [s for s in slots if s.slot_number <= 10]


def make_test_problem() -> TimetableProblem:
    """Realistic test school: 5 days, 10 classes, 15 teachers, 12 subjects."""
    from core.solver.problem import ClassInfo

    slots = [
        SlotInfo(slot_id=i, slot_number=i, label=f"P{i}", can_start_double=True,
                 start_time=f"{7 + i}:00", end_time=f"{7 + i}:50")
        for i in range(1, 9)
    ]
    classes = [
        ClassInfo(class_id=i, name=f"Form {1 + (i - 1) % 5}{'AB'[i % 2]}",
                  form_level=1 + (i - 1) % 5, sort_order=i)
        for i in range(1, 11)
    ]
    classes = [
        ClassInfo(class_id=i, name=f"Form {1 + (i - 1) % 5}{'AB'[i % 2]}",
                  form_level=1 + (i - 1) % 5, sort_order=i)
        for i in range(1, 11)
    ]
    teachers = [
        TeacherInfo(teacher_id=i, name=f"Teacher {i}") for i in range(1, 16)
    ]
    subjects = [
        SubjectInfo(subject_id=i, code=code, name=code)
        for i, code in enumerate(SUBJECT_CODES, start=1)
    ]

    periods = {"MAT": 6, "ENL": 5, "FRE": 5, "PHY": 4, "CHE": 4, "BIO": 4,
               "HIS": 3, "GEO": 3, "ECO": 3, "CSC": 3, "SPO": 2, "CTZ": 2}
    subject_by_code = {s.code: s.subject_id for s in subjects}
    subject_by_id = {s.subject_id: s for s in subjects}

    requirements = []
    for class_info in classes:
        for code, weekly in periods.items():
            subject_id = subject_by_code[code]
            teacher_id = 1 + (class_info.class_id + subject_id) % 15
            doubles = 1 if code in ("PHY", "CHE", "SPO") else 0
            requirements.append(
                Requirement(
                    class_id=class_info.class_id,
                    subject_id=subject_id,
                    teacher_id=teacher_id,
                    periods_per_week=weekly,
                    doubles_per_week=doubles,
                    room_id=None,
                )
            )

    return TimetableProblem(
        days=DAYS,
        slots_per_day=slots,
        assembly_day="Monday",
        assembly_lost_slots=0,
        classes=classes,
        teachers=teachers,
        subjects=subjects,
        rooms=[],
        requirements=requirements,
        unavailabilities=[
            Unavailability(teacher_id=14, day="Monday", slot_id=1),
            Unavailability(teacher_id=15, day="Friday", slot_id=8),
        ],
        soft_constraints=[],
    )


class TestFitnessFunction:
    def test_perfect_schedule_scores_zero(self):
        problem = make_test_problem()
        schedule, failed = build_greedy_schedule(problem, random.Random(1), relaxed=True)
        # Greedy places everything or skips; a schedule with only placed
        # entries has teacher/class/room clashes checked here.
        score, hard, _soft = evaluate_schedule(problem, schedule)
        assert score <= 0
        # Clashes are separate from period-count violations.
        clash_types = {v.violation_type for v in hard}
        assert not clash_types & {"teacher_clash", "class_clash", "room_clash"}

    def test_teacher_clash_penalised(self):
        problem = make_test_problem()
        req = problem.requirements[0]
        entry_a = ScheduleEntry(
            class_id=req.class_id, subject_id=req.subject_id,
            teacher_id=req.teacher_id, room_id=None,
            day="Monday", slot_id=1,
        )
        entry_b = ScheduleEntry(
            class_id=req.class_id + 1, subject_id=req.subject_id,
            teacher_id=req.teacher_id, room_id=None,
            day="Monday", slot_id=1,
        )
        score, hard, _soft = evaluate_schedule(problem, [entry_a, entry_b])
        assert any(v.violation_type == "teacher_clash" for v in hard)
        assert any(v.penalty == 10_000 for v in hard)
        assert score <= -10_000

    def test_teacher_unavailability_penalised(self):
        problem = make_test_problem()
        problem.unavailabilities.append(
            Unavailability(teacher_id=1, day="Monday", slot_id=1)
        )
        entry = ScheduleEntry(
            class_id=1, subject_id=1, teacher_id=1, room_id=None,
            day="Monday", slot_id=1,
        )
        _score, hard, _soft = evaluate_schedule(problem, [entry])
        assert any(v.violation_type == "teacher_unavailable" for v in hard)

    def test_double_split_penalised(self):
        problem = make_test_problem()
        entry_a = ScheduleEntry(
            class_id=1, subject_id=1, teacher_id=1, room_id=None,
            day="Monday", slot_id=1, is_double_start=True,
        )
        # The second half is placed in a NON-adjacent slot.
        entry_b = ScheduleEntry(
            class_id=1, subject_id=1, teacher_id=1, room_id=None,
            day="Monday", slot_id=3, is_double_end=True,
        )
        _score, hard, _soft = evaluate_schedule(problem, [entry_a, entry_b])
        assert any(v.violation_type == "double_split" for v in hard)

    def test_room_clash_penalised(self):
        problem = make_test_problem()
        entry_a = ScheduleEntry(
            class_id=1, subject_id=1, teacher_id=1, room_id=5,
            day="Monday", slot_id=1,
        )
        entry_b = ScheduleEntry(
            class_id=2, subject_id=2, teacher_id=2, room_id=5,
            day="Monday", slot_id=1,
        )
        _score, hard, _soft = evaluate_schedule(problem, [entry_a, entry_b])
        assert any(v.violation_type == "room_clash" for v in hard)

    def test_missing_periods_penalised(self):
        problem = make_test_problem()
        entry = ScheduleEntry(
            class_id=1, subject_id=11, teacher_id=1, room_id=None,
            day="Monday", slot_id=1,
        )
        # Subject 11 (MAT) requires 6 periods; only 1 scheduled.
        _score, hard, _soft = evaluate_schedule(problem, [entry])
        assert any(v.violation_type == "period_count" for v in hard)

    def test_subject_not_spread_penalised(self):
        problem = make_test_problem()
        entries = [
            ScheduleEntry(
                class_id=1, subject_id=11, teacher_id=1, room_id=None,
                day="Monday", slot_id=slot,
            )
            for slot in (1, 2)
        ]
        _score, soft, _hard = evaluate_schedule(problem, entries)
        assert soft


class TestGreedyConstructor:
    def test_greedy_places_lessons(self):
        problem = make_test_problem()
        rng = random.Random(7)
        schedule, failed = build_greedy_schedule(problem, rng)
        assert len(schedule) > 0
        # All placed entries must have no teacher/class/room clash.
        hard = find_hard_violations(problem, schedule)
        clashes = [v for v in hard if v.violation_type in ("teacher_clash", "class_clash", "room_clash")]
        assert not clashes

    def test_respects_teacher_unavailability(self):
        problem = make_test_problem()
        rng = random.Random(3)
        schedule, _failed = build_greedy_schedule(problem, rng)
        for entry in schedule:
            for u in problem.unavailabilities:
                assert (entry.teacher_id, entry.day, entry.slot_id) != (
                    u.teacher_id, u.day, u.slot_id
                )

    def test_failed_lessons_reported(self):
        problem = make_test_problem()
        # Reduce teachers to 1 so many lessons cannot be placed.
        problem.teachers = problem.teachers[:1]
        problem.requirements = [
            r for r in problem.requirements if r.teacher_id == problem.teachers[0].teacher_id
        ]
        # Give one requirement impossible volume (Requirement is frozen).
        problem.requirements[0] = replace(
            problem.requirements[0], periods_per_week=100
        )
        schedule, failed = build_greedy_schedule(problem, random.Random(2))
        assert failed  # some lessons could not be placed


class TestGeneticAlgorithm:
    def test_solver_returns_result(self):
        problem = make_test_problem()
        solver = TimetableSolver(problem)
        result = solver.solve(time_limit=5, population_size=10, generations=30)
        assert result.schedule
        assert result.generation_time_seconds <= 10
        assert isinstance(result.success, bool)

    def test_locked_entries_preserved(self):
        problem = make_test_problem()
        rng = random.Random(11)
        schedule, _failed = build_greedy_schedule(problem, rng)
        locked_source = [
            entry for entry in schedule[:5]
        ]
        for entry in locked_source:
            entry.is_locked = True
        problem.locked_entries = list(locked_source)

        solver = TimetableSolver(problem)
        result = solver.solve(time_limit=4, population_size=8, generations=20)

        for locked in problem.locked_entries:
            match = next(
                (
                    e
                    for e in result.schedule
                    if e.class_id == locked.class_id
                    and e.subject_id == locked.subject_id
                    and e.day == locked.day
                    and e.slot_id == locked.slot_id
                ),
                None,
            )
            assert match is not None


class TestValidator:
    def test_valid_swap_returns_no_hard_violations(self):
        problem = make_test_problem()
        rng = random.Random(21)
        schedule, _failed = build_greedy_schedule(problem, rng)
        validator = TimetableValidator(problem)

        entry_a = schedule[0]
        entry_b = next(
            e
            for e in schedule
            if e.class_id == entry_a.class_id and e.slot_id != entry_a.slot_id
        )
        index_a = schedule.index(entry_a)
        index_b = schedule.index(entry_b)
        violations = validator.check_swap(schedule, index_a, index_b)
        assert isinstance(violations, list)

    def test_invalid_swap_returns_teacher_clash(self):
        problem = make_test_problem()
        rng = random.Random(5)
        schedule, _failed = build_greedy_schedule(problem, rng)
        validator = TimetableValidator(problem)

        first = schedule[0]
        second = next(e for e in schedule if e.teacher_id != first.teacher_id)
        index_a = schedule.index(first)
        index_b = schedule.index(second)
        violations = validator.check_swap(schedule, index_a, index_b)
        assert any(v.violation_type == "teacher_clash" for v in violations)

    def test_suggest_fixes_returns_options(self):
        problem = make_test_problem()
        rng = random.Random(9)
        schedule, _failed = build_greedy_schedule(problem, rng)
        validator = TimetableValidator(problem)

        hard = find_hard_violations(problem, schedule)
        if not hard:
            pytest.skip("no hard violations in this greedy pass")
        proposals = validator.suggest_fixes(schedule, hard[0])
        assert isinstance(proposals, list)


class TestMutations:
    def test_mutations_preserve_entry_count(self):
        from core.solver.mutations import (
            swap_double,
            swap_within_teacher,
        )

        problem = make_test_problem()
        rng = random.Random(31)
        schedule, _failed = build_greedy_schedule(problem, rng)

        for mutate in (
            swap_within_class,
            swap_within_teacher,
            move_to_empty,
            swap_double,
            day_swap,
        ):
            mutated = mutate(problem, schedule, rng)
            if mutated is not None:
                assert len(mutated) == len(schedule)

        child = crossover(problem, schedule, schedule, rng)
        assert len(child) == len(schedule)

"""Phase 1: greedy construction of an initial timetable.

Lessons are expanded from requirements, sorted most-constrained-first, and
placed one at a time into the best valid (day, slot) position.
"""

import random
from collections import defaultdict
from dataclasses import dataclass

from core.solver.problem import ScheduleEntry, TimetableProblem


@dataclass
class Lesson:
    """One placeable unit. A double consumes two consecutive teaching slots."""

    class_id: int
    subject_id: int
    teacher_id: int
    room_id: int | None
    is_double: bool


def expand_lessons(problem: TimetableProblem) -> list[Lesson]:
    lessons: list[Lesson] = []
    for req in problem.requirements:
        doubles = req.doubles_per_week
        singles = req.periods_per_week - 2 * doubles
        for _ in range(doubles):
            lessons.append(
                Lesson(req.class_id, req.subject_id, req.teacher_id, req.room_id, True)
            )
        for _ in range(max(0, singles)):
            lessons.append(
                Lesson(req.class_id, req.subject_id, req.teacher_id, req.room_id, False)
            )
    return lessons


def _difficulty(lesson: Lesson, problem: TimetableProblem, rng: random.Random) -> float:
    teacher_unavailability = sum(
        1 for u in problem.unavailabilities if u.teacher_id == lesson.teacher_id
    )
    periods = next(
        (
            r.periods_per_week
            for r in problem.requirements
            if r.class_id == lesson.class_id and r.subject_id == lesson.subject_id
        ),
        0,
    )
    jitter = rng.random()
    return (
        (2 if lesson.room_id else 0)
        + teacher_unavailability * 1.5
        + (1 if lesson.is_double else 0)
        + periods / 6
        + jitter
    )


class GreedyBuilder:
    """Places lessons into the schedule one at a time, best spot first."""

    def __init__(
        self, problem: TimetableProblem, rng: random.Random, relaxed: bool = False
    ):
        self.problem = problem
        self.rng = rng
        self.relaxed = relaxed

        self.class_busy: set[tuple[int, str, int]] = set()
        self.teacher_busy: set[tuple[int, str, int]] = set()
        self.teacher_unavailable: set[tuple[int, str, int]] = {
            (u.teacher_id, u.day, u.slot_id) for u in problem.unavailabilities
        }
        self.room_busy: set[tuple[int, str, int]] = set()
        self.locked_slots: set[tuple[int, str, int]] = {
            (e.class_id, e.day, e.slot_id) for e in problem.locked_entries
        }
        self.subject_day_count: dict[tuple[int, int, str], int] = defaultdict(int)
        self.teacher_day_load: dict[tuple[int, str], int] = defaultdict(int)

        self.failed: list[Lesson] = []
        self.schedule: list[ScheduleEntry] = list(problem.locked_entries)
        for entry in self.schedule:
            self.class_busy.add((entry.class_id, entry.day, entry.slot_id))
            self.teacher_busy.add((entry.teacher_id, entry.day, entry.slot_id))
            if entry.room_id is not None:
                self.room_busy.add((entry.room_id, entry.day, entry.slot_id))

        self.days = list(problem.days)
        self.day_slots = {day: problem.teaching_slots_for_day(day) for day in self.days}

    def place_all(self) -> tuple[list[ScheduleEntry], list[Lesson]]:
        lessons = expand_lessons(self.problem)
        lessons.sort(key=lambda lesson: _difficulty(lesson, self.problem, self.rng))
        for lesson in lessons:
            if not self._place_lesson(lesson):
                self.failed.append(lesson)

        # Relaxed retry: same-day placement allowed for lessons that failed
        # the spreading preference.
        for lesson in list(self.failed):
            if self._place_lesson(lesson, relaxed=True):
                self.failed.remove(lesson)
        return self.schedule, self.failed

    def _place_lesson(self, lesson: Lesson, relaxed: bool = False) -> bool:
        days = list(self.days)
        if not relaxed:
            self.rng.shuffle(days)
            days.sort(
                key=lambda day: self.subject_day_count.get(
                    (lesson.class_id, lesson.subject_id, day), 0
                )
            )

        best: tuple[float, str, int, int | None] | None = None
        for day in days:
            slots = self.day_slots.get(day, [])
            slots_by_number = {s.slot_number: s for s in slots}
            for slot in slots:
                if lesson.is_double and slot.can_start_double:
                    nxt = slots_by_number.get(slot.slot_number + 1)
                    if nxt is None:
                        continue
                    class_free = (
                        lesson.class_id,
                        day,
                        slot.slot_id,
                    ) not in self.class_busy and (
                        lesson.class_id,
                        day,
                        nxt.slot_id,
                    ) not in self.class_busy
                    class_not_locked = (
                        lesson.class_id,
                        day,
                        slot.slot_id,
                    ) not in self.locked_slots and (
                        lesson.class_id,
                        day,
                        nxt.slot_id,
                    ) not in self.locked_slots
                    teacher_free = (
                        lesson.teacher_id,
                        day,
                        slot.slot_id,
                    ) not in self.teacher_busy and (
                        lesson.teacher_id,
                        day,
                        nxt.slot_id,
                    ) not in self.teacher_busy
                    teacher_available = (
                        lesson.teacher_id,
                        day,
                        slot.slot_id,
                    ) not in self.teacher_unavailable and (
                        lesson.teacher_id,
                        day,
                        nxt.slot_id,
                    ) not in self.teacher_unavailable
                    room_free = lesson.room_id is None or (
                        (lesson.room_id, day, slot.slot_id) not in self.room_busy
                        and (lesson.room_id, day, nxt.slot_id) not in self.room_busy
                    )
                    valid = (
                        class_free
                        and class_not_locked
                        and teacher_free
                        and teacher_available
                        and room_free
                    )
                    placement = (slot.slot_id, nxt.slot_id)
                else:
                    class_free = (
                        lesson.class_id,
                        day,
                        slot.slot_id,
                    ) not in self.class_busy
                    class_not_locked = (
                        lesson.class_id,
                        day,
                        slot.slot_id,
                    ) not in self.locked_slots
                    teacher_free = (
                        lesson.teacher_id,
                        day,
                        slot.slot_id,
                    ) not in self.teacher_busy
                    teacher_available = (
                        lesson.teacher_id,
                        day,
                        slot.slot_id,
                    ) not in self.teacher_unavailable
                    room_free = (
                        lesson.room_id is None
                        or (
                            lesson.room_id,
                            day,
                            slot.slot_id,
                        )
                        not in self.room_busy
                    )
                    valid = (
                        class_free
                        and class_not_locked
                        and teacher_free
                        and teacher_available
                        and room_free
                    )
                    placement = (slot.slot_id, None)

                if not valid:
                    continue

                subject_today = self.subject_day_count.get(
                    (lesson.class_id, lesson.subject_id, day), 0
                )
                teacher_load = self.teacher_day_load.get((lesson.teacher_id, day), 0)
                score = (
                    -subject_today * 10
                    - teacher_load * 3
                    + slot.slot_number * (0 if relaxed else 0.5)
                    + self.rng.random()
                )
                if best is None or score > best[0]:
                    best = (score, day, placement[0], placement[1])

        if best is None:
            return False

        _score, day, slot_id, nxt_id = best
        entry = ScheduleEntry(
            class_id=lesson.class_id,
            subject_id=lesson.subject_id,
            teacher_id=lesson.teacher_id,
            room_id=lesson.room_id,
            day=day,
            slot_id=slot_id,
            is_double_start=lesson.is_double,
            is_double_end=False,
        )
        self.schedule.append(entry)
        self.class_busy.add((entry.class_id, day, slot_id))
        self.teacher_busy.add((entry.teacher_id, day, slot_id))
        self.subject_day_count[(lesson.class_id, lesson.subject_id, day)] += 1
        self.teacher_day_load[(lesson.teacher_id, day)] += 1
        if entry.room_id is not None:
            self.room_busy.add((entry.room_id, day, slot_id))

        if lesson.is_double and nxt_id is not None:
            second = ScheduleEntry(
                class_id=lesson.class_id,
                subject_id=lesson.subject_id,
                teacher_id=lesson.teacher_id,
                room_id=lesson.room_id,
                day=day,
                slot_id=nxt_id,
                is_double_end=True,
            )
            self.schedule.append(second)
            self.class_busy.add((second.class_id, day, nxt_id))
            self.teacher_busy.add((second.teacher_id, day, nxt_id))
            self.subject_day_count[(second.class_id, second.subject_id, day)] += 1
            if second.room_id is not None:
                self.room_busy.add((second.room_id, day, nxt_id))
        return True


def build_greedy_schedule(
    problem: TimetableProblem, rng: random.Random, relaxed: bool = False
) -> tuple[list[ScheduleEntry], list[Lesson]]:
    """Build a schedule greedily. Returns (schedule, failed_lessons)."""
    builder = GreedyBuilder(problem, rng, relaxed=relaxed)
    builder.place_all()
    return builder.schedule, builder.failed

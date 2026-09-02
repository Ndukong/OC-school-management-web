"""Fitness scoring for candidate timetables.

Single pass builds lookup indexes; a second pass finds hard violations;
a third applies the soft penalty table. Lower score = better (0 = perfect).
"""

from collections import defaultdict

from core.solver.problem import ScheduleEntry, TimetableProblem, Violation

PENALTY_TEACHER_CLASH = 10_000.0
PENALTY_CLASS_CLASH = 10_000.0
PENALTY_ROOM_CLASH = 10_000.0
PENALTY_UNAVAILABLE = 10_000.0
PENALTY_PERIOD_COUNT = 5_000.0
PENALTY_DOUBLE_SPLIT = 10_000.0
PENALTY_LOCKED_MOVED = 10_000.0

PENALTY_SPREAD = 60.0
PENALTY_AVOID_LAST = 30.0
PENALTY_MAX_CONSECUTIVE = 40.0
PENALTY_TEACHER_GAP = 20.0
PENALTY_PREF_VIOLATION = 25.0
PENALTY_UNEVEN_LOAD = 15.0
PENALTY_HALF_OF_DAY = 20.0


def _slot_numbers_by_id(problem: TimetableProblem) -> dict[int, int]:
    return {s.slot_id: s.slot_number for s in problem.slots_per_day}


def _slots_by_day(problem: TimetableProblem) -> dict[str, list]:
    days: dict[str, list] = {}
    for day in problem.days:
        days[day] = problem.teaching_slots_for_day(day)
    return days


def _constraint_weights(problem: TimetableProblem) -> dict[tuple[str, int], int]:
    weights: dict[tuple[str, int], int] = {}
    for sc in problem.soft_constraints:
        weights[(sc.constraint_type, sc.target_id)] = sc.weight
    return weights


def find_hard_violations(
    problem: TimetableProblem, schedule: list[ScheduleEntry]
) -> list[Violation]:
    """Return every hard constraint violation in the schedule."""
    violations: list[Violation] = []
    index_by_key: dict[tuple, int] = {}

    by_teacher: dict[tuple, list[int]] = defaultdict(list)
    by_class: dict[tuple, list[int]] = defaultdict(list)
    by_room: dict[tuple, list[int]] = defaultdict(list)
    unavailable: set[tuple] = {
        (u.teacher_id, u.day, u.slot_id) for u in problem.unavailabilities
    }
    day_slots: dict[str, set[int]] = {}
    slot_order: dict[int, int] = {}
    for day in problem.days:
        slots = problem.teaching_slots_for_day(day)
        day_slots[day] = {s.slot_id for s in slots}
        for s in slots:
            slot_order[s.slot_id] = s.slot_number

    entries_by_position: dict[tuple[int, int], ScheduleEntry] = {}
    for index, entry in enumerate(schedule):
        index_by_key[index] = index
        key_t = (entry.teacher_id, entry.day, entry.slot_id)
        key_c = (entry.class_id, entry.day, entry.slot_id)
        by_teacher[key_t].append(index)
        by_class[key_c].append(index)
        if entry.room_id is not None:
            by_room[(entry.room_id, entry.day, entry.slot_id)].append(index)
        entries_by_position[(entry.class_id, entry.day, entry.slot_id)] = entry

        if (entry.teacher_id, entry.day, entry.slot_id) in unavailable:
            violations.append(
                Violation(
                    "teacher_unavailable",
                    "hard",
                    f"Teacher {entry.teacher_id} is unavailable on {entry.day} slot {entry.slot_id}.",
                    [index],
                    PENALTY_UNAVAILABLE,
                )
            )

    for key, indices in by_teacher.items():
        if len(indices) > 1:
            violations.append(
                Violation(
                    "teacher_clash",
                    "hard",
                    f"Teacher {key[0]} is in {len(indices)} places on {key[1]} slot {key[2]}.",
                    indices,
                    PENALTY_TEACHER_CLASH * (len(indices) - 1),
                )
            )

    for key, indices in by_class.items():
        if len(indices) > 1:
            violations.append(
                Violation(
                    "class_clash",
                    "hard",
                    f"Class {key[0]} has {len(indices)} lessons on {key[1]} slot {key[2]}.",
                    indices,
                    PENALTY_CLASS_CLASH * (len(indices) - 1),
                )
            )

    for key, indices in by_room.items():
        if len(indices) > 1:
            violations.append(
                Violation(
                    "room_clash",
                    "hard",
                    f"Room {key[0]} is used by {len(indices)} classes on {key[1]} slot {key[2]}.",
                    indices,
                    PENALTY_ROOM_CLASH * (len(indices) - 1),
                )
            )

    requirements: dict[tuple[int, int], int] = defaultdict(int)
    expected_doubles: dict[tuple[int, int], int] = defaultdict(int)
    actual_doubles: dict[tuple[int, int], int] = defaultdict(int)
    for entry in schedule:
        requirements[(entry.class_id, entry.subject_id)] += 1
        if entry.is_double_start:
            actual_doubles[(entry.class_id, entry.subject_id)] += 1

    for req in problem.requirements:
        key = (req.class_id, req.subject_id)
        actual = requirements.get(key, 0)
        if actual != req.periods_per_week:
            direction = "missing" if actual < req.periods_per_week else "excess"
            violations.append(
                Violation(
                    "period_count",
                    "hard",
                    f"Subject {req.subject_id} for class {req.class_id}: "
                    f"{direction} {abs(req.periods_per_week - actual)} period(s).",
                    [],
                    PENALTY_PERIOD_COUNT * abs(req.periods_per_week - actual),
                )
            )
        expected_doubles[key] = req.doubles_per_week

    for key, count in actual_doubles.items():
        if count != expected_doubles.get(key, 0):
            violations.append(
                Violation(
                    "double_count",
                    "hard",
                    f"Class {key[0]} subject {key[1]} has {count} doubles "
                    f"(expected {expected_doubles.get(key, 0)}).",
                    [],
                    PENALTY_PERIOD_COUNT,
                )
            )

    # Double adjacency: a double_start must be immediately followed by the
    # matching double_end in the next teaching slot of the same day.
    next_teaching: dict[tuple[str, int], int] = {}
    for day, slots in day_slots.items():
        ordered = sorted((slot_order[sid], sid) for sid in slots)
        for pos, sid in ordered:
            nxt = next((s2 for p2, s2 in ordered if p2 == pos + 1), None)
            if nxt is not None:
                next_teaching[(day, sid)] = nxt

    for entry in schedule:
        if not entry.is_double_start:
            continue
        nxt_id = next_teaching.get((entry.day, entry.slot_id))
        follower = entries_by_position.get(
            (entry.class_id, entry.day, slot_order.get(nxt_id, -2))
            if nxt_id
            else (0, "", -1)
        )
        valid = (
            nxt_id is not None
            and follower is not None
            and follower.is_double_end
            and follower.subject_id == entry.subject_id
            and follower.teacher_id == entry.teacher_id
        )
        if not valid:
            violations.append(
                Violation(
                    "double_split",
                    "hard",
                    f"Double period for class {entry.class_id} subject "
                    f"{entry.subject_id} on {entry.day} is split by a break or "
                    "missing second half.",
                    [],
                    PENALTY_DOUBLE_SPLIT,
                )
            )

    for locked in problem.locked_entries:
        match = next(
            (
                e
                for e in schedule
                if e.class_id == locked.class_id
                and e.subject_id == locked.subject_id
                and e.teacher_id == locked.teacher_id
                and e.day == locked.day
                and e.slot_id == locked.slot_id
            ),
            None,
        )
        if match is None:
            violations.append(
                Violation(
                    "locked_moved",
                    "hard",
                    f"Locked entry for class {locked.class_id} subject "
                    f"{locked.subject_id} on {locked.day} was moved or removed.",
                    [],
                    PENALTY_LOCKED_MOVED,
                )
            )

    return violations


def find_soft_violations(
    problem: TimetableProblem, schedule: list[ScheduleEntry]
) -> list[Violation]:
    """Apply the weighted soft penalty table. Returns the violations found."""
    violations: list[Violation] = []
    slot_order = {s.slot_id: s.slot_number for s in problem.slots_per_day}
    day_slots = _slots_by_day(problem)

    subject_constraints: dict[tuple[str, int], int] = {}
    teacher_constraints: dict[tuple[str, int], int] = {}
    for sc in problem.soft_constraints:
        if sc.target_type == "subject":
            subject_constraints[(sc.constraint_type, sc.target_id)] = sc.weight
        else:
            teacher_constraints[(sc.constraint_type, sc.target_id)] = sc.weight

    default_weight = 5
    mid_points = {day: (len(slots) + 1) / 2 for day, slots in day_slots.items()}
    last_slot_by_day = {
        day: (slots[-1].slot_id if slots else None) for day, slots in day_slots.items()
    }

    day_subject_count: dict[tuple[int, int, str], int] = defaultdict(int)
    teacher_day_slots: dict[tuple[int, str], list[int]] = defaultdict(list)
    teacher_day_count: dict[tuple[int, str], int] = defaultdict(int)

    for index, entry in enumerate(schedule):
        day_subject_count[(entry.class_id, entry.subject_id, entry.day)] += 1
        slot_num = slot_order.get(entry.slot_id, 0)
        teacher_day_slots[(entry.teacher_id, entry.day)].append(slot_num)
        teacher_day_count[(entry.teacher_id, entry.day)] += 1

        w_avoid = subject_constraints.get(("avoid_last_period", entry.subject_id))
        if w_avoid is not None and last_slot_by_day.get(entry.day) == entry.slot_id:
            violations.append(
                Violation(
                    "heavy_last_period",
                    "soft",
                    f"Subject {entry.subject_id} for class {entry.class_id} is in "
                    f"the last period on {entry.day}.",
                    [index],
                    PENALTY_AVOID_LAST * w_avoid,
                )
            )

        w_morning = subject_constraints.get(("prefer_morning", entry.subject_id))
        w_afternoon = subject_constraints.get(("prefer_afternoon", entry.subject_id))
        mid = mid_points.get(entry.day, 0)
        if w_morning is not None and slot_num > mid:
            violations.append(
                Violation(
                    "subject_half",
                    "soft",
                    f"Morning-preferred subject {entry.subject_id} scheduled in "
                    f"the afternoon on {entry.day}.",
                    [index],
                    PENALTY_HALF_OF_DAY * w_morning,
                )
            )
        if w_afternoon is not None and 0 < slot_num <= mid:
            violations.append(
                Violation(
                    "subject_half",
                    "soft",
                    f"Afternoon-preferred subject {entry.subject_id} scheduled in "
                    f"the morning on {entry.day}.",
                    [index],
                    PENALTY_HALF_OF_DAY * w_afternoon,
                )
            )

    for (class_id, subject_id, day), count in day_subject_count.items():
        if count < 2:
            continue
        weight = subject_constraints.get(("spread_evenly", subject_id), default_weight)
        violations.append(
            Violation(
                "subject_not_spread",
                "soft",
                f"Subject {subject_id} appears {count} times on {day} for class "
                f"{class_id}.",
                [],
                PENALTY_SPREAD * weight,
            )
        )

    teachers_involved = {entry.teacher_id for entry in schedule}
    for teacher_id in teachers_involved:
        w_free = teacher_constraints.get(("free_day", teacher_id))
        w_compact = teacher_constraints.get(("compact_day", teacher_id))
        w_max_daily = teacher_constraints.get(("max_periods_per_day", teacher_id))
        w_consec = teacher_constraints.get(("max_consecutive", teacher_id))

        for day in problem.days:
            slots = sorted(teacher_day_slots.get((teacher_id, day), []))
            if not slots:
                if w_free is not None:
                    continue
                continue

            if w_free is not None:
                violations.append(
                    Violation(
                        "free_day_violated",
                        "soft",
                        f"Teacher {teacher_id} teaches on preferred free day {day}.",
                        [],
                        PENALTY_PREF_VIOLATION * w_free,
                    )
                )

            gaps = (slots[-1] - slots[0] + 1) - len(slots)
            gap_weight = w_compact if w_compact is not None else 1
            if gaps > 0:
                violations.append(
                    Violation(
                        "teacher_gap",
                        "soft",
                        f"Teacher {teacher_id} has {gaps} gap(s) on {day}.",
                        [],
                        PENALTY_TEACHER_GAP * gaps * gap_weight,
                    )
                )

            if w_max_daily is not None and len(slots) > w_max_daily:
                violations.append(
                    Violation(
                        "max_periods_violated",
                        "soft",
                        f"Teacher {teacher_id} has {len(slots)} periods on {day} "
                        f"(max {w_max_daily}).",
                        [],
                        PENALTY_PREF_VIOLATION
                        * (len(slots) - w_max_daily)
                        * w_max_daily
                        // max(w_max_daily, 1),
                    )
                )

            longest_run = 1
            run = 1
            for i in range(1, len(slots)):
                if slots[i] == slots[i - 1] + 1:
                    run += 1
                    longest_run = max(longest_run, run)
                else:
                    run = 1
            if w_consec is not None and longest_run > w_consec:
                violations.append(
                    Violation(
                        "max_consecutive_violated",
                        "soft",
                        f"Teacher {teacher_id} teaches {longest_run} consecutive "
                        f"periods on {day} (max {w_consec}).",
                        [],
                        PENALTY_MAX_CONSECUTIVE * (longest_run - w_consec) * w_consec,
                    )
                )

            w_morning = teacher_constraints.get(("prefer_morning", teacher_id))
            w_afternoon = teacher_constraints.get(("prefer_afternoon", teacher_id))
            if (w_morning is not None or w_afternoon is not None) and slots:
                mid = mid_points.get(day, 0)
                wrong_half = (
                    sum(1 for s in slots if s > mid)
                    if w_morning is not None
                    else sum(1 for s in slots if s <= mid)
                )
                if wrong_half:
                    violations.append(
                        Violation(
                            "teacher_half",
                            "soft",
                            f"Teacher {teacher_id} has lessons in the less preferred "
                            f"half on {day}.",
                            [],
                            PENALTY_PREF_VIOLATION * wrong_half,
                        )
                    )

        daily_counts = [
            len(teacher_day_slots.get((teacher_id, day), [])) for day in problem.days
        ]
        if daily_counts:
            mean = sum(daily_counts) / len(daily_counts)
            variance = sum((c - mean) ** 2 for c in daily_counts) / len(daily_counts)
            std = variance**0.5
            if std > 2:
                violations.append(
                    Violation(
                        "uneven_load",
                        "soft",
                        f"Teacher {teacher_id} has an uneven daily load "
                        f"(std {std:.1f}).",
                        [],
                        PENALTY_UNEVEN_LOAD,
                    )
                )

    return violations


def evaluate_schedule(
    problem: TimetableProblem, schedule: list[ScheduleEntry]
) -> tuple[float, list[Violation], list[Violation]]:
    """Score a schedule. Returns (score, hard_violations, soft_violations)."""
    hard = find_hard_violations(problem, schedule)
    soft = find_soft_violations(problem, schedule)
    score = sum(v.penalty for v in hard) + sum(v.penalty for v in soft)
    return -score, hard, soft

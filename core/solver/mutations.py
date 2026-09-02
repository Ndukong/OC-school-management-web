"""Mutation and crossover operators for the genetic algorithm.

Every operator works on a plain list of ScheduleEntry copies, and the
caller is responsible for validating hard constraints (the helpers here
return the modified candidate; the GA scores and rejects it if worse).
"""

import random
from dataclasses import replace

from core.solver.problem import ScheduleEntry, TimetableProblem


def clone_schedule(schedule: list[ScheduleEntry]) -> list[ScheduleEntry]:
    return [replace(entry) for entry in schedule]


def _lessons_of_class(schedule: list[ScheduleEntry], class_id: int) -> list[int]:
    return [i for i, e in enumerate(schedule) if e.class_id == class_id]


def _lessons_of_teacher(schedule: list[ScheduleEntry], teacher_id: int) -> list[int]:
    return [i for i, e in enumerate(schedule) if e.teacher_id == teacher_id]


def swap_within_class(
    problem: TimetableProblem, schedule: list[ScheduleEntry], rng: random.Random
) -> list[ScheduleEntry] | None:
    """Swap two lessons of the same class (different day+slot)."""
    classes = [c.class_id for c in problem.classes]
    if not classes:
        return None
    class_id = rng.choice(classes)
    indices = _lessons_of_class(schedule, class_id)
    unlocked = [i for i in indices if not schedule[i].is_locked]
    if len(unlocked) < 2:
        return None
    a, b = rng.sample(unlocked, 2)
    if (schedule[a].day, schedule[a].slot_id) == (schedule[b].day, schedule[b].slot_id):
        return None
    modified = clone_schedule(schedule)
    modified[a].day, modified[b].day = modified[b].day, modified[a].day
    modified[a].slot_id, modified[b].slot_id = modified[b].slot_id, modified[a].slot_id
    modified[a].is_double_start, modified[b].is_double_start = (
        modified[b].is_double_start,
        modified[a].is_double_start,
    )
    return modified


def swap_within_teacher(
    problem: TimetableProblem, schedule: list[ScheduleEntry], rng: random.Random
) -> list[ScheduleEntry] | None:
    """Swap the time slots of two lessons taught by the same teacher."""
    teachers = list({e.teacher_id for e in schedule})
    if not teachers:
        return None
    teacher_id = rng.choice(teachers)
    indices = _lessons_of_teacher(schedule, teacher_id)
    unlocked = [i for i in indices if not schedule[i].is_locked]
    if len(unlocked) < 2:
        return None
    a, b = rng.sample(unlocked, 2)
    entry_a, entry_b = schedule[a], schedule[b]
    if entry_a.class_id == entry_b.class_id:
        return None
    modified = clone_schedule(schedule)
    modified[a].day, modified[b].day = modified[b].day, modified[a].day
    modified[a].slot_id, modified[b].slot_id = modified[b].slot_id, modified[a].slot_id
    return modified


def move_to_empty(
    problem: TimetableProblem,
    schedule: list[ScheduleEntry],
    rng: random.Random,
    empty_slots: dict[tuple[int, str], list[tuple[int, int]]] | None = None,
) -> list[ScheduleEntry] | None:
    """Move one lesson to an empty (day, slot) position for its class."""
    movable = [i for i, e in enumerate(schedule) if not e.is_locked]
    if not movable:
        return None
    index = rng.choice(movable)
    entry = schedule[index]

    occupied = {(e.day, e.slot_id) for e in schedule if e.class_id == entry.class_id}
    free: list[tuple[str, int]] = []
    for day in problem.days:
        for slot in problem.teaching_slots_for_day(day):
            if (day, slot.slot_id) not in occupied:
                free.append((day, slot.slot_id))
    if not free:
        return None

    day, slot_id = rng.choice(free)
    modified = clone_schedule(schedule)
    modified[index].day = day
    modified[index].slot_id = slot_id
    modified[index].is_double_start = False
    modified[index].is_double_end = False
    return modified


def swap_double(
    problem: TimetableProblem, schedule: list[ScheduleEntry], rng: random.Random
) -> list[ScheduleEntry] | None:
    """Move a double lesson to a different valid double-eligible slot pair."""
    doubles = [
        i for i, e in enumerate(schedule) if e.is_double_start and not e.is_locked
    ]
    if not doubles:
        return None
    index = rng.choice(doubles)
    entry = schedule[index]

    slots_by_number = {
        s.slot_number: s
        for day in problem.days
        for s in problem.teaching_slots_for_day(day)
    }
    occupied = {(e.day, e.slot_id) for e in schedule if e.class_id == entry.class_id}
    pairs: list[tuple[str, int, int]] = []
    for day in problem.days:
        day_entry_slots = {
            e.slot_id for e in schedule if e.day == day and e.class_id == entry.class_id
        }
        for slot in problem.teaching_slots_for_day(day):
            if not slot.can_start_double:
                continue
            nxt = slots_by_number.get(slot.slot_number + 1)
            if nxt is None:
                continue
            if (day, slot.slot_id) in occupied or (day, nxt.slot_id) in occupied:
                continue
            if (day, slot.slot_id) in day_entry_slots:
                continue
            pairs.append((day, slot.slot_id, nxt.slot_id))
    if not pairs:
        return None

    day, slot_id, nxt_id = rng.choice(pairs)
    modified = clone_schedule(schedule)
    modified[index].day = day
    modified[index].slot_id = slot_id
    # the paired is_double_end entry follows immediately in the old layout;
    # find and move it too
    old_next_pos = None
    ordered = sorted(
        (
            (i, e)
            for i, e in enumerate(schedule)
            if e.class_id == entry.class_id and e.day == entry.day
        ),
        key=lambda pair: (slot_order_of(problem, pair[1].slot_id),),
    )
    for pos, (i, e) in enumerate(ordered):
        if i == index:
            old_next_pos = ordered[pos + 1][0] if pos + 1 < len(ordered) else None
            break
    if old_next_pos is not None:
        modified[old_next_pos].day = day
        modified[old_next_pos].slot_id = nxt_id
    return modified


def slot_order_of(problem: TimetableProblem, slot_id: int) -> int:
    for slot in problem.slots_per_day:
        if slot.slot_id == slot_id:
            return slot.slot_number
    return 0


def day_swap(
    problem: TimetableProblem, schedule: list[ScheduleEntry], rng: random.Random
) -> list[ScheduleEntry] | None:
    """Swap all lessons of one class between two whole days."""
    if len(problem.days) < 2:
        return None
    day_a, day_b = rng.sample(problem.days, 2)
    class_id = rng.choice([c.class_id for c in problem.classes])
    indices_a = [
        i for i, e in enumerate(schedule) if e.class_id == class_id and e.day == day_a
    ]
    indices_b = [
        i for i, e in enumerate(schedule) if e.class_id == class_id and e.day == day_b
    ]
    if any(schedule[i].is_locked for i in indices_a + indices_b):
        return None
    modified = clone_schedule(schedule)
    for i in indices_a:
        modified[i].day = day_b
    for i in indices_b:
        modified[i].day = day_a
    return modified


def crossover(
    problem: TimetableProblem,
    parent_a: list[ScheduleEntry],
    parent_b: list[ScheduleEntry],
    rng: random.Random,
) -> list[ScheduleEntry]:
    """Class-row crossover: take whole class-rows from each parent, then
    repair teacher clashes by moving one conflicting entry to a free slot."""
    class_ids = [c.class_id for c in problem.classes]
    rng.shuffle(class_ids)
    half = len(class_ids) // 2 or 1
    from_a = set(class_ids[:half])

    child: list[ScheduleEntry] = []
    source_by_class: dict[int, list[ScheduleEntry]] = {}
    for class_id in class_ids:
        parent = parent_a if class_id in from_a else parent_b
        rows = [replace(e) for e in parent if e.class_id == class_id]
        source_by_class[class_id] = rows
        child.extend(rows)

    # Repair teacher clashes: when both halves contain the same teacher at
    # the same day+slot, move one of the conflicting entries to a free slot
    # for its own class.
    seen: dict[tuple[int, str, int], int] = {}
    for i, entry in enumerate(child):
        key = (entry.teacher_id, entry.day, entry.slot_id)
        if key in seen:
            occupied = {
                (e.day, e.slot_id) for e in child if e.class_id == entry.class_id
            }
            free = [
                (day, slot.slot_id)
                for day in problem.days
                for slot in problem.teaching_slots_for_day(day)
                if (day, slot.slot_id) not in occupied
            ]
            for day, slot_id in free:
                trial = [replace(e) for e in child]
                trial[i].day = day
                trial[i].slot_id = slot_id
                clash = any(
                    other_i != i
                    and other.teacher_id == entry.teacher_id
                    and other.day == day
                    and other.slot_id == slot_id
                    for other_i, other in enumerate(trial)
                )
                if not clash:
                    child[i].day = day
                    child[i].slot_id = slot_id
                    break
        else:
            seen[key] = i
    return child

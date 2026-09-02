"""Standalone validator used by the solver and the manual editor."""

from core.solver.fitness import find_hard_violations, find_soft_violations
from core.solver.problem import ScheduleEntry, TimetableProblem, Violation


class TimetableValidator:
    """Validate a complete or partial timetable schedule.

    Can validate a full schedule, or check a single proposed change
    (swap/move) for conflicts before applying it.
    """

    def __init__(self, problem: TimetableProblem):
        self.problem = problem

    def validate_full(self, schedule: list[ScheduleEntry]) -> list[Violation]:
        """Check every constraint. Returns all violations found."""
        return find_hard_violations(self.problem, schedule) + find_soft_violations(
            self.problem, schedule
        )

    def validate_hard(self, schedule: list[ScheduleEntry]) -> list[Violation]:
        """Check only the hard constraints (fast path for editors)."""
        return find_hard_violations(self.problem, schedule)

    def validate_soft(self, schedule: list[ScheduleEntry]) -> list[Violation]:
        """Check only the soft constraints."""
        return find_soft_violations(self.problem, schedule)

    def check_swap(
        self,
        schedule: list[ScheduleEntry],
        entry_index_a: int,
        entry_index_b: int,
    ) -> list[Violation]:
        """Check what violations would result from swapping two entries."""
        from dataclasses import replace

        modified = [replace(e) for e in schedule]
        a = modified[entry_index_a]
        b = modified[entry_index_b]
        a.day, b.day = b.day, a.day
        a.slot_id, b.slot_id = b.slot_id, a.slot_id
        return self.validate_hard(modified)

    def check_move(
        self,
        schedule: list[ScheduleEntry],
        entry_index: int,
        new_day: str,
        new_slot_id: int,
    ) -> list[Violation]:
        """Check what violations would result from moving an entry to a new slot."""
        from dataclasses import replace

        modified = [replace(e) for e in schedule]
        entry = modified[entry_index]
        entry.day = new_day
        entry.slot_id = new_slot_id
        return self.validate_hard(modified)

    def free_slots_for_class(
        self, schedule: list[ScheduleEntry], class_id: int
    ) -> list[tuple[str, int]]:
        """All (day, slot_id) teaching positions where the class is free."""
        occupied = {(e.day, e.slot_id) for e in schedule if e.class_id == class_id}
        free: list[tuple[str, int]] = []
        for day in self.problem.days:
            for slot in self.problem.teaching_slots_for_day(day):
                if (day, slot.slot_id) not in occupied:
                    free.append((day, slot.slot_id))
        return free

    def suggest_fixes(
        self,
        schedule: list[ScheduleEntry],
        violation: Violation,
    ) -> list[tuple[int, str, int]]:
        """Suggest swaps/moves that would resolve a given violation.

        Returns a list of (entry_index, new_day, new_slot_id) proposals that
        produce no hard violations when applied.
        """
        proposals: list[tuple[int, str, int]] = []
        if not violation.entries:
            return proposals

        target_index = violation.entries[0]
        entry = schedule[target_index]

        for day, slot in (
            (day, slot.slot_id)
            for day in self.problem.days
            for slot in self.problem.teaching_slots_for_day(day)
        ):
            if not self.check_move(schedule, target_index, day, slot):
                proposals.append((target_index, day, slot))
            if len(proposals) >= 5:
                return proposals

        for other_index, other in enumerate(schedule):
            if other_index == target_index or other.class_id != entry.class_id:
                continue
            if other.is_locked:
                continue
            if not self.check_swap(schedule, target_index, other_index):
                proposals.append((other_index, other.day, other.slot_id))
            if len(proposals) >= 5:
                break

        return proposals

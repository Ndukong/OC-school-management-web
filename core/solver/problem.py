"""Data structures for the timetable solver.

These are pure Python — no Django dependency. The Django layer converts
ORM objects into these before calling the solver.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SlotInfo:
    """One teaching period in the day template."""

    slot_id: int  # PeriodSlot.pk
    slot_number: int  # Position in day (1-based)
    label: str
    can_start_double: bool
    start_time: str  # "HH:MM" for display
    end_time: str


@dataclass(frozen=True)
class ClassInfo:
    class_id: int  # SchoolClass.pk
    name: str  # e.g. "Form 2 A"
    form_level: int
    sort_order: int


@dataclass(frozen=True)
class TeacherInfo:
    teacher_id: int  # Teacher.pk
    name: str  # e.g. "Mr. Ndukong"


@dataclass(frozen=True)
class SubjectInfo:
    subject_id: int  # Subject.pk
    code: str  # e.g. "MAT"
    name: str


@dataclass(frozen=True)
class RoomInfo:
    room_id: int
    name: str
    room_type: str
    capacity: int


@dataclass(frozen=True)
class Requirement:
    """One requirement: 'class X needs subject Y taught by teacher Z,
    N periods per week, D of which are doubles, optionally in room R.'"""

    class_id: int
    subject_id: int
    teacher_id: int
    periods_per_week: int
    doubles_per_week: int  # Number of double-period pairs
    room_id: int | None  # Required room (None = any / class's own room)


@dataclass(frozen=True)
class Unavailability:
    """Teacher T cannot teach on day D in slot S."""

    teacher_id: int
    day: str
    slot_id: int


@dataclass
class SoftConstraint:
    """A weighted soft constraint for the fitness function."""

    constraint_type: str  # e.g. "spread_evenly", "max_consecutive", etc.
    target_type: str  # "teacher" or "subject"
    target_id: int  # Teacher.pk or Subject.pk
    value: dict  # Constraint-specific parameters
    weight: int  # 1-10


@dataclass
class TimetableProblem:
    """Complete input to the solver. Built by Django, consumed by the solver."""

    days: list[str]  # e.g. ["Monday", ..., "Friday"]
    slots_per_day: list[SlotInfo]  # Template day (teaching slots only)
    assembly_day: str
    assembly_lost_slots: int  # How many teaching slots assembly eats
    classes: list[ClassInfo]
    teachers: list[TeacherInfo]
    subjects: list[SubjectInfo]
    rooms: list[RoomInfo]
    requirements: list[Requirement]
    unavailabilities: list[Unavailability]
    soft_constraints: list[SoftConstraint]
    locked_entries: list[ScheduleEntry] = field(default_factory=list)

    def teaching_slots_for_day(self, day: str) -> list[SlotInfo]:
        """Return available teaching slots for a given day."""
        if day == self.assembly_day and self.assembly_lost_slots > 0:
            return self.slots_per_day[self.assembly_lost_slots :]
        return list(self.slots_per_day)

    @property
    def total_weekly_slots_per_class(self) -> dict[int, int]:
        """Total available teaching slots per class across the week."""
        totals: dict[int, int] = {}
        for ci in self.classes:
            total = sum(len(self.teaching_slots_for_day(d)) for d in self.days)
            totals[ci.class_id] = total
        return totals


@dataclass
class ScheduleEntry:
    """One assignment in a solution: class C has subject S with teacher T
    in room R on day D at slot P."""

    class_id: int
    subject_id: int
    teacher_id: int
    room_id: int | None
    day: str
    slot_id: int
    is_double_start: bool = False
    is_double_end: bool = False
    is_locked: bool = False


@dataclass
class Violation:
    """A constraint violation found during validation."""

    violation_type: str  # "teacher_clash", "class_clash", "room_clash", etc.
    severity: str  # "hard" or "soft"
    description: str
    entries: list[int]  # Indices into the schedule that conflict
    penalty: float


@dataclass
class SolverResult:
    """Output from the solver."""

    schedule: list[ScheduleEntry]
    fitness_score: float
    hard_violations: list[Violation]
    soft_violations: list[Violation]
    generation_time_seconds: float
    iterations: int
    solver_log: str
    success: bool  # True if hard_violations is empty

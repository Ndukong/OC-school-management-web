"""Timetable configuration, solver results, and schedule entries.

Models are ordered by dependency — configure first, generate second, store third.
"""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class TimetableConfig(models.Model):
    """One configuration per school per academic year. Defines the weekly
    structure: active days, assembly settings, and links to period slots."""

    school = models.ForeignKey(
        "core.School", on_delete=models.CASCADE, related_name="timetable_configs"
    )
    academic_year_start = models.PositiveIntegerField(help_text="e.g. 2026")
    academic_year_end = models.PositiveIntegerField(help_text="e.g. 2027")
    days = models.JSONField(
        default=list,
        help_text='Ordered active day names, e.g. ["Monday","Tuesday","Wednesday","Thursday","Friday"]',
    )
    assembly_day = models.CharField(
        max_length=15,
        default="Monday",
        help_text="Day of the week that has morning assembly.",
    )
    assembly_duration_periods = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(0), MaxValueValidator(3)],
        help_text="How many teaching periods the assembly replaces (0 = no assembly).",
    )
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Timetable Config"
        verbose_name_plural = "Timetable Configs"
        unique_together = [["school", "academic_year_start", "academic_year_end"]]

    def __str__(self) -> str:
        return (
            f"{self.school.name_en} {self.academic_year_start}/{self.academic_year_end}"
        )

    def save(self, *args, **kwargs):
        if self.is_active:
            TimetableConfig.objects.filter(school=self.school, is_active=True).exclude(
                pk=self.pk
            ).update(is_active=False)
        super().save(*args, **kwargs)

    @property
    def teaching_slots_per_day(self) -> int:
        return self.period_slots.filter(slot_type="teaching").count()

    def teaching_slots_for_day(self, day: str):
        """Return teaching PeriodSlots available on a given day.

        On assembly_day, the first N teaching slots (where N = assembly_duration_periods)
        are consumed by assembly and excluded.
        """
        teaching = list(
            self.period_slots.filter(slot_type="teaching").order_by("slot_number")
        )
        if day == self.assembly_day and self.assembly_duration_periods > 0:
            teaching = teaching[self.assembly_duration_periods :]
        return teaching


class PeriodSlot(models.Model):
    """A single time block in the school day (teaching period, break, or assembly).

    The admin configures these freely: number of periods, break positions,
    start/stop times. Slot numbering is 1-based and sequential for a full day
    INCLUDING breaks (so the solver can reason about adjacency for double periods).
    """

    SLOT_TYPE_CHOICES = [
        ("teaching", "Teaching Period"),
        ("break", "Break"),
        ("assembly", "Assembly"),
    ]

    config = models.ForeignKey(
        TimetableConfig, on_delete=models.CASCADE, related_name="period_slots"
    )
    slot_number = models.PositiveSmallIntegerField(
        help_text="Global ordering within the day (1-based, sequential)."
    )
    slot_type = models.CharField(max_length=10, choices=SLOT_TYPE_CHOICES)
    label = models.CharField(
        max_length=50,
        help_text='Display label, e.g. "Period 1", "Morning Break", "Assembly".',
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    can_start_double = models.BooleanField(
        default=False,
        help_text="True if a double-period lesson can START in this slot "
        "(i.e. the immediately following slot is also a teaching slot "
        "with no break in between).",
    )

    class Meta:
        verbose_name = "Period Slot"
        verbose_name_plural = "Period Slots"
        ordering = ["slot_number"]
        unique_together = [["config", "slot_number"]]

    def __str__(self) -> str:
        return f"{self.label} ({self.start_time:%H:%M}–{self.end_time:%H:%M})"


class Room(models.Model):
    """Physical rooms/labs. Optional — many Cameroon schools don't need room
    scheduling because each class has a fixed classroom. Included for schools
    with shared labs, workshops, or computer rooms."""

    ROOM_TYPE_CHOICES = [
        ("classroom", "Classroom"),
        ("lab", "Laboratory"),
        ("workshop", "Workshop"),
        ("hall", "Hall"),
        ("field", "Field / Sports Ground"),
        ("computer", "Computer Room"),
    ]

    school = models.ForeignKey(
        "core.School", on_delete=models.CASCADE, related_name="rooms"
    )
    name = models.CharField(max_length=100)
    room_type = models.CharField(
        max_length=15, choices=ROOM_TYPE_CHOICES, default="classroom"
    )
    capacity = models.PositiveIntegerField(
        default=60, help_text="Maximum student capacity."
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Room"
        verbose_name_plural = "Rooms"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class SubjectPeriodRequirement(models.Model):
    """How many periods per week a subject needs in a specific class.

    This is the PRIMARY input to the solver. Each row says 'Form 2A needs
    6 periods of Mathematics per week, of which 0 are doubles.'
    """

    config = models.ForeignKey(
        TimetableConfig,
        on_delete=models.CASCADE,
        related_name="subject_requirements",
    )
    school_class = models.ForeignKey(
        "core.SchoolClass", on_delete=models.CASCADE, related_name="period_requirements"
    )
    subject = models.ForeignKey(
        "core.Subject", on_delete=models.CASCADE, related_name="period_requirements"
    )
    periods_per_week = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    doubles_per_week = models.PositiveSmallIntegerField(
        default=0,
        help_text="How many of the weekly periods should be consecutive doubles "
        "(e.g. 1 means one double = 2 periods consumed, rest are singles).",
    )
    preferred_room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Required room (e.g. lab for Chemistry practicals).",
    )

    class Meta:
        verbose_name = "Subject Period Requirement"
        verbose_name_plural = "Subject Period Requirements"
        unique_together = [["config", "school_class", "subject"]]

    def __str__(self) -> str:
        d = f" ({self.doubles_per_week}×double)" if self.doubles_per_week else ""
        return (
            f"{self.school_class} - {self.subject.code}: "
            f"{self.periods_per_week}/wk{d}"
        )


class TeacherAvailability(models.Model):
    """Blocks a teacher from a specific day+slot. Only UNAVAILABLE slots are stored;
    the absence of a row means the teacher IS available.

    Use case: PTA teachers who only come Mon/Wed/Fri, or a teacher with an
    external commitment on Thursday mornings.
    """

    config = models.ForeignKey(
        TimetableConfig,
        on_delete=models.CASCADE,
        related_name="teacher_availabilities",
    )
    teacher = models.ForeignKey(
        "core.Teacher", on_delete=models.CASCADE, related_name="availabilities"
    )
    day = models.CharField(max_length=15)
    period_slot = models.ForeignKey(
        PeriodSlot, on_delete=models.CASCADE, related_name="teacher_availabilities"
    )
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Teacher Unavailability"
        verbose_name_plural = "Teacher Unavailabilities"
        unique_together = [["config", "teacher", "day", "period_slot"]]

    def __str__(self) -> str:
        return f"{self.teacher} unavailable {self.day} {self.period_slot.label}"


class TeacherPreference(models.Model):
    """Soft constraints on teacher scheduling. The solver tries to honour these
    but will violate them to produce a valid timetable.

    Weight 1-10 controls priority (10 = most important to satisfy).
    """

    PREF_TYPE_CHOICES = [
        ("prefer_morning", "Prefers morning periods"),
        ("prefer_afternoon", "Prefers afternoon periods"),
        ("max_consecutive", "Maximum consecutive periods"),
        ("free_day", "Preferred free day (no classes)"),
        ("max_periods_per_day", "Maximum periods per day"),
        ("min_gap_between", "Minimum gap between lessons (periods)"),
        ("compact_day", "Prefers compact day (no gaps)"),
    ]

    config = models.ForeignKey(
        TimetableConfig,
        on_delete=models.CASCADE,
        related_name="teacher_preferences",
    )
    teacher = models.ForeignKey(
        "core.Teacher", on_delete=models.CASCADE, related_name="preferences"
    )
    preference_type = models.CharField(max_length=25, choices=PREF_TYPE_CHOICES)
    value = models.JSONField(
        default=dict,
        help_text='e.g. {"max_consecutive": 4} or {"free_day": "Wednesday"}',
    )
    weight = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )

    class Meta:
        verbose_name = "Teacher Preference"
        verbose_name_plural = "Teacher Preferences"

    def __str__(self) -> str:
        return (
            f"{self.teacher} - {self.get_preference_type_display()} "
            f"(weight {self.weight})"
        )


class SubjectConstraint(models.Model):
    """Soft constraints on how a subject should be scheduled across the week."""

    CONSTRAINT_TYPE_CHOICES = [
        ("spread_evenly", "Spread evenly across days (no 2 periods same day)"),
        ("avoid_last_period", "Avoid scheduling in the last period of the day"),
        ("prefer_morning", "Prefer morning periods (first half of day)"),
        ("prefer_afternoon", "Prefer afternoon periods (second half of day)"),
        ("not_consecutive_days", "Avoid placing on consecutive days"),
    ]

    config = models.ForeignKey(
        TimetableConfig,
        on_delete=models.CASCADE,
        related_name="subject_constraints",
    )
    subject = models.ForeignKey(
        "core.Subject", on_delete=models.CASCADE, related_name="timetable_constraints"
    )
    constraint_type = models.CharField(max_length=25, choices=CONSTRAINT_TYPE_CHOICES)
    value = models.JSONField(default=dict, blank=True)
    weight = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )

    class Meta:
        verbose_name = "Subject Constraint"
        verbose_name_plural = "Subject Constraints"

    def __str__(self) -> str:
        return f"{self.subject.code} - {self.get_constraint_type_display()}"


class Timetable(models.Model):
    """A generated (or manually assembled) timetable. Multiple versions can exist
    for comparison; only one can be published at a time per config."""

    STATUS_CHOICES = [
        ("generating", "Generating..."),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("published", "Published"),
    ]

    config = models.ForeignKey(
        TimetableConfig, on_delete=models.CASCADE, related_name="timetables"
    )
    name = models.CharField(max_length=100, default="Untitled")
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default="generating"
    )
    fitness_score = models.FloatField(
        default=0, help_text="Solver fitness score (higher = better)."
    )
    hard_violations = models.PositiveIntegerField(
        default=0,
        help_text="Number of hard constraint violations (must be 0 for valid).",
    )
    soft_violation_count = models.PositiveIntegerField(
        default=0, help_text="Number of soft constraint violations."
    )
    generation_time_seconds = models.FloatField(default=0)
    solver_log = models.TextField(
        blank=True, help_text="Iteration details and diagnostics from the solver."
    )
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Timetable"
        verbose_name_plural = "Timetables"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_status_display()})"

    def publish(self):
        Timetable.objects.filter(config=self.config, status="published").exclude(
            pk=self.pk
        ).update(status="completed", published_at=None)
        self.status = "published"
        self.published_at = timezone.now()
        self.save(update_fields=["status", "published_at"])


class TimetableEntry(models.Model):
    """One cell in the timetable grid: a class has a subject with a teacher
    in a room at a specific day+period.

    Hard uniqueness: one class can only be in one place per day+period.
    The solver also enforces teacher and room uniqueness, but those are
    checked at the application level (not DB unique_together) because
    the solver needs to handle them as constraint violations during search.
    """

    timetable = models.ForeignKey(
        Timetable, on_delete=models.CASCADE, related_name="entries"
    )
    day = models.CharField(max_length=15)
    period_slot = models.ForeignKey(
        PeriodSlot, on_delete=models.CASCADE, related_name="entries"
    )
    school_class = models.ForeignKey(
        "core.SchoolClass", on_delete=models.CASCADE, related_name="timetable_entries"
    )
    subject = models.ForeignKey(
        "core.Subject", on_delete=models.CASCADE, related_name="timetable_entries"
    )
    teacher = models.ForeignKey(
        "core.Teacher", on_delete=models.CASCADE, related_name="timetable_entries"
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="timetable_entries",
    )
    is_double_start = models.BooleanField(
        default=False,
        help_text="True if this is the FIRST period of a double-period lesson.",
    )
    is_double_end = models.BooleanField(
        default=False,
        help_text="True if this is the SECOND period of a double-period lesson.",
    )
    is_locked = models.BooleanField(
        default=False,
        help_text="Locked entries are preserved during re-generation.",
    )

    class Meta:
        verbose_name = "Timetable Entry"
        verbose_name_plural = "Timetable Entries"
        unique_together = [["timetable", "day", "period_slot", "school_class"]]

    def __str__(self) -> str:
        return (
            f"{self.day} {self.period_slot.label}: "
            f"{self.school_class} - {self.subject.code} ({self.teacher})"
        )

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


def clear_attendance(apps, schema_editor):
    AttendanceRecord = apps.get_model("core", "AttendanceRecord")
    AttendanceRegister = apps.get_model("core", "AttendanceRegister")
    AttendanceRecord.objects.all().delete()
    AttendanceRegister.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0013_schoolclass_dismissal_mark"),
    ]

    operations = [
        migrations.RunPython(clear_attendance, migrations.RunPython.noop),
        migrations.AddField(
            model_name="school",
            name="periods_per_day",
            field=models.PositiveSmallIntegerField(
                default=8,
                help_text="Number of teaching periods per day (6\u201310).",
                validators=[
                    MinValueValidator(6),
                    MaxValueValidator(10),
                ],
            ),
        ),
        migrations.AddField(
            model_name="attendanceregister",
            name="period",
            field=models.PositiveSmallIntegerField(
                default=1, help_text="Period number within the day (1-based)."
            ),
        ),
        migrations.AlterUniqueTogether(
            name="attendanceregister",
            unique_together={("school_class", "date", "period")},
        ),
        migrations.AlterField(
            model_name="attendancerecord",
            name="status",
            field=models.CharField(
                choices=[
                    ("P", "Present"),
                    ("L", "Late"),
                    ("A", "Absent"),
                    ("PRM", "Permission"),
                ],
                max_length=3,
            ),
        ),
    ]

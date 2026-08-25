from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0014_attendance_periods"),
    ]

    operations = [
        migrations.AddField(
            model_name="license",
            name="school",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="licenses",
                to="core.school",
            ),
        ),
    ]

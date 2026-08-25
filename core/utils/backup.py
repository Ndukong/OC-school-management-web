import json
import os
import shutil
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path

from django.conf import settings


def create_backup_archive(user=None, notes="", backup_type="full"):
    """Create a backup ZIP containing the database and optionally media."""
    from core.models.backup import BackupHistory

    backup_dir = Path(settings.BASE_DIR) / "backups"
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    db_name = Path(settings.DATABASES["default"]["NAME"]).stem
    filename = f"backup_{db_name}_{timestamp}.zip"
    filepath = backup_dir / filename

    with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zf:
        db_path = Path(settings.DATABASES["default"]["NAME"])
        db_added = False
        if db_path.exists() and db_path.stat().st_size > 0:
            zf.write(db_path, "database/db.sqlite3")
            db_added = True
        if not db_added:
            import io

            from django.core.management import call_command

            buf = io.StringIO()
            call_command("dumpdata", stdout=buf, verbosity=0)
            zf.writestr("database/dumpdata.json", buf.getvalue())
            db_added = True

        if backup_type == "full":
            media_root = Path(settings.MEDIA_ROOT)
            if media_root.exists():
                for root, _dirs, files in os.walk(media_root):
                    for f in files:
                        full = Path(root) / f
                        arc = f"media/{full.relative_to(media_root)}"
                        zf.write(full, arc)

        zf.writestr(
            "backup_meta.json",
            json.dumps(
                {
                    "created_at": datetime.now().isoformat(),
                    "backup_type": backup_type,
                    "db_name": db_name,
                    "notes": notes,
                    "django_settings": str(settings.DATABASES["default"]["NAME"]),
                },
                indent=2,
            ),
        )

    file_size = filepath.stat().st_size
    history = BackupHistory.objects.create(
        filename=filename,
        filepath=str(filepath),
        file_size=file_size,
        backup_type=backup_type,
        notes=notes,
        created_by=user,
    )
    return history


def restore_backup_archive(backup_id):
    """Restore from a BackupHistory record. Returns (success, message)."""
    from core.models.backup import BackupHistory

    try:
        history = BackupHistory.objects.get(pk=backup_id)
    except BackupHistory.DoesNotExist:
        return False, "Backup not found."

    filepath = Path(history.filepath)
    if not filepath.exists():
        return False, "Backup file not found on disk."

    try:
        with zipfile.ZipFile(filepath, "r") as zf:
            names = zf.namelist()
            has_db = "database/db.sqlite3" in names
            has_dump = "database/dumpdata.json" in names
            if not has_db and not has_dump:
                return False, "Invalid backup: no database found."

            db_path = Path(settings.DATABASES["default"]["NAME"])
            db_backup = db_path.with_suffix(".sqlite3.pre_restore")

            if db_path.exists():
                shutil.copy2(db_path, db_backup)

            try:
                if has_db:
                    with zf.open("database/db.sqlite3") as src, open(
                        db_path, "wb"
                    ) as dst:
                        dst.write(src.read())

                    conn = sqlite3.connect(str(db_path))
                    cursor = conn.execute("PRAGMA integrity_check")
                    result = cursor.fetchone()
                    conn.close()

                    if result[0] != "ok":
                        if db_backup.exists():
                            shutil.copy2(db_backup, db_path)
                        return False, f"Integrity check failed: {result[0]}"
                elif has_dump:
                    import json as _json
                    import tempfile

                    from django.core.management import call_command

                    dump_data = zf.read("database/dumpdata.json").decode()
                    _json.loads(dump_data)  # validate JSON is well-formed
                    with tempfile.NamedTemporaryFile(
                        mode="w", suffix=".json", delete=False
                    ) as tmp:
                        tmp.write(dump_data)
                        tmp_path = tmp.name
                    try:
                        call_command("loaddata", tmp_path, verbosity=0)
                    finally:
                        Path(tmp_path).unlink(missing_ok=True)

                media_root = Path(settings.MEDIA_ROOT)
                media_files = [n for n in names if n.startswith("media/")]
                if media_files:
                    media_root.mkdir(parents=True, exist_ok=True)
                    for member in media_files:
                        if member == "media/":
                            continue
                        zf.extract(member, media_root.parent)

            except Exception as e:
                if db_backup.exists():
                    shutil.copy2(db_backup, db_path)
                return False, f"Restore failed: {e}"
            finally:
                if db_backup.exists():
                    db_backup.unlink(missing_ok=True)

        history.status = "restored"
        history.save(update_fields=["status", "restored_at"])
        return True, "Backup restored successfully."
    except zipfile.BadZipFile:
        return False, "Invalid backup file."
    except Exception as e:
        return False, f"Restore error: {e}"


def generate_scheduled_task_script():
    """Generate a Windows .bat script for daily backup via Task Scheduler."""
    backup_dir = Path(settings.BASE_DIR) / "backups"
    manage_py = Path(settings.BASE_DIR) / "manage.py"
    script_path = backup_dir / "daily_backup.bat"

    backup_dir.mkdir(exist_ok=True)
    script_path.write_text(
        f"@echo off\n"
        f"REM Auto-generated daily backup script\n"
        f'cd /d "{settings.BASE_DIR}"\n'
        f'python "{manage_py}" create_backup --notes "Scheduled daily backup"\n'
    )
    return str(script_path)


def generate_scheduled_task_xml():
    """Generate a Windows Task Scheduler XML for daily 2 AM backup."""
    script = generate_scheduled_task_script()
    xml_path = Path(settings.BASE_DIR) / "backups" / "daily_backup_task.xml"
    xml_content = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Daily backup for School Management System</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2025-01-01T02:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{script}</Command>
    </Exec>
  </Actions>
</Task>"""
    xml_path.write_text(xml_content)
    return str(xml_path)

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core.api.views import (
    api_assignments,
    api_class_subject,
    api_save_scores,
)
from core.views.admin_config import (
    audit_log,
    class_subjects_index,
    class_subjects_manage,
    classes_manage,
    competencies_manage,
    pta_config,
    school_profile,
    settings_hub,
    subjects_manage,
    terms_manage,
    users_manage,
)
from core.views.auth_views import activate_view, dashboard, login_view, logout_view
from core.views.backup import (
    backup_management,
    download_backup,
    generate_license_key,
    license_info,
    offline_license_check,
)
from core.views.data_transfer import (
    school_data_export,
    school_data_import,
    school_data_transfer,
)
from core.views.discipline import (
    attendance_entry,
    conduct_config,
    discipline_summary_view,
    save_attendance_batch,
    save_attendance_cell,
)
from core.views.exports import (
    export_attendance_excel,
    export_finance_excel,
    export_marks_excel,
    export_results_excel,
    export_students_excel,
)
from core.views.finance import finance_dashboard, student_fee_status
from core.views.imports import import_students_view
from core.views.marks import mark_entry, mark_entry_select, save_score_cell
from core.views.notifications_views import (
    mark_all_read,
    mark_notification_read,
    notifications_list,
    notifications_unread_count,
)
from core.views.reports import (
    annual_class_council_view,
    batch_annual_report_cards,
    batch_report_cards,
    class_council_motifs,
    class_council_view,
    download_annual_mark_sheet,
    download_annual_report,
    download_annual_results_summary,
    download_id_cards,
    download_mark_sheet,
    download_results_summary,
    download_term_report,
    preview_annual_mark_sheet,
    preview_annual_report,
    preview_annual_results_summary,
    preview_id_cards,
    preview_mark_sheet,
    preview_results_summary,
    preview_term_report,
    pta_financial_view,
    reports_hub,
)
from core.views.results import compute_results
from core.views.sms_views import sms_cancel, sms_configuration, sms_history
from core.views.students import (
    student_create,
    student_detail,
    student_edit,
    student_export_excel,
    student_list,
)
from core.views.teachers_crud import (
    teacher_assignments,
    teacher_create,
    teacher_delete,
    teacher_detail,
    teacher_edit,
    teacher_list,
)
from core.views.timetable import (
    export_all_class_pdfs,
    export_all_teacher_pdfs,
    export_class_pdf,
    export_master_excel,
    export_master_pdf,
    export_teacher_pdf,
    generate_timetable,
    generation_status,
    rooms_manage,
    timetable_class_view,
    timetable_config_wizard,
    timetable_delete,
    timetable_edit,
    timetable_hub,
    timetable_lock_entry,
    timetable_master_view,
    timetable_publish,
    timetable_regenerate,
    timetable_room_view,
    timetable_stats,
    timetable_swap,
    timetable_teacher_view,
)

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("parent/", include("core.urls_parent", namespace="parent")),
    path("admin/dashboard/", dashboard, name="admin_dashboard"),
    path("admin/import-students/", import_students_view, name="import_students"),
    path("admin/", admin.site.urls),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("activate/", activate_view, name="activate"),
    path("teacher/", dashboard, name="teacher_dashboard"),
    # Students
    path("students/", student_list, name="student_list"),
    path("students/create/", student_create, name="student_create"),
    path("students/import/", import_students_view, name="student_import"),
    path("students/export/", student_export_excel, name="student_export_excel"),
    path("students/<int:pk>/edit/", student_edit, name="student_edit"),
    path("students/<int:pk>/", student_detail, name="student_detail"),
    path(
        "students/<int:student_id>/fee-status/",
        student_fee_status,
        name="student_fee_status",
    ),
    # Teachers
    path("teachers/", teacher_list, name="teacher_list"),
    path("teachers/create/", teacher_create, name="teacher_create"),
    path("teachers/<int:pk>/edit/", teacher_edit, name="teacher_edit"),
    path("teachers/<int:pk>/delete/", teacher_delete, name="teacher_delete"),
    path("teachers/assignments/", teacher_assignments, name="teacher_assignments"),
    path("teachers/<int:pk>/", teacher_detail, name="teacher_detail"),
    # Reports
    path("reports/", reports_hub, name="reports_hub"),
    # Admin Settings
    path("settings/", settings_hub, name="settings"),
    path("settings/school-profile/", school_profile, name="school_profile"),
    path("settings/terms/", terms_manage, name="terms_manage"),
    path("settings/classes/", classes_manage, name="classes_manage"),
    path("settings/subjects/", subjects_manage, name="subjects_manage"),
    path("settings/subjects/classes/", class_subjects_index, name="class_subjects_all"),
    path(
        "settings/classes/<int:class_id>/subjects/",
        class_subjects_manage,
        name="class_subjects_manage",
    ),
    path("settings/competencies/", competencies_manage, name="competencies_manage"),
    path("settings/users/", users_manage, name="users_manage"),
    path("settings/pta-config/", pta_config, name="pta_config"),
    path("settings/audit/", audit_log, name="audit_log"),
    # Backup & License
    path("settings/backup/", backup_management, name="backup_management"),
    path(
        "settings/backup/<int:backup_id>/download/",
        download_backup,
        name="download_backup",
    ),
    path("settings/license/", license_info, name="license_info"),
    path(
        "settings/license/generate/", generate_license_key, name="generate_license_key"
    ),
    path(
        "settings/license/offline-check/",
        offline_license_check,
        name="offline_license_check",
    ),
    # Per-school data transfer
    path("settings/data-transfer/", school_data_transfer, name="school_data_transfer"),
    path(
        "settings/data-transfer/export/", school_data_export, name="school_data_export"
    ),
    path(
        "settings/data-transfer/import/", school_data_import, name="school_data_import"
    ),
    # SMS
    path("settings/sms/", sms_configuration, name="sms_configuration"),
    path("settings/sms/history/", sms_history, name="sms_history"),
    path("settings/sms/<int:sms_id>/cancel/", sms_cancel, name="sms_cancel"),
    # Notifications
    path("notifications/", notifications_list, name="notifications_list"),
    path(
        "notifications/<int:notification_id>/read/",
        mark_notification_read,
        name="mark_notification_read",
    ),
    path("notifications/read-all/", mark_all_read, name="mark_all_read"),
    path(
        "api/notifications/unread-count/",
        notifications_unread_count,
        name="notifications_unread_count",
    ),
    # Mark Entry Engine
    path("marks/", mark_entry_select, name="mark_entry_select"),
    path("marks/save-cell/", save_score_cell, name="save_score_cell"),
    path(
        "marks/<int:class_id>/<int:subject_id>/<int:term_id>/",
        mark_entry,
        name="mark_entry_grid",
    ),
    path(
        "teacher/marks/<int:class_id>/<int:subject_id>/",
        mark_entry,
        name="mark_entry",
    ),
    path(
        "reports/term/<int:student_id>/<int:term_id>/",
        download_term_report,
        name="download_term_report",
    ),
    path(
        "reports/annual/<int:student_id>/<int:year_start>/<int:year_end>/",
        download_annual_report,
        name="download_annual_report",
    ),
    path(
        "reports/annual/<int:student_id>/<int:year_start>/<int:year_end>/preview/",
        preview_annual_report,
        name="preview_annual_report",
    ),
    path(
        "reports/batch-annual/<int:class_id>/<int:year_start>/<int:year_end>/",
        batch_annual_report_cards,
        name="batch_annual_report_cards",
    ),
    path(
        "reports/term/<int:student_id>/<int:term_id>/preview/",
        preview_term_report,
        name="preview_term_report",
    ),
    path(
        "reports/marksheet/<int:class_id>/<int:term_id>/",
        download_mark_sheet,
        name="download_mark_sheet",
    ),
    path(
        "reports/marksheet-annual/<int:class_id>/<int:year_start>/<int:year_end>/",
        download_annual_mark_sheet,
        name="download_annual_mark_sheet",
    ),
    path(
        "reports/marksheet/<int:class_id>/<int:term_id>/preview/",
        preview_mark_sheet,
        name="preview_mark_sheet",
    ),
    path(
        "reports/marksheet-annual/<int:class_id>/<int:year_start>/<int:year_end>/preview/",
        preview_annual_mark_sheet,
        name="preview_annual_mark_sheet",
    ),
    path("reports/id-cards/preview/", preview_id_cards, name="preview_id_cards"),
    path("reports/id-cards/download/", download_id_cards, name="download_id_cards"),
    path(
        "reports/results/<int:term_id>/",
        preview_results_summary,
        name="preview_results_summary",
    ),
    path(
        "reports/results/<int:term_id>/download/",
        download_results_summary,
        name="download_results_summary",
    ),
    path(
        "reports/results-annual/<int:year_start>/<int:year_end>/preview/",
        preview_annual_results_summary,
        name="preview_annual_results_summary",
    ),
    path(
        "reports/results-annual/<int:year_start>/<int:year_end>/download/",
        download_annual_results_summary,
        name="download_annual_results_summary",
    ),
    path(
        "reports/batch/<int:class_id>/<int:term_id>/",
        batch_report_cards,
        name="batch_report_cards",
    ),
    path(
        "reports/class-council/<int:term_id>/",
        class_council_view,
        name="class_council",
    ),
    path(
        "reports/class-council-annual/<int:year_start>/<int:year_end>/",
        annual_class_council_view,
        name="class_council_annual",
    ),
    path(
        "reports/class-council/motifs/",
        class_council_motifs,
        name="class_council_motifs",
    ),
    path(
        "reports/pta-finance/<int:term_id>/",
        pta_financial_view,
        name="pta_financial",
    ),
    # Excel exports
    path("exports/students/", export_students_excel, name="export_students_excel"),
    path(
        "exports/marks/<int:class_id>/<int:term_id>/",
        export_marks_excel,
        name="export_marks_excel",
    ),
    path(
        "exports/finance/<int:term_id>/",
        export_finance_excel,
        name="export_finance_excel",
    ),
    path(
        "exports/attendance/<int:class_id>/<int:term_id>/",
        export_attendance_excel,
        name="export_attendance_excel",
    ),
    path(
        "exports/results/<int:term_id>/",
        export_results_excel,
        name="export_results_excel",
    ),
    path("results/compute/", compute_results, name="compute_results"),
    path("finance/", finance_dashboard, name="finance_dashboard"),
    path("discipline/attendance/", attendance_entry, name="attendance_entry"),
    path(
        "discipline/attendance/save/", save_attendance_cell, name="save_attendance_cell"
    ),
    path(
        "discipline/attendance/save-batch/",
        save_attendance_batch,
        name="save_attendance_batch",
    ),
    path("discipline/summary/", discipline_summary_view, name="discipline_summary"),
    path("discipline/conduct-config/", conduct_config, name="conduct_config"),
    # API
    path("api/assignments/", api_assignments, name="api_assignments"),
    path(
        "api/class/<int:class_id>/subject/<int:subject_id>/",
        api_class_subject,
        name="api_class_subject",
    ),
    path(
        "api/class/<int:class_id>/subject/<int:subject_id>/save/",
        api_save_scores,
        name="api_save_scores",
    ),
    # Timetable
    path('timetable/', timetable_hub, name='timetable_hub'),
    path('timetable/config/', timetable_config_wizard, name='timetable_config_create'),
    path('timetable/config/<int:config_id>/', timetable_config_wizard, name='timetable_config_edit'),
    path('timetable/rooms/', rooms_manage, name='timetable_rooms'),
    path('timetable/config/<int:config_id>/generate/', generate_timetable, name='timetable_generate'),
    path('timetable/config/<int:config_id>/status/', generation_status, name='timetable_generation_status'),
    path('timetable/<int:timetable_id>/', timetable_master_view, name='timetable_master'),
    path('timetable/<int:timetable_id>/class/<int:class_id>/', timetable_class_view, name='timetable_class'),
    path('timetable/<int:timetable_id>/teacher/', timetable_teacher_view, name='timetable_my_schedule'),
    path('timetable/<int:timetable_id>/teacher/<int:teacher_id>/', timetable_teacher_view, name='timetable_teacher'),
    path('timetable/<int:timetable_id>/rooms/', timetable_room_view, name='timetable_room_view'),
    path('timetable/<int:timetable_id>/stats/', timetable_stats, name='timetable_stats'),
    path('timetable/<int:timetable_id>/edit/', timetable_edit, name='timetable_edit'),
    path('timetable/<int:timetable_id>/swap/', timetable_swap, name='timetable_swap'),
    path('timetable/entry/<int:entry_id>/lock/', timetable_lock_entry, name='timetable_lock_entry'),
    path('timetable/<int:timetable_id>/publish/', timetable_publish, name='timetable_publish'),
    path('timetable/<int:timetable_id>/regenerate/', timetable_regenerate, name='timetable_regenerate'),
    path('timetable/<int:timetable_id>/delete/', timetable_delete, name='timetable_delete'),
    path('timetable/<int:timetable_id>/export/master/pdf/', export_master_pdf, name='timetable_export_master_pdf'),
    path('timetable/<int:timetable_id>/export/class/<int:class_id>/pdf/', export_class_pdf, name='timetable_export_class_pdf'),
    path('timetable/<int:timetable_id>/export/teacher/pdf/', export_teacher_pdf, name='timetable_export_my_pdf'),
    path('timetable/<int:timetable_id>/export/teacher/<int:teacher_id>/pdf/', export_teacher_pdf, name='timetable_export_teacher_pdf'),
    path('timetable/<int:timetable_id>/export/all-classes/pdf/', export_all_class_pdfs, name='timetable_export_all_classes'),
    path('timetable/<int:timetable_id>/export/all-teachers/pdf/', export_all_teacher_pdfs, name='timetable_export_all_teachers'),
    path('timetable/<int:timetable_id>/export/excel/', export_master_excel, name='timetable_export_excel'),
]


# Uploaded media (photos, logos, seals, signatures) must be served even when
# DEBUG is false: the offline LAN deployment and the pre-R2 Railway setup both
# rely on local file storage, and without this every /media/ URL 404s.
if not settings.USE_S3:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

from django.urls import path

from core.views.parent_portal import (
    parent_attendance,
    parent_dashboard,
    parent_fees,
    parent_login,
    parent_logout,
    parent_marks,
    parent_student_detail,
)

app_name = "parent"

urlpatterns = [
    path("", parent_login, name="login"),
    path("logout/", parent_logout, name="logout"),
    path("dashboard/", parent_dashboard, name="dashboard"),
    path("details/", parent_student_detail, name="student_detail"),
    path("marks/", parent_marks, name="marks"),
    path("attendance/", parent_attendance, name="attendance"),
    path("fees/", parent_fees, name="fees"),
]

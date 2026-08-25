from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def student_list(request):
    return render(request, "students/list.html", {})


@login_required
def student_create(request):
    return render(request, "students/create.html", {})


@login_required
def student_detail(request, pk):
    return render(request, "students/detail.html", {})


@login_required
def student_edit(request, pk):
    return render(request, "students/edit.html", {})


@login_required
def teacher_list(request):
    return render(request, "teachers/list.html", {})


@login_required
def teacher_create(request):
    return render(request, "teachers/create.html", {})


@login_required
def teacher_detail(request, pk):
    return render(request, "teachers/detail.html", {})


@login_required
def teacher_assignments(request):
    return render(request, "teachers/assignments.html", {})


@login_required
def reports_hub(request):
    return render(request, "reports/hub.html", {})


@login_required
def settings_page(request):
    return render(request, "settings/page.html", {})

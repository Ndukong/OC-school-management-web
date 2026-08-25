from django.shortcuts import get_object_or_404, render

from core.models import AcademicTerm, SchoolClass
from core.utils.compute_results import compute_term_results
from core.utils.permissions import role_required


@role_required("admin")
def compute_results(request):
    classes = SchoolClass.objects.all().order_by("sort_order")
    terms = AcademicTerm.objects.all().order_by("year_start", "term_number")
    context = {
        "classes": classes,
        "terms": terms,
        "results": None,
    }

    if request.method == "POST":
        school_class = get_object_or_404(SchoolClass, pk=request.POST.get("class_id"))
        term = get_object_or_404(AcademicTerm, pk=request.POST.get("term_id"))
        context.update(
            {
                "results": compute_term_results(school_class, term),
                "school_class": school_class,
                "term": term,
            }
        )

    return render(request, "results/compute_results.html", context)

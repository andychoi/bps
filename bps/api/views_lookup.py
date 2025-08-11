# views_lookup.py
from django.http import JsonResponse, Http404
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from ..access import allowed_orgunits_qs

PAGE = 30

def header_options(request, layout_year_id, model_name):
    # model_name is lowercase (e.g. "orgunit")
    try:
        ct = ContentType.objects.get(model=model_name)
    except ContentType.DoesNotExist:
        raise Http404("Unknown dimension")

    Model = ct.model_class()
    q = request.GET.get("q", "")
    page = int(request.GET.get("page", 1))
    if model_name == "orgunit":
        qs = allowed_orgunits_qs(request.user, request)
    else:
        qs = Model.objects.all()

    if q:
        crit = Q(name__icontains=q) | Q(code__icontains=q)
        qs = qs.filter(crit) if hasattr(Model, "code") else qs.filter(name__icontains=q)

    total = qs.count()
    items = []
    for obj in qs.order_by("name" if hasattr(Model, "name") else "pk")[(page-1)*PAGE: page*PAGE]:
        text = getattr(obj, "code", None) or getattr(obj, "name", str(obj))
        items.append({"id": obj.pk, "text": text})

    return JsonResponse({
        "results": items,
        "pagination": {"more": page * PAGE < total},
    })
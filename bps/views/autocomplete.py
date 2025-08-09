# bps/autocomplete.py

from dal_select2.views import Select2QuerySetView
from dal_select2.widgets import ModelSelect2, ModelSelect2Multiple
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from ..models.models import (
    PlanningLayout,
    Year,
    Period,
    OrgUnit,
    Account,
    InternalOrder,
    CBU,
    UnitOfMeasure,
    PlanningLayoutYear,
    KeyFigure
)
from ..models.models_dimension import Service, Version

class ServiceAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = Service.objects.filter(is_active=True)
        if self.q: qs = qs.filter(Q(code__icontains=self.q)|Q(name__icontains=self.q))
        return qs

class KeyFigureAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = KeyFigure.objects.all()
        if self.q: qs = qs.filter(Q(code__icontains=self.q)|Q(name__icontains=self.q))
        return qs

class VersionAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = Version.objects.all()
        if self.q: qs = qs.filter(Q(code__icontains=self.q)|Q(name__icontains=self.q))
        return qs
    
class LayoutAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = PlanningLayout.objects.all()
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs
    
class ContentTypeAutocomplete(Select2QuerySetView):
    """
    Autocomplete for Django ContentType objects.
    """
    def get_queryset(self):
        qs = ContentType.objects.all()
        if self.q:
            qs = qs.filter(
                Q(model__icontains=self.q) |
                Q(app_label__icontains=self.q)
            )
        return qs


class YearAutocomplete(Select2QuerySetView):
    """
    Autocomplete for Year InfoObject.
    """
    def get_queryset(self):
        qs = Year.objects.all()
        if self.q:
            qs = qs.filter(
                Q(code__icontains=self.q) |
                Q(name__icontains=self.q)
            )
        return qs


class PeriodAutocomplete(Select2QuerySetView):
    """
    Autocomplete for Period (months 01–12).
    """
    def get_queryset(self):
        qs = Period.objects.all()
        if self.q:
            qs = qs.filter(
                Q(code__icontains=self.q) |
                Q(name__icontains=self.q)
            )
        return qs


class OrgUnitAutocomplete(Select2QuerySetView):
    """
    Autocomplete for organizational units.
    """
    def get_queryset(self):
        qs = OrgUnit.objects.all()
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs


class AccountAutocomplete(Select2QuerySetView):
    """
    Autocomplete for Account objects.
    """
    def get_queryset(self):
        qs = Account.objects.all()
        if self.q:
            qs = qs.filter(
                Q(code__icontains=self.q) |
                Q(name__icontains=self.q)
            )
        return qs


class InternalOrderAutocomplete(Select2QuerySetView):
    """
    Autocomplete for InternalOrder objects.
    """
    def get_queryset(self):
        qs = InternalOrder.objects.all()
        if self.q:
            qs = qs.filter(
                Q(code__icontains=self.q) |
                Q(name__icontains=self.q)
            )
        return qs


class CBUAutocomplete(Select2QuerySetView):
    """
    Autocomplete for Client Business Units.
    """
    def get_queryset(self):
        qs = CBU.objects.all()
        if self.q:
            qs = qs.filter(
                Q(code__icontains=self.q) |
                Q(name__icontains=self.q)
            )
        return qs


class PriceTypeAutocomplete(Select2QuerySetView):
    """
    Autocomplete for PriceType InfoObjects.
    """
    def get_queryset(self):
        qs = PriceType.objects.all()
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs


class UnitOfMeasureAutocomplete(Select2QuerySetView):
    """
    Autocomplete for UnitOfMeasure objects.
    """
    def get_queryset(self):
        qs = UnitOfMeasure.objects.all()
        if self.q:
            qs = qs.filter(
                Q(code__icontains=self.q) |
                Q(name__icontains=self.q)
            )
        return qs


class LayoutYearAutocomplete(Select2QuerySetView):
    """
    Autocomplete for PlanningLayoutYear, filtering by layout name or year code.
    """
    def get_queryset(self):
        qs = PlanningLayoutYear.objects.select_related('layout', 'year', 'version')
        if self.q:
            qs = qs.filter(
                Q(layout__name__icontains=self.q) |
                Q(year__code__icontains=self.q) |
                Q(version__code__icontains=self.q)
            )
        return qs
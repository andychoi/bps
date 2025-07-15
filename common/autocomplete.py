# autocomplete.py
from dal import autocomplete
from dal_select2.views import Select2QuerySetView

""" Select2 style issue: https://stackoverflow.com/questions/75249988/why-is-django-autocomplete-light-single-select-badly-styled-and-broken-when-mult
"""
from django.contrib.auth import get_user_model
UserModel = get_user_model()
from .models import OrgUnit, OrgLevel
from django.db.models import Count, Q

class UserAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = UserModel.objects.all()
        if self.q:
            qs = qs.filter(
                Q(username__icontains=self.q) | Q(first_name__icontains=self.q) | Q(last_name__icontains=self.q)
            )
        return qs

class AuthUserAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        # Ensure the user is authenticated
        if not self.request.user.is_authenticated:
            return UserModel.objects.none()

        qs = UserModel.objects.filter(is_active=True)

        # If the current user is a superuser, return all users
        if self.request.user.is_superuser:
            pass
        else:
            # Non-superusers should only see certain users
            qs = qs.filter(is_superuser=False)
        
        # Autocomplete search
        if self.q:
            qs = qs.filter(
                Q(username__icontains=self.q) | Q(first_name__icontains=self.q) | Q(last_name__icontains=self.q)
            )
        return qs

class OrgUnitAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        # start with all active units
        qs = OrgUnit.objects.filter(is_active=True)

        # if the user hasn't typed anything yet (no self.q),
        # restrict to their own unit + descendants:
        if not self.q:
            org_id = self.forwarded.get('orgunit') or getattr(self.request.user, 'orgunit_id', None)
            if org_id:
                try:
                    root = OrgUnit.objects.get(pk=org_id)
                    descendants = root.get_descendants()  # your helper
                    qs = qs.filter(pk__in=[root.pk] + [o.pk for o in descendants])
                except OrgUnit.DoesNotExist:
                    pass

        # if the user has typed (self.q), filter across name & code:
        if self.q:
            qs = qs.filter(
                Q(name__icontains=self.q) |
                Q(code__icontains=self.q)
            )

        return qs
        
    def get_result_label(self, item):
        # show “Level – Name”
        return f"{item.get_level_display()} - {item.name}"

    def get_selected_result_label(self, item):
        # same label once selected
        return self.get_result_label(item)

    def get_result_value(self, item):
        # return the PK so your filters can still validate
        return item.pk


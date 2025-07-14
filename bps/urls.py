# bps/urls.py
from django.urls import path, include
from django.contrib.contenttypes.models import ContentType
from dal import autocomplete

from . import views
from .autocomplete import (
    LayoutAutocomplete, ContentTypeAutocomplete,
    YearAutocomplete, PeriodAutocomplete,
    OrgUnitAutocomplete, CBUAutocomplete,
    AccountAutocomplete, InternalOrderAutocomplete,
    UnitOfMeasureAutocomplete, LayoutYearAutocomplete,
)
from .models import Year, Period, OrgUnit, CBU, Account, InternalOrder, CostCenter, UnitOfMeasure, PlanningLayoutYear

app_name = "bps"

urlpatterns = [
    # Dashboard & basics
    path("",            views.dashboard,    name="dashboard"),
    path("profile/",    views.profile,      name="profile"),
    path("inbox/",      views.inbox,        name="inbox"),
    path("notifications/", views.notifications, name="notifications"),

    # --- Manual Planning ---
    # Step 1: pick layout/year/version
    path(
        "planning/manual/select/",
        views.ManualPlanningSelectView.as_view(),
        name="manual_planning_select",
    ),
    # Step 2: show the grid
    path(
        "planning/manual/<int:layout_id>/<int:year_id>/<int:version_id>/",
        views.ManualPlanningView.as_view(),
        name="manual_planning",
    ),

    # --- Constants, formulas, sub-formulas, etc. ---
    path("constants/",    views.constant_list,      name="constant_list"),
    path("subformulas/",  views.subformula_list,    name="subformula_list"),
    path("formulas/",     views.formula_list,       name="formula_list"),
    path("formulas/run/<int:pk>/", views.formula_run, name="formula_run"),

    # planning functions
    path("copy-actual/",    views.copy_actual,   name="copy_actual"),
    path("distribute-key/", views.distribute_key, name="distribute_key"),
    path("functions/",            views.planning_function_list,  name="planning_function_list"),
    path("functions/run/<int:pk>/<int:session_id>/", views.run_planning_function, name="run_function"),

    # reference data
    path("reference-data/", views.reference_data_list, name="reference_data_list"),

    # data requests & facts
    path("data-requests/",               views.data_request_list,    name="data_request_list"),
    path("data-requests/<uuid:pk>/",     views.data_request_detail,  name="data_request_detail"),
    path("requests/<uuid:request_id>/facts/", views.fact_list,        name="fact_list"),

    # global variables
    path("variables/", views.variable_list, name="variable_list"),

    # planning sessions
    path("sessions/",       views.session_list,   name="session_list"),
    path("sessions/<int:session_id>/advance/",views.advance_stage, name="advance_stage",),
    path("sessions/<int:pk>/", views.session_detail, name="session_detail"),

    # --- Autocomplete endpoints ---
    path("autocomplete/layout/",        LayoutAutocomplete.as_view(), name="layout-autocomplete"),
    path("autocomplete/contenttype/",   ContentTypeAutocomplete.as_view(), name="contenttype-autocomplete"),
    path("autocomplete/year/",          YearAutocomplete.as_view(),    name="year-autocomplete"),
    path("autocomplete/period/",        PeriodAutocomplete.as_view(),  name="period-autocomplete"),
    path("autocomplete/orgunit/",       OrgUnitAutocomplete.as_view(), name="orgunit-autocomplete"),
    path("autocomplete/cbu/",           CBUAutocomplete.as_view(),     name="cbu-autocomplete"),
    path("autocomplete/account/",       AccountAutocomplete.as_view(), name="account-autocomplete"),
    path("autocomplete/internalorder/", InternalOrderAutocomplete.as_view(), name="internalorder-autocomplete"),
    path("autocomplete/uom/",           UnitOfMeasureAutocomplete.as_view(), name="uom-autocomplete"),
    path("autocomplete/layoutyear/",    LayoutYearAutocomplete.as_view(),   name="layoutyear-autocomplete"),

    # --- API URLs (DRF) ---
    path("api/", include("bps.api.urls")),
]
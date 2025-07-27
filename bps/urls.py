# urls.py
from django.urls import path, include
from .views import (
    DashboardView, ProfileView, InboxView, NotificationsView,
    ManualPlanningSelectView, ManualPlanningView,
    PlanningSessionListView, PlanningSessionDetailView, AdvanceStageView,
    ConstantListView, SubFormulaListView, FormulaListView, FormulaRunView,
    CopyActualView, DistributeKeyView,
    PlanningFunctionListView, RunPlanningFunctionView,
    ReferenceDataListView, DataRequestListView, DataRequestDetailView,
    FactListView, VariableListView,
)
from .autocomplete import (
    LayoutAutocomplete, ContentTypeAutocomplete,
    YearAutocomplete, PeriodAutocomplete,
    OrgUnitAutocomplete, CBUAutocomplete,
    AccountAutocomplete, InternalOrderAutocomplete,
    UnitOfMeasureAutocomplete, LayoutYearAutocomplete,
)

# viewset and router imports
from rest_framework.routers import DefaultRouter
from .viewsets import PlanningFactViewSet, OrgUnitViewSet
router = DefaultRouter()
router.register(r'facts',    PlanningFactViewSet, basename='facts')
router.register(r'orgunits', OrgUnitViewSet,    basename='orgunits')
urlpatterns = [
    path('', include(router.urls)),
    # --- API URLs (DRF) ---
    path("api/", include("bps.api.urls")),
]


app_name = "bps"

urlpatterns += [
    # Dashboard & basics
    path("",                 DashboardView.as_view(),    name="dashboard"),
    path("profile/",         ProfileView.as_view(),      name="profile"),
    path("inbox/",           InboxView.as_view(),        name="inbox"),
    path("notifications/",   NotificationsView.as_view(),name="notifications"),

    # Manual Planning
    path(
        "planning/manual/select/",
        ManualPlanningSelectView.as_view(),
        name="manual_planning_select",
    ),
    path(
        "planning/manual/<int:layout_id>/<int:year_id>/<int:version_id>/",
        ManualPlanningView.as_view(),
        name="manual_planning",
    ),

    # Constants, sub-formulas, formulas
    path("constants/",       ConstantListView.as_view(),       name="constant_list"),
    path("subformulas/",     SubFormulaListView.as_view(),     name="subformula_list"),
    path("formulas/",        FormulaListView.as_view(),        name="formula_list"),
    path("formulas/run/<int:pk>/", FormulaRunView.as_view(),     name="formula_run"),

    # Planning functions
    path("copy-actual/",     CopyActualView.as_view(),         name="copy_actual"),
    path("distribute-key/",  DistributeKeyView.as_view(),      name="distribute_key"),
    path("functions/",       PlanningFunctionListView.as_view(), name="planning_function_list"),
    path("functions/run/<int:pk>/<int:session_id>/",
         RunPlanningFunctionView.as_view(),                   name="run_function"),

    # Reference data
    path("reference-data/",  ReferenceDataListView.as_view(),  name="reference_data_list"),

    # Data requests & facts
    path("data-requests/",               DataRequestListView.as_view(),       name="data_request_list"),
    path("data-requests/<uuid:pk>/",     DataRequestDetailView.as_view(),     name="data_request_detail"),
    path("requests/<uuid:request_id>/facts/", FactListView.as_view(),            name="fact_list"),

    # Global variables
    path("variables/",      VariableListView.as_view(),      name="variable_list"),

    # Planning sessions
    path("sessions/",       PlanningSessionListView.as_view(),   name="session_list"),
    path("sessions/<int:session_id>/advance/",
         AdvanceStageView.as_view(),                            name="advance_stage"),
    path("sessions/<int:pk>/", PlanningSessionDetailView.as_view(), name="session_detail"),

    # Autocomplete endpoints
    path("autocomplete/layout/",      LayoutAutocomplete.as_view(),      name="layout-autocomplete"),
    path("autocomplete/contenttype/", ContentTypeAutocomplete.as_view(), name="contenttype-autocomplete"),
    path("autocomplete/year/",        YearAutocomplete.as_view(),        name="year-autocomplete"),
    path("autocomplete/period/",      PeriodAutocomplete.as_view(),      name="period-autocomplete"),
    path("autocomplete/orgunit/",     OrgUnitAutocomplete.as_view(),     name="orgunit-autocomplete"),
    path("autocomplete/cbu/",         CBUAutocomplete.as_view(),         name="cbu-autocomplete"),
    path("autocomplete/account/",     AccountAutocomplete.as_view(),     name="account-autocomplete"),
    path("autocomplete/internalorder/", InternalOrderAutocomplete.as_view(), name="internalorder-autocomplete"),
    path("autocomplete/uom/",         UnitOfMeasureAutocomplete.as_view(), name="uom-autocomplete"),
    path("autocomplete/layoutyear/",  LayoutYearAutocomplete.as_view(),   name="layoutyear-autocomplete"),

    # API URLs (DRF)
    path("api/", include("bps.api.urls")),
]
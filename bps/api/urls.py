from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .api import (
    PlanningGridView,
    PlanningGridBulkUpdateView,
)
from .views_manual import ManualPlanningGridAPIView
from ..views.viewsets import PlanningFactViewSet, OrgUnitViewSet
from .views import PlanningFactPivotedAPIView
from .views_lookup import header_options

app_name = "bps_api"

# Router for REST viewsets
router = DefaultRouter()
router.register(r'facts',    PlanningFactViewSet,  basename='facts')
router.register(r'orgunits', OrgUnitViewSet,     basename='orgunits')

urlpatterns = [
    # built-in viewsets
    path("", include(router.urls)),

    # manual planning UI endpoints (used by Tabulator)
    path(
        "manual-grid/",
        ManualPlanningGridAPIView.as_view(),
        name="manual_planning_grid",
    ),

    # JSON grid endpoints (simpler planning-grid endpoints are best reserved for other grid UI use-cases (e.g. ad-hoc exports, dashboards, etc.).
    path(
        "grid/",
        PlanningGridView.as_view(),
        name="planning_grid",
    ),
    path(
        "grid-update/",
        PlanningGridBulkUpdateView.as_view(),
        name="planning_grid_update",
    ),

    # pivot endpoint (if still needed by other UIs)
    path(
        "pivot/",
        PlanningFactPivotedAPIView.as_view(),
        name="planning_pivot",
    ),

    path("api/layout/<int:layout_year_id>/header-options/<str:model_name>/", header_options, name="header-options"),

]
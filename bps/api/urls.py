# bps/api/urls.py
from django.urls import path, include
from .views_manual import ManualPlanningGridAPIView, PlanningGridAPIView, PlanningGridBulkUpdateAPIView
from .views import PlanningFactPivotedAPIView
from ..views.viewsets import PlanningFactViewSet, OrgUnitViewSet
from rest_framework.routers import DefaultRouter

app_name = "bps_api"

router = DefaultRouter()
router.register(r'facts',    PlanningFactViewSet, basename='facts')
router.register(r'orgunits', OrgUnitViewSet,    basename='orgunits')

urlpatterns = [
    # DRF router
    path("", include(router.urls)),

    # Extra endpoints
    path("bps_planning_grid/",          PlanningGridAPIView.as_view(),       name="bps_planning_grid"),
    path("planning-grid/",              ManualPlanningGridAPIView.as_view(), name="manual_planning_grid"),
    path("bps_planning_grid_update/",   PlanningGridBulkUpdateAPIView.as_view(), name="bps_planning_grid_update"),
    path("bps_planning_pivot/",         PlanningFactPivotedAPIView.as_view(),   name="bps_planning_pivot"),
]
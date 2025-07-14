from django.urls import path
from .views_manual import ManualPlanningGridAPIView, PlanningGridAPIView, PlanningGridBulkUpdateAPIView
from .views import PlanningFactPivotedAPIView

app_name = "bps_api"

urlpatterns = [
    path(
        "bps_planning_grid/", PlanningGridAPIView.as_view(), name="bps_planning_grid",),
    path('planning-grid/', ManualPlanningGridAPIView.as_view(), name='manual-planning-grid'),
    path("bps_planning_grid_update/", PlanningGridBulkUpdateAPIView.as_view(), name="bps_planning_grid_update",),
    path("bps_planning_pivot/", PlanningFactPivotedAPIView.as_view(), name="bps_planning_pivot",),
]
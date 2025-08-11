# models/admin_proxy.py
from django.db import models
from .models_layout import PlanningLayout

class PlanningAdminDashboard(PlanningLayout):
    class Meta:
        proxy = True
        verbose_name = "Planning Admin Dashboard"
        verbose_name_plural = "Planning Admin Dashboard"
# common/choices.py

from django.db import models

USERTYPE_CHOICES  = (
    ("ADM",   "Admin"),
    ("EMP",   "Employee"),
    ("TEM",   "Contractor"),
    ("CUS",   "Customer"),
    ("VEN",   "Vendor"),
)

class UserTypeChoices(models.TextChoices):
    ADMIN = 'ADM', "Admin"
    EMPLOYEE = 'EMP', "Employee"
    CONTRACTOR = 'TEM', "Contractor"
    CUSTOMER = 'CUS', "Customer"
    VENDOR = 'VEN', "Vendor"
    UNKNOWN = 'UNK', "Unknown"

class OrgCategoryChoices(models.TextChoices):
    DIRECT = 'DIRECT', 'Direct'  # Revenue-generating or client-facing teams (e.g., Product, Consulting)
    SUPPORT = 'SUPPORT', 'Support'  # Internal IT, HR, Finance, or Legal supporting business operations
    ADMIN = 'ADMIN', 'Admin'  # Executive management, administrative, and overhead functions
    NOT = 'NOT', 'Not Categorized'  # Departments that don’t fit into the above categories
Below is a recipe for wiring up a fully generic, regex-driven hierarchy that you can attach to any bps dimension.  You’ll get:
	1.	A Hierarchy container
	2.	A self-referencing HierarchyNode with a regex field for matching values
	3.	(Optional) A little helper you can call at runtime to classify a raw dimension value into the right node
	4.	Admin classes so you can manage the tree inline in Django’s admin

⸻

1. Models

# bps/models.py

import re
from django.db import models
from django.core.exceptions import ValidationError

class Hierarchy(models.Model):
    """
    A named hierarchy (e.g. 'CBU Regions', 'Product Families', 'Account Segments').
    """
    name        = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Hierarchy"
        verbose_name_plural = "Hierarchies"

    def __str__(self):
        return self.name


class HierarchyNode(models.Model):
    """
    A single node in a Hierarchy, with an optional regex
    that will match raw values and assign them to this node.
    """
    hierarchy = models.ForeignKey(
        Hierarchy,
        on_delete=models.CASCADE,
        related_name="nodes"
    )
    parent    = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="children"
    )
    name      = models.CharField(max_length=100)
    regex     = models.CharField(
        max_length=200,
        blank=True,
        help_text="A Python-style regex that, when matched against a raw dimension value, assigns that value to this node."
    )
    order     = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = (('hierarchy', 'name'),)
        ordering = ('hierarchy', 'order',)

    def __str__(self):
        return f"{self.hierarchy.name}: {self.name}"

    def clean(self):
        # ensure the regex compiles
        if self.regex:
            try:
                re.compile(self.regex)
            except re.error as e:
                raise ValidationError({'regex': f"Invalid regex: {e}"})

    def matches(self, raw_value: str) -> bool:
        """Return True if this node’s regex matches the supplied raw_value."""
        if not self.regex:
            return False
        return bool(re.search(self.regex, raw_value))


# Optional utility: assign a raw_value to the first matching node
def classify_value(hierarchy: Hierarchy, raw_value: str) -> HierarchyNode:
    """
    Given a Hierarchy and a raw dimension value (string),
    return the first node whose regex matches, or None.
    """
    for node in hierarchy.nodes.order_by('order'):
        if node.matches(raw_value):
            return node
    return None


⸻

2. Admin

# bps/admin.py

from django.contrib import admin
from .models import Hierarchy, HierarchyNode

class HierarchyNodeInline(admin.TabularInline):
    model = HierarchyNode
    extra = 1
    fields = ('name', 'parent', 'regex', 'order')
    show_change_link = True

@admin.register(Hierarchy)
class HierarchyAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    inlines = [HierarchyNodeInline]


@admin.register(HierarchyNode)
class HierarchyNodeAdmin(admin.ModelAdmin):
    list_display  = ('name', 'hierarchy', 'parent', 'order')
    list_filter   = ('hierarchy',)
    search_fields = ('name', 'regex')

	•	HierarchyAdmin lets you create a hierarchy and, inline, add/edit/delete its nodes.
	•	HierarchyNodeAdmin gives you a flat view of all nodes across hierarchies.

⸻

3. Wiring it into your bps code
	1.	Capture the raw dimension value (e.g. a CBU code or account string) in your form, just as you do today with other dimensions.
	2.	Classify it before saving:

from bps.models import classify_value

raw = "NA-01 West Coast"
node = classify_value(my_hierarchy, raw)
if node:
    rec.dimension_values['CBU_HierarchyNode'] = node.pk


	3.	Querying becomes easy: filter on dimension_values__CBU_HierarchyNode=5 or look up the node and then get all child nodes via node.get_descendants() (you can write a small helper for that).

⸻

🛠️ Migrations

After adding the two models above, run:

python manage.py makemigrations bps
python manage.py migrate


⸻

With this in place you now have:
	•	A reusable Hierarchy/Node pattern for any dimension
	•	The power of regex to bucket arbitrary text into nodes
	•	A Django-admin-friendly interface to draw trees

Let me know if you’d like helper methods for descendant-lookup or bulk-classification utilities!
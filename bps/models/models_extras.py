# models_extras.py
from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class DimensionKey(models.Model):
    """
    Registry of allowed extra dimension keys and which model they must point to.
    Keeps keys consistent and prevents typos.
    """
    key = models.CharField(max_length=64, unique=True)  # e.g. "market", "channel"
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True, db_index=True) 
    
    def __str__(self):
        return self.key


class PlanningFactExtra(models.Model):
    """
    One row per (fact, key) pair. Value is a Generic FK to the specific
    dimension row, enforced via DimensionKey.content_type.
    """
    fact = models.ForeignKey(
        "bps.PlanningFact",
        on_delete=models.CASCADE,
        related_name="extras",
        db_index=True,
    )

    # Which logical dimension (market, channel, product_line, …)
    key = models.ForeignKey(DimensionKey, on_delete=models.PROTECT, db_index=True)

    # Polymorphic FK to the chosen dimension row
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id    = models.PositiveIntegerField()
    value_obj    = GenericForeignKey("content_type", "object_id")

    class Meta:
        # a fact can have at most one value for a given logical key
        constraints = [
            models.UniqueConstraint(fields=["fact", "key"], name="uniq_fact_key"),
        ]
        indexes = [
            models.Index(
                fields=["key", "content_type", "object_id"],
                name="bps_factextra_ct_obj_idx",
            ),
        ]

    def clean(self):
        # Enforce the key points to the correct model type
        if self.key_id and self.content_type_id:
            if self.key.content_type_id != self.content_type_id:
                from django.core.exceptions import ValidationError
                raise ValidationError(
                    {"content_type": f"Key '{self.key.key}' must reference {self.key.content_type}."}
                )
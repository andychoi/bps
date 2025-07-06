Yes—given that Amount and Quantity are by far the most common key-figures, it often makes sense to pull them out of the generic key_figure/value pattern and make them first-class fields on your fact model, with an explicit Unit-of-Measure (UoM) and a ConversionRate table to handle reference‐unit lookups. This improves performance (no JSON lookups for 90% of use-cases), enforces data consistency, and simplifies UoM conversions.

⸻

1. Enhanced PlanningFact model

class UnitOfMeasure(models.Model):
    """
    Master list of units (e.g. 'EA', 'KG', 'HRS', 'USD').
    The 'base' flag marks the canonical target for conversions.
    """
    code        = models.CharField(max_length=10, unique=True)
    name        = models.CharField(max_length=50)
    is_base     = models.BooleanField(default=False,
                                      help_text="Target unit for conversion rates")
    def __str__(self):
        return self.code

class ConversionRate(models.Model):
    """
    Conversion factors between units:
      value_in_to_unit = factor * value_in_from_unit
    """
    from_uom = models.ForeignKey(UnitOfMeasure, on_delete=models.CASCADE,
                                 related_name='conv_from')
    to_uom   = models.ForeignKey(UnitOfMeasure, on_delete=models.CASCADE,
                                 related_name='conv_to')
    factor   = models.DecimalField(max_digits=18, decimal_places=6,
                                   help_text="Multiply a from_uom value by this to get to_uom")
    class Meta:
        unique_together = ('from_uom','to_uom')
    def __str__(self):
        return f"1 {self.from_uom} → {self.factor} {self.to_uom}"

class PlanningFact(models.Model):
    """
    One “row” of plan data for a given DataRequest + Period.
    Most plans have both Quantity and Amount; we surface them.
    """
    request      = models.ForeignKey(DataRequest,
                                     on_delete=models.PROTECT,
                                     related_name='facts')
    session      = models.ForeignKey(PlanningSession,
                                     on_delete=models.CASCADE,
                                     related_name='facts')
    period       = models.CharField(max_length=10)     # '01','Q1','H1'
    row_values   = models.JSONField(default=dict,
                 help_text="Dynamic dims: {'OrgUnit':12,'Product':34}")

    # ← First-class key-figures instead of value      = models.DecimalField(max_digits=18, decimal_places=2)
    quantity     = models.DecimalField(max_digits=18, decimal_places=3,
                                       default=0,
                                       help_text="Planned quantity in quantity_uom")
    quantity_uom = models.ForeignKey(UnitOfMeasure,
                                     on_delete=models.PROTECT,
                                     related_name='+',
                                     null=True, blank=True)
    amount       = models.DecimalField(max_digits=18, decimal_places=2,
                                       default=0,
                                       help_text="Planned amount in amount_uom")
    amount_uom   = models.ForeignKey(UnitOfMeasure,
                                     on_delete=models.PROTECT,
                                     related_name='+',
                                     null=True, blank=True)

    # ← Legacy generic slot, for any other key-figure
    other_key_figure = models.CharField(max_length=100, blank=True)
    other_value      = models.DecimalField(max_digits=18, decimal_places=2,
                                           null=True, blank=True)

    class Meta:
        unique_together = (
            'request','period','other_key_figure','row_values'
        )
    def __str__(self):
        return (f"{self.session} | {self.period} | "
                f"Qty={self.quantity}{self.quantity_uom or ''}  "
                f"Amt={self.amount}{self.amount_uom or ''}")

Why this helps
	1.	Performance: 99% of your queries (“show me quantities and amounts by OrgUnit/Period”) can use direct columns and fast B-tree indexes, not JSON lookups.
	2.	Data Integrity: UoM is enforced via FK, and you can cascade or restrict deletes.
	3.	Conversion: A ConversionRate table normalizes cross-UoM math (e.g. convert hours→days, pieces→cases, USD→EUR).

⸻

2. Converting on the fly

Add a helper on PlanningFact:

    def get_amount_in(self, target_uom_code):
        """
        Return self.amount converted into the unit target_uom_code.
        """
        if not self.amount_uom:
            return None
        if self.amount_uom.code == target_uom_code:
            return self.amount
        to_uom = UnitOfMeasure.objects.get(code=target_uom_code, is_base=True)
        rate  = ConversionRate.objects.get(
            from_uom=self.amount_uom,
            to_uom=to_uom
        ).factor
        return round(self.amount * rate, 2)

You can similarly convert the quantity field.

⸻

3. Admin & Forms updates

Admin

@admin.register(UnitOfMeasure)
class UoMAdmin(admin.ModelAdmin):
    list_display = ('code','name','is_base')

@admin.register(ConversionRate)
class ConversionRateAdmin(admin.ModelAdmin):
    list_display = ('from_uom','to_uom','factor')

class PlanningFactAdmin(admin.ModelAdmin):
    list_display = ('session','period','quantity','quantity_uom',
                    'amount','amount_uom','other_key_figure','other_value')
    list_filter  = ('quantity_uom','amount_uom','period')

Form

class PlanningFactForm(forms.ModelForm):
    class Meta:
        model = PlanningFact
        fields = [
          'period','quantity','quantity_uom',
          'amount','amount_uom',
          'other_key_figure','other_value',
        ]
        widgets = {
          'period': forms.TextInput(attrs={'placeholder':'01, Q1, H1'}),
          'quantity_uom': autocomplete.ModelSelect2(url='uom-autocomplete'),
          'amount_uom':   autocomplete.ModelSelect2(url='uom-autocomplete'),
        }


⸻

4. Suggested Next Steps
	1.	Data-Mart ETL: nightly flattening into a star schema on (OrgUnit,Period,Version) with aggregated sums/averages.
	2.	UoM Base Unit: pick a canonical base per dimension (e.g. ‘EA’, ‘USD’) and index conversion rates from every unit to base for faster queries.
	3.	Rich Validation: enforce that amount/quantity can’t both be zero, or if one is zero, the other must be populated.
	4.	Performance: add B-tree indexes on (quantity_uom), (amount_uom), and multi-column on (session,period).
	5.	Reporting: build convenience views that expose “amount per quantity” (unit cost) as a computed property.

⸻

Conclusion

By promoting quantity and amount (plus their UoMs) to dedicated columns, and pairing them with a ConversionRate table, you get far more efficient queries, stronger data integrity, and straightforward unit conversions—without losing the ability to store other exotic key-figures in your generic slots.
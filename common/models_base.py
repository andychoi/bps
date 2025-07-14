
from django.db import models
from django.utils.translation import gettext_lazy as _

# from apps.psm.models import BaseModel
class BaseModel(models.Model):
    created_at = models.DateTimeField(_("created at"), auto_now_add=True, editable=False)
    updated_on = models.DateTimeField(_("updated_on"), auto_now=True, editable=False)
    created_by = models.ForeignKey('users.User', related_name='created_by_%(class)s_related', verbose_name=_('created by'),
                                   on_delete=models.DO_NOTHING, null=True)
    updated_by = models.ForeignKey('users.User', related_name='updated_by_%(class)s_related', verbose_name=_('updated by'),
                                   on_delete=models.DO_NOTHING, null=True)
    class Meta:
        abstract = True    


class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)
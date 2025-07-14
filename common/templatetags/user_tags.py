from django.conf import settings
from django import template

register = template.Library()

from django.contrib.auth import get_user_model

User = get_user_model()


@register.filter
def has_group(user, group_name):
    """{% if request.user|has_group:"some_group_name" %}"""
    return user.groups.filter(name=group_name).exists()


@register.filter()
def check_permission(user, permission):
    """{% if user|check_permission:'delete_bills' %}"""
    if user.user_permissions.filter(codename=permission).exists():
        return True
    return False


@register.simple_tag(takes_context=True)
def get_session_value(context, key):
    """
    A custom template tag to safely access session variables in Django templates.
    Usage: {% get_session_value 'key' as session_value %}
    """
    request = context["request"]
    return request.session.get(key, None)


@register.simple_tag(takes_context=True)
def is_original_user_superuser(context):
    """
    Template tag to check if the original user (from session) is a superuser.
    Returns True if the original user is a superuser, False otherwise.
    Usage: {% is_original_user_superuser as is_superuser %}
    """
    request = context["request"]
    original_login_id = request.session.get("original_login_id")

    if original_login_id:
        try:
            original_user = User.objects.get(id=original_login_id)
            return original_user.is_superuser
        except User.DoesNotExist:
            return False
    return False


@register.simple_tag(takes_context=True)
def get_session_user_id(context):
    return get_session_value(context, "original_login_id")


@register.simple_tag(takes_context=True)
def get_selected_user(context):
    """
    example:
        <input type="text" id="selectedUser" name="selected_user" class="form-control"
        value="{% get_selected_user %}" readonly>
    """

    request = context["request"]
    # Check if 'selected_user' is in request.GET, else default to request.user
    selected_user = request.GET.get("selected_user", "")

    if not selected_user:
        selected_user = request.user.username

    return selected_user

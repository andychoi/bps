# loginas.py
from django.conf import settings
from django.shortcuts import redirect, resolve_url
from django.contrib.auth import login, logout, get_user_model
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib import messages
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

def login_as(request):
    # Only superusers may impersonate
    orig_id = request.session.get('original_login_id')
    original = User.objects.filter(pk=orig_id).first() if orig_id else request.user
    if not original.is_superuser:
        messages.error(request, "Access denied: only superusers can impersonate.")
        return redirect(settings.LOGIN_REDIRECT_URL)

    # Determine target user
    target = None
    uname = request.GET.get("username")
    if uname:
        target = User.objects.filter(username=uname).first()
    else:
        try:
            pk = int(request.GET.get("user_pk", ""))
            target = User.objects.filter(pk=pk).first()
        except (ValueError, TypeError):
            target = None

    # If no target, log out and clear impersonation
    if not target:
        logout(request)
        request.session.pop('original_login_id', None)
        messages.warning(request, "Logged out successfully.")
        logger.info(f"{original.username} ended impersonation")
        return redirect(settings.LOGIN_REDIRECT_URL)

    # Save original before swapping
    if 'original_login_id' not in request.session:
        request.session['original_login_id'] = original.pk

    # Perform login
    target.backend = 'django.contrib.auth.backends.ModelBackend'
    login(request, target)
    request.session.save()
    messages.success(request, f"You are now impersonating {target.username}.")
    logger.info(f"{original.username} is impersonating {target.username}")

    # Safe redirect
    next_url = request.GET.get('next') or settings.LOGIN_REDIRECT_URL
    if url_has_allowed_host_and_scheme(next_url, {request.get_host()}):
        return redirect(next_url)
    return redirect(settings.LOGIN_REDIRECT_URL)
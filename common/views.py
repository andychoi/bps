# common/views.py
from django.db.models import Q
from django.views.generic import ListView
from dal import autocomplete
from django.http import JsonResponse
from .autocomplete import AuthUserAutocomplete
from .user import User
from django.core.paginator import Paginator
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render

@user_passes_test(lambda u: u.is_superuser)
def loginas_list_view(request):
    return render(request, "loginas_list.html")


class UserSearchJSON(ListView): 
    model = User
    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        search_term = request.GET.get('q', '')

        # Use Q objects to search in both 'username' and 'alias'
        # users = User.objects.filter(
        #     Q(username__icontains=search_term) | Q(alias__icontains=search_term)
        # ).order_by('username').values('id', 'username', 'alias', 'job_title', 'dept_name', 'company')
        users = User.objects.filter(
            Q(username__icontains=search_term) |
            Q(alias__icontains=search_term) |
            Q(first_name__icontains=search_term) |
            Q(last_name__icontains=search_term)
        ).order_by('username').values('id', 'username', 'first_name', 'last_name', 'alias', 'job_title', 'dept_name', 'company')

        # Convert to list to allow pagination
        users_list = list(users)

        # Set up pagination
        paginator = Paginator(users_list, 10)  # Show 10 users per page
        page_number = request.GET.get('page', 1)  # Get the page number from the query parameters
        page_obj = paginator.get_page(page_number)

        user_data = list(page_obj.object_list)
        has_more = page_obj.has_next()

        return JsonResponse({
            'users': user_data,
            'has_more': has_more
        })
    

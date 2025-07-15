# apps/users/urls.py
from django.urls import path, re_path
from .autocomplete import UserAutocomplete, OrgUnitAutocomplete
from .loginas import login_as
from .views import UserSearchJSON, loginas_list_view

app_name = 'common'

urlpatterns = [
    path('api/user-search/', UserSearchJSON.as_view(), name='api-user-search'),
    path('user-autocomplete/', UserAutocomplete.as_view(), name='user-autocomplete'),
    path('orgunit-autocomplete/', OrgUnitAutocomplete.as_view(), name='orgunit-autocomplete'),

    # demo purpose only
    path('api/login_as/', login_as, name="api-login-as"),
    path('loginas/', loginas_list_view, name='loginas_list'),
]        


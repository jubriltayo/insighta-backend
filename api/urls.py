from django.urls import path
from . import views

urlpatterns = [
    path('profiles', views.profile_list, name='profile-list'),
    path('profiles/search', views.search_profiles, name='search-profiles'),
    path('profiles/<str:profile_id>', views.profile_detail, name='profile-detail'),
]
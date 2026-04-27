from django.urls import path
from . import views

urlpatterns = [
    path('profiles', views.ProfileListCreateView.as_view(), name='profile-list'),
    path('profiles/search', views.ProfileSearchView.as_view(), name='search-profiles'),
    path('profiles/<str:profile_id>', views.ProfileDetailView.as_view(), name='profile-detail'),
]
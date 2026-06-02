from django.urls import path
from django.contrib.auth import views as auth_views

from . import views

urlpatterns = [
    path("", views.RootView.as_view(), name="root"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("films/<str:film_slug>/", views.film, name="film"),
    path("c/<str:crew_slug>/", views.crew, name="crew"),
]

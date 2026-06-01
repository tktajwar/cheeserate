from django.urls import path

from . import views

urlpatterns = [
    path("", views.RootView.as_view(), name="root"),
    path("register", views.RegisterView.as_view(), name="register"),
    path("films/<str:film_slug>/", views.film, name="film"),
    path("c/<str:crew_slug>/", views.crew, name="crew"),
]

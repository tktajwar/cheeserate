from django.urls import path

from . import views

urlpatterns = [
    path("", views.root, name="root"),
    path("films/<str:film_slug>/", views.film, name="film"),
    path("c/<str:crew_slug>/", views.crew, name="crew"),
]

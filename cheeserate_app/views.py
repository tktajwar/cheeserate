from django.http import Http404, HttpResponseServerError
from django.http import HttpResponse
from django.shortcuts import render
from django.template import loader
from django.urls import reverse
from django.utils.html import format_html

from requests import ConnectionError, HTTPError

from .models import Crew, Film

# Create your views here.

def root(request):
    latest_items = [ item for item in Film.objects.order_by("-pk") ]
    context = {"latest_items": latest_items}
    return render(request, "cheeserate/index.html", context)

def film(request, film_slug):
    try:
        film = Film.get_or_create_by_slug(film_slug)
        directors = Crew.objects.filter(crewdirectedfilm__film=film)
        casts = Crew.objects.filter(crewstarringfilm__film=film)
    except HTTPError as e:
        if e.response.status_code == 404:
            raise Http404("Film does not exist")
        else:
            print(e)
            return HttpResponseServerError()
    except ConnectionError as e:
        print(e)
        return HttpResponseServerError("Connection error. API call failed.")
    try:
        print(film.update_if_appropriate())
    except ConnectionError:
        pass
    directors = ', '.join([
        format_html(
            '<a href="{}" class="underline">{}</a>',
            reverse('crew', args=[crew.trakt_slug]),
            crew.name,
        )
            for crew in directors
    ])
    casts = ', '.join([
        format_html(
            '<a href="{}" class="underline">{}</a>',
            reverse('crew', args=[crew.trakt_slug]),
            crew.name,
        )
            for crew in casts
    ])
    context = {
        "film": film,
        "directors": directors,
        "casts": casts,
    }
    return render(request, "cheeserate/film_slug.html", context)

def crew(request, crew_slug):
    try:
        crew = Crew.get_or_create_by_slug(crew_slug)
        directed_films = Film.objects.filter(
            crewdirectedfilm__director=crew
        ).distinct()
        starring_films = Film.objects.filter(
            crewstarringfilm__cast=crew
        ).distinct()
    except HTTPError as e:
        if e.response.status_code == 404:
            raise Http404("Crew does not exist")
        else:
            print(e)
            return HttpResponseServerError("Internal Server Error.")
    except ConnectionError as e:
        print(e)
        return HttpResponseServerError("Connection error. API call failed.")
    try:
        print(crew.update_if_appropriate())
    except ConnectionError:
        pass
    directing = ', '.join([
        format_html(
            '<a href="{}" class="underline">{}</a>',
            reverse('film', args=[film.trakt_slug]),
            str(film),
        )
            for film in directed_films
    ])
    starring = ', '.join([
        format_html(
            '<a href="{}" class="underline">{}</a>',
            reverse('film', args=[film.trakt_slug]),
            str(film),
        )
            for film in starring_films
    ])
    context = {
        "crew": crew,
        "directing": directing,
        "starring": starring,
    }
    return render(request, "cheeserate/crew_slug.html", context)

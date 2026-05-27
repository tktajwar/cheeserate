from django.http import Http404, HttpResponseServerError
from django.http import HttpResponse
from django.shortcuts import render
from django.template import loader

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
    context = {
        "film": film,
        "directors": directors,
        "casts": casts,
    }
    return render(request, "cheeserate/film_slug.html", context)

def crew(request, crew_slug):
    try:
        crew = Crew.get_or_create_by_slug(crew_slug)
    except HTTPError as e:
        if e.response.status_code == 404:
            raise Http404("Crew does not exist")
        else:
            print(e)
            return HttpResponseServerError("Internal Server Error.")
    except ConnectionError as e:
        print(e)
        return HttpResponseServerError("Connection error. API call failed.")
    return HttpResponse("You're looking for %s." % crew.name)

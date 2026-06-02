from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth import logout
from django.http import Http404, HttpResponseServerError
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template import loader
from django.utils.html import format_html
from django.views import View

from requests import ConnectionError, HTTPError

from .forms import UserRegisterationForm
from .models import Crew, Film

# Create your views here.

class RootView(View):
    template_name = "cheeserate/index.html"

    def get(self, request):
        films = film_list(Film.objects.order_by('-pk')[:12])
        return render(request, self.template_name, {"films": films})


class RegisterView(View):
    template_name = 'registration/register.html'

    def get(self, request):
        form = UserRegisterationForm()
        context = {
            "form": form,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        form = UserRegisterationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            messages.success(request, f"{username} account created.")
            new_user = authenticate(
                username=username,
                password=password,
            )
            login(request, new_user)
            return redirect('root')
        messages.error(request, "Account creation failed.")
        context = {
            "form": form,
        }
        return render(request, self.template_name, context)

def logout_view(request):
    logout(request)
    return redirect('login')

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
            crew.get_absolute_url(),
            crew.name,
        )
            for crew in directors
    ])
    context = {
        "film": film,
        "directors": directors,
        "casts": crew_list(casts),
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
    context = {
        "crew": crew,
        "directed_films": film_list(directed_films),
        "starring_films": film_list(starring_films),
    }
    return render(request, "cheeserate/crew_slug.html", context)


# Helper functions

def film_list(films):
    return '\n'.join([
        format_html(
            '''
            <div title="{}">
              <a href="{}">
                <figure class="w-full">
                  <img src="{}"
                       class="w-full rounded-xs shadow-md" />
                <figurecaption>{}</figurecaption>
                </figure>
              </a>
            </div>
            ''',
            f"{film.title} ({film.year})",
            film.get_absolute_url(),
            film.img(),
            film.title,
        )
        for film in films
    ])

def crew_list(crews):
    return '\n'.join([
        format_html(
            '''
            <div title="{}">
              <a href="{}">
                <figure class="w-full">
                  <img src="{}"
                       class="w-full rounded-xs shadow-md" />
                  <figurecaption>{}</figurecaption>
                </figure>
              </a>
            </div>
            ''',
            crew.name,
            crew.get_absolute_url(),
            crew.img(),
            crew.name,
        )
        for crew in crews
    ])

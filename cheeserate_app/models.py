from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.timezone import now

import requests


# Item update constants

INITIAL_INTERVAL_HOUR = 6
MAX_INTERVAL_HOUR = 72
INTERVAL_MULTIPLIER = 2

# Create your models here.

class User(models.Model):
    username = models.CharField(max_length=64, unique=True)

    def __str__(self):
        return self.username

class Item(models.Model):
    title = models.CharField(max_length=1023,null=True,blank=True)
    score_avg = models.FloatField(
        validators=[
            MinValueValidator(-1.0),
            MaxValueValidator(+1.0),
        ],
        default=0.0,
    )
    score_sum = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

class Rating(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.FloatField(
        validators=[
            MinValueValidator(-1.0),
            MaxValueValidator(+1.0),
        ]
    )
    review = models.CharField(max_length=1023, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username}'s rating of {self.item.title}"

class TraktCommon(models.Model):
    trakt_slug = models.CharField(unique=True)
    next_fetch = models.DateTimeField(default=now)
    next_interval = models.IntegerField(default=INITIAL_INTERVAL_HOUR)

    class Meta:
        abstract = True

    @classmethod
    def get_or_create_by_slug(cls, slug: str):
        slug = clean_slug(slug)
        try:
            return cls.objects.get(trakt_slug=slug)
        except cls.DoesNotExist:
            return cls.create(slug)

class TraktItemCommon(TraktCommon):
    item = models.ForeignKey(Item, on_delete=models.CASCADE)

    class Meta:
        abstract = True

    def __str__(self):
        return self.item.__str__()

    @staticmethod
    def get_directors(res: dict):
        return [
            Crew.get_or_shallow_create(
                director.get('person').get('ids').get('slug'),
                director.get('person').get('name'),
            ) for director in res.get('crew').get('directing')
            if 'Director' in director.get('jobs')
        ]


class Film(TraktItemCommon):
    title = models.CharField()
    year = models.IntegerField(null=True)
    poster_url = models.URLField(null=True)

    def get_absolute_url(self):
        return f"/films/{self.trakt_slug}"

    def add_directors(self) -> int:
        url = f"https://api.trakt.tv/movies/{self.trakt_slug}/people"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "cheeserate/1.0.0",
            "trakt-api-key": settings.TRAKT_API,
            "trakt-api-version": "2",
        }

        try:
            response = requests.get(url, headers=headers)
        except requests.ConnectionError:
            raise
        response.raise_for_status()
        res = response.json()

        updated_count = 0
        for director in self.get_directors(res):
            (_, new_added) = CrewDirectedFilm.objects.get_or_create(
                director=director,
                film=self,
            )
            updated_count += new_added

        return updated_count

    @classmethod
    def create(cls, slug: str):
        slug = clean_slug(slug)
        url = f"https://api.trakt.tv/movies/{slug}/"

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "cheeserate/1.0.0",
            "trakt-api-key": settings.TRAKT_API,
            "trakt-api-version": "2",
        }

        params = { "extended": "images" }

        try:
            response = requests.get(url, headers=headers, params=params)
        except requests.ConnectionError:
            raise
        response.raise_for_status()
        res = response.json()

        (title, year, trakt_slug) = (
            res.get('title'),
            res.get('year'),
            res.get('ids').get('slug'),
        )

        poster_url = res.get('images').get('poster')
        poster_url = poster_url[0] if len(poster_url) else None

        item = Item ( title = f"{title} ({year})" )
        item.save()

        film = Film (
            item=item,
            trakt_slug=trakt_slug,
            title=title,
            year=year,
            poster_url=poster_url,
        )
        film.save()

        film.add_directors()

        return film

    @classmethod
    def shallow_create(cls, trakt_slug: str, title: str, year: int):
        item = Item ( title = f"{title} ({year})" )
        item.save()

        film = Film (
            item=item,
            trakt_slug=trakt_slug,
            title=title,
            year=year,
        )
        film.save()

        return film

    @classmethod
    def get_or_shallow_create(cls, slug: str, title: str, year: int):
        slug = clean_slug(slug)
        try:
            return cls.objects.get(trakt_slug=slug)
        except cls.DoesNotExist:
            return cls.shallow_create(slug, title, year)

class Crew(TraktCommon):
    name = models.CharField()
    headshot_url = models.URLField(null=True)
    birth = models.DateField(null=True)
    death = models.DateField(null=True)
    biography = models.CharField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_absolute_url(self):
        return f"/crew/{self.trakt_slug}"

    def add_films(self) -> int:
        url = f"https://api.trakt.tv/people/{self.trakt_slug}/movies"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "cheeserate/1.0.0",
            "trakt-api-key": settings.TRAKT_API,
            "trakt-api-version": "2",
        }

        try:
            response = requests.get(url, headers=headers)
        except requests.ConnectionError:
            raise
        response.raise_for_status()
        res = response.json()

        updated_count = 0
        for movie in [
            movie.get('movie') for movie in
            res.get('crew').get('directing')
            if 'Director' in movie.get('jobs')
        ]:
            film_slug = movie.get('ids').get('slug')
            title = movie.get('title')
            year = movie.get('year')
            film = Film.get_or_shallow_create(
                film_slug,
                title,
                year,
            )
            (_, new_added) = CrewDirectedFilm.objects.get_or_create(
                director=self,
                film=film,
            )
            updated_count += new_added

        return updated_count

    @classmethod
    def create(cls, slug: str):
        slug = clean_slug(slug)
        url = f"https://api.trakt.tv/people/{slug}/"

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "cheeserate/1.0.0",
            "trakt-api-key": settings.TRAKT_API,
            "trakt-api-version": "2",
        }

        params = { "extended": "images" }

        try:
            response = requests.get(url, headers=headers, params=params)
        except requests.ConnectionError:
            raise
        response.raise_for_status()
        res = response.json()

        (name, birth, death, biography, trakt_slug) = (
            res.get('name'),
            res.get('birthday'),
            res.get('death'),
            res.get('biography'),
            res.get('ids').get('slug'),
        )

        headshot_url = res.get('images').get('headshot')
        headshot_url = headshot_url[0] if len(headshot_url) else None

        crew = Crew (
            name=name,
            trakt_slug=trakt_slug,
            birth=birth,
            death=death,
            biography=biography,
            headshot_url=headshot_url,
        )
        crew.save()

        return crew

    @classmethod
    def shallow_create(cls, trakt_slug: str, name: str):
        crew = Crew (
            name=name,
            trakt_slug=trakt_slug,
        )
        crew.save()

        return crew

    @classmethod
    def get_or_shallow_create(cls, slug: str, name: str):
        slug = clean_slug(slug)
        try:
            return cls.objects.get(trakt_slug=slug)
        except cls.DoesNotExist:
            return cls.shallow_create(slug, name)

class CrewDirectedFilm(models.Model):
    director = models.ForeignKey(Crew, on_delete=models.CASCADE)
    film = models.ForeignKey(Film, on_delete=models.CASCADE)


# Helper functions

def clean_slug(slug: str) -> str:
    return slug.casefold().replace(' ', '-')

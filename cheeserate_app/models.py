from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

import requests


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
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    trakt_slug = models.CharField(unique=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.item.__str__()

    @classmethod
    def get_or_create_by_slug(cls, slug: str):
        slug = slug.casefold()
        try:
            return cls.objects.get(trakt_slug=slug)
        except cls.DoesNotExist:
            return cls.create(slug)

class Film(TraktCommon):
    title = models.CharField()
    year = models.IntegerField()
    poster_url = models.URLField(null=True)

    def get_absolute_url(self):
        return f"/films/{self.trakt_slug}"

    @classmethod
    def create(cls, slug: str):
        slug = slug.casefold()
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

        return film

class Crew(models.Model):
    trakt_slug = models.CharField(unique=True)
    name = models.CharField()
    headshot_url = models.URLField(null=True)
    birth = models.DateField(null=True)
    death = models.DateField(null=True)
    biography = models.CharField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_absolute_url(self):
        return f"/crew/{self.trakt_slug}"

    @classmethod
    def create(cls, slug: str):
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

class CrewDirectedFilm(models.Model):
    director = models.ForeignKey(Crew, on_delete=models.CASCADE)
    film = models.ForeignKey(Film, on_delete=models.CASCADE)

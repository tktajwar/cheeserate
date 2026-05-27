from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now

from datetime import datetime, timedelta, timezone
import requests


# Item update constants

INITIAL_INTERVAL_HOUR = 6
MAX_INTERVAL_HOUR = 576
INTERVAL_MULTIPLIER = 2

def ancient_time() -> datetime:
    return datetime(1990,1,1,0,0,0, tzinfo=timezone.utc)

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
    last_fetched = models.DateTimeField(default=ancient_time)
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
    title = models.CharField()
    year = models.IntegerField(null=True)
    poster_url = models.URLField(null=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.item.__str__()

    def update_if_appropriate(self) -> bool:
        updated = False
        if now() > self.next_fetch:
            updated = bool(
                self.add_crews() + self.update_info()
            )
            self.last_fetched = now()
            if updated:
                self.next_interval = INITIAL_INTERVAL_HOUR
            else:
                self.next_interval = min (
                    self.next_interval * INTERVAL_MULTIPLIER,
                    MAX_INTERVAL_HOUR,
                )
            self.next_fetch = now() + timedelta(hours=self.next_interval)
            self.save()
        return updated

    @classmethod
    def shallow_create(
            cls,
            trakt_slug: str,
            title: str,
            year: int,
            poster_url: str,
    ):
        item = Item ( title = f"{title} ({year})" )
        item.save()

        item = cls (
            item=item,
            trakt_slug=trakt_slug,
            title=title,
            year=year,
            poster_url=poster_url,
        )
        item.save()

        return item

    @classmethod
    def get_or_shallow_create(
            cls,
            slug: str,
            title: str,
            year: int,
            poster_url: str,
    ):
        slug = clean_slug(slug)
        try:
            return cls.objects.get(trakt_slug=slug)
        except cls.DoesNotExist:
            return cls.shallow_create(slug, title, year, poster_url)

    @staticmethod
    def get_directors(res: dict):
        directing = res.get('crew').get('directing')
        if directing is None:
            return [ ]
        return [
            Crew.get_or_shallow_create(
                director.get('person').get('ids').get('slug'),
                director.get('person').get('name'),
                (director.get('images').get('headshot') or [None])[0],
            ) for director in directing
            if 'Director' in director.get('jobs')
        ]

    @staticmethod
    def get_casts(res: dict):
        return [
            (Crew.get_or_shallow_create(
                cast.get('person').get('ids').get('slug'),
                cast.get('person').get('name'),
                (cast.get('images').get('headshot') or [None])[0],
            ), cast.get('characters')) for cast in res.get('cast')
        ]


class Film(TraktItemCommon):
    def get_absolute_url(self):
        return f"/films/{self.trakt_slug}"

    def update_info(self) -> bool:
        url = f"https://api.trakt.tv/movies/{self.trakt_slug}/"

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

        if parse_datetime(res.get('updated_at')) < self.last_fetched:
            return False

        (title, year) = (
            res.get('title'),
            res.get('year'),
        )

        poster_url = res.get('images').get('poster')
        poster_url = poster_url[0] if len(poster_url) else None

        self.title = title
        self.year = year
        self.poster_url = poster_url
        self.save()

        return True

    def add_crews(self) -> int:
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

        for (cast, cast_as) in self.get_casts(res):
            for character in cast_as:
                (_, new_added) = CrewStarringFilm.objects.get_or_create(
                    cast=cast,
                    film=self,
                    cast_as=character,
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

        film.update_if_appropriate()

        return film

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

    def update_info(self) -> bool:
        url = f"https://api.trakt.tv/people/{self.trakt_slug}/"

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

        if parse_datetime(res.get('updated_at')) < self.last_fetched:
            return False

        (name, birth, death, biography) = (
            res.get('name'),
            res.get('birthday'),
            res.get('death'),
            res.get('biography'),
        )

        headshot_url = res.get('images').get('headshot')
        headshot_url = headshot_url[0] if len(headshot_url) else None

        self.name=name
        self.birth=birth
        self.death=death
        self.biography=biography
        self.headshot_url=headshot_url
        self.save()

        return True

    def add_films(self) -> int:
        url = f"https://api.trakt.tv/people/{self.trakt_slug}/movies"
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

        updated_count = 0

        directing = res.get('crew').get('directing')
        if directing:
            for movie in [
                    movie.get('movie') for movie in directing
            if 'Director' in movie.get('jobs')
            ]:
                film_slug = movie.get('ids').get('slug')
                title = movie.get('title')
                year = movie.get('year')
                poster_url = (movie.get('images').get('poster') or [None])[0]
                film = Film.get_or_shallow_create(
                    film_slug,
                    title,
                    year,
                    poster_url,
                )
                (_, new_added) = CrewDirectedFilm.objects.get_or_create(
                    director=self,
                    film=film,
                )
                updated_count += new_added

        for (movie, characters) in [
                (movie.get('movie'), movie.get('characters'))
                for movie in res.get('cast')
        ]:
            film_slug = movie.get('ids').get('slug')
            title = movie.get('title')
            year = movie.get('year')
            poster_url = (movie.get('images').get('poster') or [None])[0]
            film = Film.get_or_shallow_create(
                film_slug,
                title,
                year,
                poster_url,
            )

            for character in characters:
                (_, new_added) = CrewStarringFilm.objects.get_or_create(
                    cast=self,
                    film=film,
                    cast_as=characters,
                )
                updated_count += new_added

        return updated_count

    def update_if_appropriate(self) -> bool:
        updated = False
        if now() > self.next_fetch:
            updated = bool(
                self.add_films() + self.update_info()
            )
            self.last_fetched = now()
            if updated:
                self.next_interval = INITIAL_INTERVAL_HOUR
            else:
                self.next_interval = min (
                    self.next_interval * INTERVAL_MULTIPLIER,
                    MAX_INTERVAL_HOUR,
                )
            self.next_fetch = now() + timedelta(hours=self.next_interval)
            self.save()
        return updated

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

        crew.update_if_appropriate()

        return crew

    @classmethod
    def shallow_create(cls, trakt_slug: str, name: str, headshot_url: str):
        crew = cls (
            name=name,
            trakt_slug=trakt_slug,
            headshot_url=headshot_url,
        )
        crew.save()

        return crew

    @classmethod
    def get_or_shallow_create(cls, slug: str, name: str, headshot_url: str):
        slug = clean_slug(slug)
        try:
            return cls.objects.get(trakt_slug=slug)
        except cls.DoesNotExist:
            return cls.shallow_create(slug, name, headshot_url)

class CrewDirectedFilm(models.Model):
    director = models.ForeignKey(Crew, on_delete=models.CASCADE)
    film = models.ForeignKey(Film, on_delete=models.CASCADE)

class CrewStarringFilm(models.Model):
    cast = models.ForeignKey(Crew, on_delete=models.CASCADE)
    film = models.ForeignKey(Film, on_delete=models.CASCADE)
    cast_as = models.CharField(null=True)


# Helper functions

def clean_slug(slug: str) -> str:
    return slug.casefold().replace(' ', '-')

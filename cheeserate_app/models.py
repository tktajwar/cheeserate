from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Case, When
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

class ItemCommon(models.Model):
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

    class Meta:
        abstract = True

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

class TraktItemCommon(TraktCommon, ItemCommon):
    title = models.CharField()
    year = models.IntegerField(null=True)
    poster_url = models.URLField(null=True)
    overview = models.CharField(null=True)

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.title} ({self.year})"

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

        item = cls (
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
        directing = res.get('crew').get('directing') or []
        targets = [
            (
                director.get('person').get('ids').get('slug'),
                director.get('person').get('name'),
                (director.get('images').get('headshot') or [None])[0],
            ) for director in directing
            if 'Director' in director.get('jobs')
        ]
        return Crew.bulk_get_or_shallow_create(targets)

    @staticmethod
    def get_casts(res: dict):
        casts = res.get('cast') or []
        targets = [
            (
                cast.get('person').get('ids').get('slug'),
                cast.get('person').get('name'),
                (cast.get('images').get('headshot') or [None])[0],
            ) for cast in casts
        ]
        return Crew.bulk_get_or_shallow_create(targets)

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

        (title, year, overview) = (
            res.get('title'),
            res.get('year'),
            res.get('overview'),
        )

        poster_url = res.get('images').get('poster')
        poster_url = poster_url[0] if len(poster_url) else None

        self.title = title
        self.year = year
        self.overview = overview
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

        targets = [ ]
        for director in self.get_directors(res):
            targets.append(
                (director, self)
            )
        CrewDirectedFilm.bulk_create(targets)

        targets = [ ]
        for cast in self.get_casts(res):
            targets.append(
                (cast, self)
            )
        CrewStarringFilm.bulk_create(targets)

        return False

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

        film = Film (
            trakt_slug=trakt_slug,
            title=title,
            year=year,
            poster_url=poster_url,
        )
        film.save()

        film.update_if_appropriate()

        return film

    @classmethod
    def bulk_get_or_shallow_create(cls, targets: list):
        objs = [ ]
        for (slug, title, year, poster_url) in targets:
            objs.append(
                cls (
                    trakt_slug=slug,
                    title=title,
                    year=year,
                    poster_url=poster_url,
                )
            )
        cls.objects.bulk_create(
            objs,
            ignore_conflicts=True,
        )
        slugs = [ slug for (slug, _, _, _) in targets ]
        return cls.objects.filter(trakt_slug__in=slugs)

class Crew(TraktCommon):
    name = models.CharField()
    headshot_url = models.URLField(null=True)
    birth = models.DateField(null=True)
    death = models.DateField(null=True)
    biography = models.CharField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

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

        directing = res.get('crew').get('directing') or []
        targets = [ ]
        for movie_dir in directing:
            if 'Director' not in movie_dir.get('jobs'):
                continue
            movie = movie_dir.get('movie')
            film_slug = movie.get('ids').get('slug')
            title = movie.get('title')
            year = movie.get('year')
            poster_url = (movie.get('images').get('poster') or [None])[0]
            targets.append(
                (film_slug, title, year, poster_url)
            )
        films = Film.bulk_get_or_shallow_create(targets)
        targets = [ (self, film) for film in films ]
        CrewDirectedFilm.bulk_create(targets)

        targets = [ ]
        for movie_dir in  res.get('cast'):
            movie = movie_dir.get('movie')
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
            targets.append(
                (film_slug, title, year, poster_url)
            )
        films = Film.bulk_get_or_shallow_create(targets)
        targets = [ (self, film) for film in films ]
        CrewStarringFilm.bulk_create(targets)

        return False

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

    @classmethod
    def bulk_get_or_shallow_create(cls, targets: list):
        objs = [ ]
        for (slug, name, headshot_url) in targets:
            objs.append(
                cls(trakt_slug=slug, name=name, headshot_url=headshot_url)
            )
        cls.objects.bulk_create(
            objs,
            ignore_conflicts=True,
        )
        slugs = [ slug for (slug, _, _) in targets ]
        return cls.objects.filter(trakt_slug__in=slugs)

class CrewDirectedFilm(models.Model):
    director = models.ForeignKey(Crew, on_delete=models.CASCADE)
    film = models.ForeignKey(Film, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['director', 'film'],
                name='unique_directing'
            ),
        ]

    @classmethod
    def bulk_create(cls, targets: list):
        objs = [ ]
        for (director, film) in targets:
            objs.append(
                cls (
                    director = director,
                    film = film,
                )
            )
        cls.objects.bulk_create(
            objs,
            ignore_conflicts=True,
        )

class CrewStarringFilm(models.Model):
    cast = models.ForeignKey(Crew, on_delete=models.CASCADE)
    film = models.ForeignKey(Film, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['cast', 'film'],
                name='unique_casting'
            ),
        ]

    @classmethod
    def bulk_create(cls, targets: list):
        objs = [ ]
        for (cast, film) in targets:
            objs.append(
                cls (
                    cast = cast,
                    film = film,
                )
            )
        cls.objects.bulk_create(
            objs,
            ignore_conflicts=True,
        )


# Helper functions

def clean_slug(slug: str) -> str:
    return slug.casefold().replace(' ', '-')

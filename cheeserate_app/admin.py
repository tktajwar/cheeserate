from django.contrib import admin

from .models import Crew, Film, CrewStarringFilm, CrewDirectedFilm
from .models import UserRatingFilm

# Register your models here.

admin.site.register(Crew)
admin.site.register(Film)
admin.site.register(CrewStarringFilm)
admin.site.register(CrewDirectedFilm)
admin.site.register(UserRatingFilm)

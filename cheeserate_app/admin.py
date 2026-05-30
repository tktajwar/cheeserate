from django.contrib import admin

from .models import User, Crew, Film, CrewStarringFilm, CrewDirectedFilm

# Register your models here.

admin.site.register(User)
admin.site.register(Crew)
admin.site.register(Film)
admin.site.register(CrewStarringFilm)
admin.site.register(CrewDirectedFilm)

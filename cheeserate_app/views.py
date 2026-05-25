from django.http import HttpResponse
from django.shortcuts import render
from django.template import loader

from .models import Item, Film

# Create your views here.

def root(request):
    latest_items = [ item for item in Film.objects.order_by("-pk") ]
    context = {"latest_items": latest_items}
    return render(request, "cheeserate/index.html", context)

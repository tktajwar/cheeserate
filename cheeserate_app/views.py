from django.http import HttpResponse
from django.shortcuts import render
from django.template import loader

from .models import Item, Film

# Create your views here.

def root(request):
    latest_items = [ item for item in Film.objects.order_by("-pk") ]
    print(latest_items[0].get_absolute_url())
    template = loader.get_template("cheeserate/index.html")
    context = {"latest_items": latest_items}
    return HttpResponse(template.render(context, request))

from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.

def root(request):
    return HttpResponse("Hello, rat!")

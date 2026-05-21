from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

# Create your models here.

class User(models.Model):
    username = models.CharField(max_length=64, unique=True)

class Item(models.Model):
    title=models.CharField(max_length=256)
    score_avg = models.FloatField(
        validators=[
            MinValueValidator(-1.0),
            MaxValueValidator(+1.0),
        ],
    )
    score_sum = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

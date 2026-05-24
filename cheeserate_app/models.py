from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

# Create your models here.

class User(models.Model):
    username = models.CharField(max_length=64, unique=True)

class Item(models.Model):
    title=models.CharField(max_length=8191,null=True,blank=True)
    description=models.CharField(max_length=1023, null=True, blank=True)
    image_url = models.URLField(null=True, blank=True)
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

class Film(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE)

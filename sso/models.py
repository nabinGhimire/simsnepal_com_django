from django.db import models
from django.contrib.auth.models import User

class HamroUserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='hamro_profile')
    hamro_uuid = models.CharField(max_length=255, unique=True)
    avatar_url = models.URLField(blank=True, null=True)
    mobile_number = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.hamro_uuid}"

from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission

class CustomUser(AbstractUser):
    # Add any custom fields for CustomUser
    # For example, your custom fields might go here

    groups = models.ManyToManyField(
        Group,
        related_name='customuser_set',  # Change the reverse accessor
        blank=True
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='customuser_permissions',  # Change the reverse accessor
        blank=True
    )

class User(AbstractUser):
    email = models.EmailField(unique=True)
    profile_image = models.ImageField(upload_to='profile_images/', null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    
    def __str__(self):
        return self.username
        
    groups = models.ManyToManyField(
        Group,
        related_name='user_set',  # Ensure this reverse relationship is distinct
        blank=True
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='user_permissions',  # Ensure this reverse relationship is distinct
        blank=True
    )
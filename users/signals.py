from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from .models import User
from .utils import send_verification_email  # Adjust import based on the location

@receiver(post_save, sender=User)
def send_verification_email_on_register(sender, instance, created, **kwargs):
    if created:
        send_verification_email(instance)

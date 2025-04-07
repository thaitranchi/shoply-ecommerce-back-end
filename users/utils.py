# users/utils.py
from django.core.mail import send_mail  # Add this import
from django.conf import settings

def send_verification_email(user):
    # Send the verification email
    send_mail(
        'Verify your email address',
        'Click the link below to verify your email address.',
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import get_user_model, authenticate, login
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.contrib.sites.shortcuts import get_current_site
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.urls import reverse
from .serializers import RegisterSerializer, UserProfileSerializer,\
     PasswordResetRequestSerializer, PasswordResetConfirmSerializer
from rest_framework.views import APIView
import re
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib.auth.models import User

User = get_user_model()

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    
    def put(self, request):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')

        if not user.check_password(old_password):
            return Response({"error": "Incorrect old password"}, status=status.HTTP_400_BAD_REQUEST)
        validate_password_strength(new_password)
        user.password = make_password(new_password)
        user.save()
        return Response({"message": "Password changed successfully."}, status=status.HTTP_200_OK)

# Helper function for sending email verification
def send_verification_email(request, user):
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    verification_url = reverse('verify_email', kwargs={'uidb64': uid, 'token': token})

    # Construct full URL
    current_site = get_current_site(request)
    verification_link = f"{settings.FRONTEND_URL}{verification_url}"

    # Send email
    send_mail(
        'Verify Your Email Address',
        f'Please click the following link to verify your email: {verification_link}',
        'noreply@example.com',  # Your email
        [user.email],
    )

# Helper function to validate password strength
def validate_password_strength(password):
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long.")
    if not re.search(r"\d", password):  # Check for digits
        raise ValidationError("Password must contain at least one digit.")
    if not re.search(r"[A-Z]", password):  # Check for uppercase letter
        raise ValidationError("Password must contain at least one uppercase letter.")
    if not re.search(r"\W", password):  # Special characters
        raise ValidationError("Password must contain at least one special character.")

# Register View
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        password = serializer.validated_data.get('password')
        validate_password_strength(password)  # Validate password strength
        user = serializer.save()
        
        # Send verification email after registration
        send_verification_email(self.request, user)

# Login View
@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    username = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(request, username=username, password=password)

    if user is not None and user.is_verified and user.is_active:
        refresh = RefreshToken.for_user(user)
        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "message": "Login successful!"
        }, status=status.HTTP_200_OK)
    elif user is not None and not user.is_verified:
        return Response({"error": "Email not verified."}, status=status.HTTP_400_BAD_REQUEST)
    else:
        return Response({"error": "Invalid credentials."}, status=status.HTTP_400_BAD_REQUEST)

# User Profile View
class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user  # Get the currently logged-in user

# Change Password View
@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
def change_password(request):
    user = request.user
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')

    if not user.check_password(old_password):
        return Response({"error": "Old password is incorrect"}, status=status.HTTP_400_BAD_REQUEST)

    validate_password_strength(new_password)  # Validate new password strength
    user.password = make_password(new_password)
    user.save()
    return Response({"message": "Password changed successfully"}, status=status.HTTP_200_OK)

# Password Reset Flow
def generate_password_reset_token(user):
    token = default_token_generator.make_token(user)  # Generate password reset token
    return token

def send_password_reset_email(user, token):
    if not default_token_generator.check_token(user, token):
        return Response({"error": "Invalid or expired token"}, status=status.HTTP_400_BAD_REQUEST)
    reset_link = f"{settings.FRONTEND_URL}/password-reset-confirm/?token={token}"
    subject = "Đặt lại mật khẩu của bạn"
    message = f"Nhấp vào liên kết sau để đặt lại mật khẩu của bạn: {reset_link}"
    send_mail(subject, message, settings.EMAIL_HOST_USER, [user.email])

class PasswordResetRequestView(APIView):
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "Email không tồn tại trong hệ thống."}, status=status.HTTP_400_BAD_REQUEST)

        token = generate_password_reset_token(user)
        send_password_reset_email(user, token)

        return Response({"message": "Email đặt lại mật khẩu đã được gửi."}, status=status.HTTP_200_OK)

class PasswordResetConfirmView(APIView):
    def post(self, request, token):
        email = request.data.get('email')
        new_password = request.data.get('new_password')

        # Handle missing data first
        if not email or not new_password:
            return Response({"error": "This field may not be blank."}, status=status.HTTP_400_BAD_REQUEST)

        if len(new_password) < 8:
            return Response({"error": "Password is too short or not secure."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            if not default_token_generator.check_token(user, token):
                return Response({"detail": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)

            user.set_password(new_password)
            user.save()

            return Response({"detail": "Password reset successful"}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)

# Email Verification View
class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user and default_token_generator.check_token(user, token):
            user.is_verified = True
            user.is_active = True  # Activate the user
            user.save()
            return Response({"message": "Email verified successfully."}, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Invalid verification link."}, status=status.HTTP_400_BAD_REQUEST)

# Logout View (Invalidates Token)
@api_view(['POST'])
def logout(request):
    try:
        refresh_token = request.data.get("refresh")  # Use .get() to avoid KeyError
        if not refresh_token:
            return Response({"error": "Refresh token is required"}, status=status.HTTP_400_BAD_REQUEST)

        token = RefreshToken(refresh_token)
        token.blacklist()  # Blacklist the refresh token
        return Response({"message": "Successfully logged out"}, status=status.HTTP_205_RESET_CONTENT)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

# users/tests.py
from django.urls import reverse
from rest_framework import status
from django.contrib.auth import get_user_model
from django.core import mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string
from django.contrib.auth.tokens import default_token_generator
from rest_framework.test import APITestCase, APIClient
from .models import User  # Import đúng model
from django.utils.encoding import force_bytes

User = get_user_model()

class UserProfileTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="testpassword"
        )
        self.user.is_verified = True
        self.user.is_active = True
        self.user.save()
        self.client = APIClient()

        # Obtain JWT token for authentication
        response = self.client.post('/api/users/login/', {
            "username": "testuser",
            "password": "testpassword"
        })

        # Ensure login was successful and token exists
        self.assertEqual(response.status_code, status.HTTP_200_OK, f"Response: {response.data}")
        self.access_token = response.data.get('access', None)
        if not self.access_token:
            self.fail(f"Login failed: {response.data}")
        
        # Add token to authorization header for subsequent requests
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

    # ✅ Test viewing profile
    def test_get_user_profile(self):
        response = self.client.get(reverse('user-profile'))  # Correct the URL name if needed
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], "testuser")
        self.assertEqual(response.data['email'], "testuser@example.com")

    # ✅ Test updating profile
    def test_update_user_profile(self):
        response = self.client.put(reverse('user-profile'), {
            "email": "updatedemail@example.com"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], "updatedemail@example.com")

    # ✅ Test unauthorized access
    def test_unauthorized_access(self):
        self.client.credentials()  # Make sure to clear credentials for the unauthorized test
        response = self.client.get(reverse('user-profile'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ✅ Test password change success
    def test_change_password_success(self):
        # Send request to change the password
        response = self.client.put('/api/users/change-password/', {
            'old_password': 'testpassword', 
            'new_password': 'newPassword123!'
        }, follow=True)
        
        # Ensure that the response status code is 200 OK after a successful password change
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], "Password changed successfully.")

        # Logout to invalidate the current session or token
        self.client.logout()

        # Try to log in with the new password
        login_response = self.client.post('/api/users/login/', {
            "username": "testuser",
            "password": "newPassword123!"
        })
        print(login_response.data)
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

    # ✅ Test password change with wrong old password
    def test_change_password_wrong_old_password(self):
        response = self.client.put('/api/users/change-password/', {
            "old_password": "wrongPassword123",
            "new_password": "newPassword123"
        }, follow=True)
        print(response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], "Incorrect old password")

class PasswordResetTests(APITestCase):

    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='testpassword'
        )
        self.user.is_verified = True
        self.user.is_active = True
        self.user.save()
        self.password_reset_url = reverse('password_reset')
        self.password_reset_confirm_url = reverse('password_reset_confirm', kwargs={'token': 'some-token'})

        # Obtain JWT token for authentication
        response = self.client.post('/api/users/login/', {
            "username": "testuser",
            "password": "testpassword"
        })

        # Ensure login was successful and token exists
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.access_token = response.data.get('access', None)
        if not self.access_token:
            self.fail(f"Login failed: {response.data}")
        
        # Add token to authorization header for subsequent requests
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

    def generate_reset_token(self, user):
        # Generate the reset token using Django's default token generator
        token = default_token_generator.make_token(user)
        return token

    # ✅ Test sending password reset request with valid email
    def test_request_password_reset_valid_email(self):
        data = {"email": "testuser@example.com"}
        response = self.client.post(self.password_reset_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Email đặt lại mật khẩu đã được gửi.", str(response.data))

    # ✅ Test sending password reset request with invalid email
    def test_request_password_reset_invalid_email(self):
        data = {"email": "nonexistent@example.com"}
        response = self.client.post(self.password_reset_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Email không tồn tại trong hệ thống.", str(response.data))

    def test_password_reset_confirm_valid_token(self):
        token = self.generate_reset_token(self.user)
        self.password_reset_confirm_url = reverse('password_reset_confirm', kwargs={'token': token})
        data = {
            'email': self.user.email,
            'new_password': 'new_secure_password123'
        }
        response = self.client.post(self.password_reset_confirm_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['detail'], "Password reset successful")

        # Log in with the new password
        login_response = self.client.post('/api/users/login/', {
            "username": "testuser",
            "password": "new_secure_password123"
        })
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

    def test_password_reset_confirm_missing_data(self):
        token = self.generate_reset_token(self.user)
        data = {
            "email": self.user.email,  # Ensure the email is included
            "new_password": ""  # Ensure the password field is empty
        }
        response = self.client.post(self.password_reset_confirm_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("This field may not be blank.", str(response.data))  # Adjust message if needed

    def test_password_reset_confirm_weak_password(self):
        token = self.generate_reset_token(self.user)
        self.password_reset_confirm_url = reverse('password_reset_confirm', kwargs={'token': token})
        data = {
            "email": 'testuser@example.com',
            "new_password": "123"  # Weak password
        }
        response = self.client.post(self.password_reset_confirm_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Password is too short or not secure.", str(response.data))  # Adjust the message as per your validation

class EmailVerificationTests(APITestCase):

    def setUp(self):
        self.email = 'testuser@example.com'
        self.username = 'testuser'
        self.password = 'testpassword123!'
        self.register_url = reverse('register')

        # Tạo user chưa kích hoạt
        self.user = User.objects.create_user(
            username=self.username,
            email=self.email,
            password=self.password,
            is_active=False
        )

    def test_email_verification_send_email(self):
        """
        Test if the email verification email is sent correctly
        """
        # Giả lập việc gửi email
        self.client.post(self.register_url, {
            "username": self.username,
            "email": self.email,
            "password": self.password
        })
        
        # Kiểm tra đã gửi đúng 1 email
        self.assertEqual(len(mail.outbox), 1)
        verification_email = mail.outbox[0]
        self.assertIn(self.email, verification_email.to)
        self.assertIn('Click the link below to verify your email address.', verification_email.body)

    def test_email_verification_successful(self):
        """
        Test successful email verification
        """
        # Tạo token và uid hợp lệ
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        # Tạo URL với thông tin thực
        verify_url = reverse('verify_email', kwargs={'uidb64': uidb64, 'token': token})

        # Gửi yêu cầu GET
        response = self.client.get(verify_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        
        # Kiểm tra người dùng đã kích hoạt
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_email_verification_invalid_token(self):
        """
        Test email verification with an invalid token
        """
        # Tạo token và uid
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        invalid_token = 'invalid_token'

        # URL với token sai
        verify_url = reverse('verify_email', kwargs={'uidb64': uidb64, 'token': invalid_token})
        
        # Gửi yêu cầu GET
        response = self.client.get(verify_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

    def test_email_verification_invalid_user(self):
        """
        Test email verification with a user that doesn't exist
        """
        # uid cho user không tồn tại
        invalid_uidb64 = urlsafe_base64_encode(force_bytes(9999))  # ID giả định
        token = default_token_generator.make_token(self.user)

        # URL với user không tồn tại
        verify_url = reverse('verify_email', kwargs={'uidb64': invalid_uidb64, 'token': token})

        # Gửi yêu cầu GET
        response = self.client.get(verify_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

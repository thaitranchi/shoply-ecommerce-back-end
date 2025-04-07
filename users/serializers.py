from django.contrib.auth import get_user_model
from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User  # ✅ Reference to the correct user model
        fields = ['id', 'username', 'email', 'password']

    def create(self, validated_data):
        password = validated_data['password']
        # Ensure password meets some basic security requirements
        if len(password) < 6:
            raise serializers.ValidationError("Mật khẩu phải có ít nhất 6 ký tự.")
        
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=password
        )
        return user

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'profile_image']
        read_only_fields = ['id', 'username']

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email không tồn tại trong hệ thống.")
        return value

class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        token = data.get('token')
        try:
            # ✅ Validate the token using Django's default token generator
            user = User.objects.get(id=default_token_generator.check_token(data.get('user'), token))
            self.user = user
        except Exception:
            raise serializers.ValidationError("Token không hợp lệ hoặc đã hết hạn.")
        return data

    def save(self):
        self.user.password = make_password(self.validated_data['password'])
        self.user.save()
        return self.user

class ChangePasswordSerializer(serializers.Serializer):
    # password validation can be included here
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_password(self, value):
        if len(value) < 8:  # Example condition for weak password
            raise serializers.ValidationError("Mật khẩu quá ngắn hoặc không an toàn.")
        return value
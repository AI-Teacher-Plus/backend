import logging
from django.contrib.auth import get_user_model
from apps.accounts.models import UserContext
from rest_framework import serializers

logger = logging.getLogger(__name__)


User = get_user_model()


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()


class LoginResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    has_user_context = serializers.BooleanField()


class RefreshResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class UserReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class UserWriteSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password']

    def validate_username(self, value):
        print(f"Validating username: {value}")  # Debug
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def validate_email(self, value):
        print(f"Validating email: {value}")  # Debug
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return value

    def create(self, validated_data):
        print(f"Creating user with validated data: {validated_data}")  # Debug
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
        )
        print(f"User created successfully: {user}")  # Debug
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class UserContextSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserContext
        exclude = ["id", "user"]

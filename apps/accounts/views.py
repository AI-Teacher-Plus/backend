from django.contrib.auth import authenticate, get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema # Import extend_schema

from .serializers import (
    UserContextSerializer,
    UserSerializer,
    LoginSerializer,
    LoginResponseSerializer,
    RefreshResponseSerializer
)

User = get_user_model()


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        operation_id="loginUser",
        request=LoginSerializer,
        responses={200: LoginResponseSerializer, 401: LoginResponseSerializer},
        description="Authenticates a user and sets access and refresh tokens as cookies."
    )
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)
        if not user:
            return Response({'detail': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        refresh = RefreshToken.for_user(user)
        response = Response({'detail': 'Login successful'})
        response.set_cookie('access_token', str(refresh.access_token), httponly=True)
        response.set_cookie('refresh_token', str(refresh), httponly=True)
        return response


class RefreshView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = None

    @extend_schema(
        operation_id="refreshUserToken",
        responses={200: RefreshResponseSerializer, 401: RefreshResponseSerializer},
        description="Refreshes the access token using the refresh token from cookies."
    )
    def post(self, request):
        token = request.COOKIES.get('refresh_token')
        if token is None:
            return Response({'detail': 'No refresh token'}, status=status.HTTP_401_UNAUTHORIZED)
        refresh = RefreshToken(token)
        access = refresh.access_token
        response = Response({'detail': 'Token refreshed'})
        response.set_cookie('access_token', str(access), httponly=True)
        return response


class LogoutView(APIView):
    serializer_class = None
    @extend_schema(
        operation_id="logoutUser",
        responses={200: {'description': 'Logged out successfully'}},
        description="Logs out the user by deleting access and refresh token cookies."
    )
    def post(self, request):
        response = Response({'detail': 'Logged out'}, status=status.HTTP_200_OK)
        response.delete_cookie('access_token')
        response.delete_cookie('refresh_token')
        return response


class UserListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    @extend_schema(
        operation_id="listUsers",
        responses={200: UserSerializer(many=True)},
        description="Retrieves a list of all users."
    )
    def get(self, request):
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    @extend_schema(
        operation_id="createUser",
        request=UserSerializer,
        responses={201: UserSerializer, 400: UserSerializer},
        description="Creates a new user."
    )
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk):
        return User.objects.get(pk=pk)

    @extend_schema(
        operation_id="retrieveUser",
        responses={200: UserSerializer},
        description="Retrieves details of a specific user."
    )
    def get(self, request, pk):
        user = self.get_object(pk)
        serializer = UserSerializer(user)
        return Response(serializer.data)

    @extend_schema(
        operation_id="updateUser",
        request=UserSerializer,
        responses={200: UserSerializer, 400: UserSerializer},
        description="Updates details of a specific user."
    )
    def put(self, request, pk):
        user = self.get_object(pk)
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        operation_id="deleteUser",
        responses={204: {'description': 'User deleted successfully'}},
        description="Deletes a specific user."
    )
    def delete(self, request, pk):
        user = self.get_object(pk)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserContextView(APIView):
    @extend_schema(
        operation_id="updateUserContext",
        request=UserContextSerializer,
        responses={200: UserContextSerializer, 400: UserContextSerializer},
        description="Updates or creates user context information."
    )
    def post(self, request):
        ctx = getattr(request.user, "context", None)
        serializer = UserContextSerializer(instance=ctx, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save(user=request.user)
        return Response(UserContextSerializer(obj).data, status=status.HTTP_200_OK)
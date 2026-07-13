import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

User = get_user_model()

from rest_framework.test import APIClient

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def register_url():
    return reverse('register')

@pytest.fixture
def login_url():
    return reverse('login')

@pytest.fixture
def refresh_url():
    return reverse('token_refresh')

@pytest.mark.django_db
def test_user_registration_success(api_client, register_url):
    data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "Password123!",
        "password_confirm": "Password123!"
    }
    response = api_client.post(register_url, data, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    assert User.objects.filter(username="testuser").exists()

@pytest.mark.django_db
def test_user_registration_password_mismatch(api_client, register_url):
    data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "Password123!",
        "password_confirm": "Password1234!"
    }
    response = api_client.post(register_url, data, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "password_confirm" in response.data

@pytest.mark.django_db
def test_user_registration_weak_password(api_client, register_url):
    # Weak password should trigger Django minimum length or numeric check (from settings.py)
    data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "123",
        "password_confirm": "123"
    }
    response = api_client.post(register_url, data, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "password" in response.data

@pytest.mark.django_db
def test_user_login_success(api_client, login_url):
    User.objects.create_user(username="testuser", password="Password123!")
    data = {
        "username": "testuser",
        "password": "Password123!"
    }
    response = api_client.post(login_url, data, format='json')
    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    assert "refresh" in response.data

@pytest.mark.django_db
def test_user_login_invalid_credentials(api_client, login_url):
    User.objects.create_user(username="testuser", password="Password123!")
    data = {
        "username": "testuser",
        "password": "WrongPassword!"
    }
    response = api_client.post(login_url, data, format='json')
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.django_db
def test_token_refresh_success(api_client, login_url, refresh_url):
    User.objects.create_user(username="testuser", password="Password123!")
    login_response = api_client.post(login_url, {
        "username": "testuser",
        "password": "Password123!"
    }, format='json')
    refresh_token = login_response.data["refresh"]

    response = api_client.post(refresh_url, {"refresh": refresh_token}, format='json')
    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data

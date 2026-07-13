import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

User = get_user_model()

from rest_framework.test import APIClient
from projects.models import Project

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def user1():
    return User.objects.create_user(username="user1", password="Password123!")

@pytest.fixture
def user2():
    return User.objects.create_user(username="user2", password="Password123!")

@pytest.fixture
def auth_client1(user1):
    client = APIClient()
    client.force_authenticate(user=user1)
    return client

@pytest.fixture
def auth_client2(user2):
    client = APIClient()
    client.force_authenticate(user=user2)
    return client

@pytest.fixture
def project1(user1):
    return Project.objects.create(title="Project 1", description="Description 1", owner=user1)

@pytest.mark.django_db
def test_create_project_authenticated(auth_client1, user1):
    url = reverse('project-list')
    data = {"title": "New Project", "description": "New Description"}
    response = auth_client1.post(url, data, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["title"] == "New Project"
    assert response.data["owner"] == user1.username

@pytest.mark.django_db
def test_create_project_unauthenticated(api_client):
    url = reverse('project-list')
    data = {"title": "New Project", "description": "New Description"}
    response = api_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.django_db
def test_list_projects_only_owner(auth_client1, auth_client2, project1):
    url = reverse('project-list')
    
    # User 1 list includes their project
    response1 = auth_client1.get(url)
    assert response1.status_code == status.HTTP_200_OK
    assert len(response1.data) == 1
    assert response1.data[0]["id"] == project1.id
    
    # User 2 list is empty
    response2 = auth_client2.get(url)
    assert response2.status_code == status.HTTP_200_OK
    assert len(response2.data) == 0

@pytest.mark.django_db
def test_retrieve_other_user_project_not_found(auth_client2, project1):
    url = reverse('project-detail', args=[project1.id])
    response = auth_client2.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.django_db
def test_update_other_user_project_not_found(auth_client2, project1):
    url = reverse('project-detail', args=[project1.id])
    data = {"title": "Updated Title"}
    response = auth_client2.put(url, data, format='json')
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.django_db
def test_delete_other_user_project_not_found(auth_client2, project1):
    url = reverse('project-detail', args=[project1.id])
    response = auth_client2.delete(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND

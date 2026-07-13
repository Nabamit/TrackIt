import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient
from projects.models import Project
from tasks.models import Task, TaskLog

User = get_user_model()

@pytest.fixture
def auth_client():
    user = User.objects.create_user(
        username="test_adv", 
        password="Password123!", 
        email="test_adv@example.com",
        timezone="Asia/Kolkata",
        reset_hour=6
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user

@pytest.fixture
def test_project(auth_client):
    _, user = auth_client
    return Project.objects.create(title="Adv Project", owner=user)

# ==============================================================================
# PROFILE ENDPOINT TESTS
# ==============================================================================
@pytest.mark.django_db
def test_profile_retrieve_and_update(auth_client):
    client, user = auth_client
    url = reverse('profile')

    # Test GET profile
    res = client.get(url)
    assert res.status_code == status.HTTP_200_OK
    assert res.data["timezone"] == "Asia/Kolkata"
    assert res.data["reset_hour"] == 6

    # Test PATCH profile
    patch_data = {"timezone": "Europe/London", "reset_hour": 12}
    res = client.patch(url, patch_data, format='json')
    assert res.status_code == status.HTTP_200_OK
    assert res.data["timezone"] == "Europe/London"
    assert res.data["reset_hour"] == 12

    # Verify db update
    user.refresh_from_db()
    assert user.timezone == "Europe/London"
    assert user.reset_hour == 12

# ==============================================================================
# ML COMPONENT TESTS
# ==============================================================================
@pytest.mark.django_db
def test_ml_prediction_blocked_task(auth_client, test_project):
    client, user = auth_client
    
    # Task 1: Blocker (pending)
    task1 = Task.objects.create(
        title="Blocker Task",
        project=test_project,
        owner=user,
        status="pending",
        type="one_off"
    )
    # Task 2: Blocked by Task 1
    task2 = Task.objects.create(
        title="Blocked Task",
        project=test_project,
        owner=user,
        status="pending",
        type="one_off",
        depends_on_task=task1
    )

    url = reverse('task-predict', args=[task2.id])
    res = client.get(url)
    assert res.status_code == status.HTTP_200_OK
    assert res.data["success_probability"] == 0.0
    assert res.data["risk_level"] == "high"
    assert any("Blocked" in insight for insight in res.data["insights"])

@pytest.mark.django_db
def test_ml_prediction_normal_task(auth_client, test_project):
    client, user = auth_client
    task = Task.objects.create(
        title="Normal Task",
        project=test_project,
        owner=user,
        status="pending",
        type="one_off",
        priority="high"
    )

    url = reverse('task-predict', args=[task.id])
    res = client.get(url)
    assert res.status_code == status.HTTP_200_OK
    assert res.data["success_probability"] > 0.0
    assert any("priority" in insight for insight in res.data["insights"])

# ==============================================================================
# AI COPILOT TESTS
# ==============================================================================
@pytest.mark.django_db
def test_ai_copilot_fallback_subtasks(auth_client, test_project):
    client, user = auth_client
    task = Task.objects.create(
        title="Decompose Task",
        project=test_project,
        owner=user,
        status="pending"
    )

    url = reverse('ai-copilot')
    data = {
        "task_id": task.id,
        "prompt": "Please break down this task."
    }
    res = client.post(url, data, format='json')
    assert res.status_code == status.HTTP_200_OK
    assert res.data["is_simulated"] is True
    assert "breakdown" in res.data["response"].lower() or "phase" in res.data["response"].lower()

@pytest.mark.django_db
def test_ai_copilot_fallback_motivational(auth_client, test_project):
    client, user = auth_client
    task = Task.objects.create(
        title="Streak Recovery",
        project=test_project,
        owner=user,
        status="pending",
        type="recurring"
    )

    url = reverse('ai-copilot')
    data = {
        "task_id": task.id,
        "prompt": "I missed my streak, how do I recover?"
    }
    res = client.post(url, data, format='json')
    assert res.status_code == status.HTTP_200_OK
    assert res.data["is_simulated"] is True
    assert "recovery plan" in res.data["response"].lower()

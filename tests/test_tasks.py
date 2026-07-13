import pytest
import pytz
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.core.management import call_command
from django.core import mail
from rest_framework import status
from rest_framework.test import APIClient

from projects.models import Project
from tasks.models import Task, TaskLog

User = get_user_model()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def user1():
    # Setting a custom timezone and reset hour for user1
    return User.objects.create_user(
        username="user1", 
        password="Password123!", 
        email="user1@example.com",
        timezone="America/New_York",
        reset_hour=4
    )

@pytest.fixture
def user2():
    return User.objects.create_user(
        username="user2", 
        password="Password123!", 
        email="user2@example.com"
    )

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

@pytest.fixture
def project2(user2):
    return Project.objects.create(title="Project 2", description="Description 2", owner=user2)

@pytest.fixture
def task1(user1, project1):
    return Task.objects.create(
        title="Task 1",
        description="Description 1",
        project=project1,
        owner=user1,
        status="pending",
        priority="high",
        type="one_off"
    )

@pytest.mark.django_db
def test_create_task_success(auth_client1, project1):
    url = reverse('task-list')
    today = timezone.now()
    data = {
        "title": "New Task",
        "project": project1.id,
        "due_date": str(today + timedelta(days=1)),
        "status": "pending",
        "priority": "high",
        "type": "one_off"
    }
    response = auth_client1.post(url, data, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["title"] == "New Task"
    assert response.data["owner"] == "user1"

@pytest.mark.django_db
def test_create_task_past_due_date_fails(auth_client1, project1):
    url = reverse('task-list')
    yesterday = timezone.now() - timedelta(days=1)
    data = {
        "title": "New Task",
        "project": project1.id,
        "due_date": str(yesterday)
    }
    response = auth_client1.post(url, data, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "due_date" in response.data

@pytest.mark.django_db
def test_create_task_other_user_project_fails(auth_client1, project2):
    url = reverse('task-list')
    data = {
        "title": "New Task",
        "project": project2.id
    }
    response = auth_client1.post(url, data, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "project" in response.data

@pytest.mark.django_db
def test_list_tasks_and_filtering(auth_client1, task1, project1, user1):
    task2 = Task.objects.create(
        title="Task 2",
        project=project1,
        owner=user1,
        status="done",
        priority="low",
        type="one_off"
    )

    url = reverse('task-list')
    response = auth_client1.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 2
    
    response = auth_client1.get(url, {"status": "pending"})
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["id"] == task1.id

    response = auth_client1.get(url, {"priority": "low"})
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["id"] == task2.id

@pytest.mark.django_db
def test_task_check_in_streak_logic(auth_client1, task1, user1):
    task1.type = 'recurring'
    task1.save()

    url = reverse('task-check-in', args=[task1.id])
    
    # Calculate timezone localized date
    user_tz = pytz.timezone(user1.timezone)
    now_local = timezone.now().astimezone(user_tz)
    if now_local.hour >= user1.reset_hour:
        local_day_start = now_local.replace(hour=user1.reset_hour, minute=0, second=0, microsecond=0)
    else:
        local_day_start = (now_local - timedelta(days=1)).replace(hour=user1.reset_hour, minute=0, second=0, microsecond=0)
    
    today = local_day_start.date()
    yesterday = today - timedelta(days=1)
    
    # 1. First check-in starts streak at 1
    response = auth_client1.post(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["current_streak"] == 1
    assert response.data["last_checked_in"] == str(today)
    
    # 2. Check-in on same day should fail
    response = auth_client1.post(url)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "detail" in response.data

    # 3. Simulate consecutive day check-in
    task1.refresh_from_db()
    task1.last_checked_in = yesterday
    task1.save()
    
    response = auth_client1.post(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["current_streak"] == 2
    assert response.data["last_checked_in"] == str(today)

    # 4. Simulate a missed day
    task1.refresh_from_db()
    task1.last_checked_in = today - timedelta(days=3)
    task1.save()

    response = auth_client1.post(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["current_streak"] == 1
    assert response.data["last_checked_in"] == str(today)

@pytest.mark.django_db
def test_other_user_cannot_access_or_modify_task(auth_client2, task1):
    detail_url = reverse('task-detail', args=[task1.id])
    check_in_url = reverse('task-check-in', args=[task1.id])
    
    response = auth_client2.get(detail_url)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    
    response = auth_client2.patch(detail_url, {"title": "Stolen task"})
    assert response.status_code == status.HTTP_404_NOT_FOUND
    
    response = auth_client2.post(check_in_url)
    assert response.status_code == status.HTTP_404_NOT_FOUND

# ==============================================================================
# ADVANCED FEATURES TESTS
# ==============================================================================

@pytest.mark.django_db
def test_task_prerequisite_blocking(auth_client1, project1, task1):
    task2 = Task.objects.create(
        title="Task 2",
        project=project1,
        owner=task1.owner,
        depends_on_task=task1,
        status="pending"
    )
    url = reverse('task-detail', args=[task2.id])
    
    # Try to set Task 2 to IN_PROGRESS while Task 1 is PENDING
    response = auth_client1.patch(url, {"status": "in_progress"}, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert f"This task is blocked by {task1.title}" in response.data["status"][0]

    # Mark Task 1 as DONE
    task1.status = "done"
    task1.save()

    # Try setting Task 2 to IN_PROGRESS again
    response = auth_client1.patch(url, {"status": "in_progress"}, format='json')
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "in_progress"

@pytest.mark.django_db
def test_circular_dependency_blocks(auth_client1, project1, task1):
    task2 = Task.objects.create(
        title="Task 2",
        project=project1,
        owner=task1.owner,
        depends_on_task=task1,
        status="pending"
    )
    url = reverse('task-detail', args=[task1.id])
    
    # Try making Task 1 depend on Task 2 (which depends on Task 1)
    response = auth_client1.patch(url, {"depends_on_task": task2.id}, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Circular dependency detected" in response.data["depends_on_task"][0]

@pytest.mark.django_db
def test_task_freeze_endpoint(auth_client1, task1, user1):
    task1.type = 'recurring'
    task1.save()

    # User starts with 0 grace tokens
    url = reverse('task-freeze', args=[task1.id])
    response = auth_client1.post(url)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "No grace tokens available" in response.data["detail"]

    # Give user 1 token
    user1.grace_tokens_balance = 1
    user1.save()

    response = auth_client1.post(url)
    assert response.status_code == status.HTTP_200_OK
    
    user1.refresh_from_db()
    assert user1.grace_tokens_balance == 0
    assert TaskLog.objects.filter(task=task1, is_frozen_day=True).exists()

@pytest.mark.django_db
def test_check_in_milestone_token_reward(auth_client1, task1, user1):
    task1.type = 'recurring'
    task1.current_streak = 14
    
    # Calculate localized yesterday
    user_tz = pytz.timezone(user1.timezone)
    now_local = timezone.now().astimezone(user_tz)
    if now_local.hour >= user1.reset_hour:
        local_day_start = now_local.replace(hour=user1.reset_hour, minute=0, second=0, microsecond=0)
    else:
        local_day_start = (now_local - timedelta(days=1)).replace(hour=user1.reset_hour, minute=0, second=0, microsecond=0)
    yesterday = (local_day_start - timedelta(days=1)).date()
    
    task1.last_checked_in = yesterday
    task1.save()

    assert user1.grace_tokens_balance == 0

    url = reverse('task-check-in', args=[task1.id])
    response = auth_client1.post(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["current_streak"] == 15
    
    user1.refresh_from_db()
    assert user1.grace_tokens_balance == 1

@pytest.mark.django_db
def test_reset_streaks_command_with_grace_token(user1, project1):
    # Setup missed habit with 1 grace token
    task = Task.objects.create(
        title="Habit Task",
        project=project1,
        owner=user1,
        type="recurring",
        current_streak=10,
        last_checked_in=timezone.now().date() - timedelta(days=3)
    )
    user1.grace_tokens_balance = 1
    user1.save()

    # Execute reset command
    call_command('reset_streaks')

    task.refresh_from_db()
    user1.refresh_from_db()
    # Rescued: streak remains 10, tokens balance deducted to 0
    assert task.current_streak == 10
    assert user1.grace_tokens_balance == 0
    assert TaskLog.objects.filter(task=task, is_frozen_day=True).exists()

@pytest.mark.django_db
def test_reset_streaks_command_fails_no_tokens(user1, project1):
    task = Task.objects.create(
        title="Habit Task",
        project=project1,
        owner=user1,
        type="recurring",
        current_streak=10,
        last_checked_in=timezone.now().date() - timedelta(days=3)
    )
    user1.grace_tokens_balance = 0
    user1.save()

    call_command('reset_streaks')

    task.refresh_from_db()
    # Reset: streak goes to 0
    assert task.current_streak == 0
    assert TaskLog.objects.filter(task=task, status_snapshot='failed').exists()

@pytest.mark.django_db
def test_send_deadline_reminders_command(user1, project1):
    # Setup a high-priority pending task due in 2 hours
    task = Task.objects.create(
        title="Urgent Project Work",
        project=project1,
        owner=user1,
        type="one_off",
        status="pending",
        priority="high",
        due_date=timezone.now() + timedelta(hours=2)
    )

    assert len(mail.outbox) == 0

    call_command('send_deadline_reminders')

    task.refresh_from_db()
    assert task.reminder_sent is True
    assert len(mail.outbox) == 1
    assert "Urgent Reminder" in mail.outbox[0].subject

@pytest.mark.django_db
def test_analytics_dashboard_view(auth_client1, project1, user1):
    # 1. Setup completed one-off task (to verify velocity calculation)
    task_one_off = Task.objects.create(
        title="One off",
        project=project1,
        owner=user1,
        type="one_off",
        status="pending"
    )
    # Simulate logs (created now, completed 2 hours later)
    task_one_off.created_at = timezone.now() - timedelta(hours=5)
    task_one_off.status = "done"
    task_one_off.save()
    
    # Overwrite the automatically generated 'done' log's timestamp to represent a 2-hour completion duration
    done_log = TaskLog.objects.filter(task=task_one_off, status_snapshot='done').first()
    done_log.timestamp = task_one_off.created_at + timedelta(hours=2)
    done_log.save()

    # 2. Setup failed logs on a specific day (e.g. Wednesday) to verify volatility
    # We will log a failure snapshot on a Wednesday
    wednesday_time = timezone.now()
    while wednesday_time.strftime('%A') != 'Wednesday':
        wednesday_time -= timedelta(days=1)
    
    TaskLog.objects.create(
        task=task_one_off,
        status_snapshot='failed',
        timestamp=wednesday_time
    )

    # 3. Setup consistency check-in days
    # Log 3 check-ins within the last 30 days
    for i in range(3):
        TaskLog.objects.create(
            task=task_one_off,
            status_snapshot='checked_in',
            timestamp=timezone.now() - timedelta(days=i)
        )

    url = reverse('analytics-dashboard')
    response = auth_client1.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["completion_velocity_hours"] == 2.0
    assert response.data["failure_volatility"]["danger_day"] == "Wednesday"
    # 3 distinct check-in days in rolling 30 days / 30 days = 10%
    assert response.data["consistency_score"] == 10.0

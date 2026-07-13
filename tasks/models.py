from django.db import models
from django.conf import settings
from django.utils import timezone
from projects.models import Project

class Task(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]

    TYPE_CHOICES = [
        ('one_off', 'One-off Task'),
        ('recurring', 'Recurring Habit'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    due_date = models.DateTimeField(null=True, blank=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tasks')
    last_checked_in = models.DateField(null=True, blank=True)
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='one_off')
    depends_on_task = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='blocked_tasks'
    )
    reminder_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_status = None
        if not is_new:
            try:
                old_status = Task.objects.get(pk=self.pk).status
            except Task.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        # Log status snapshot changes
        if is_new or old_status != self.status:
            TaskLog.objects.create(
                task=self,
                status_snapshot=self.status,
                is_frozen_day=False
            )

    class Meta:
        ordering = ['-created_at']


class TaskLog(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='logs')
    status_snapshot = models.CharField(max_length=50)
    is_frozen_day = models.BooleanField(default=False)
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.task.title} - {self.status_snapshot} ({self.timestamp})"

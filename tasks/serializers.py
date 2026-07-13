from django.utils import timezone
from rest_framework import serializers
from .models import Task
from projects.models import Project

class TaskSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')

    class Meta:
        model = Task
        fields = (
            'id', 'title', 'description', 'status', 'priority', 'due_date',
            'project', 'owner', 'last_checked_in', 'current_streak', 
            'longest_streak', 'type', 'depends_on_task', 'reminder_sent', 'created_at'
        )
        read_only_fields = ('id', 'last_checked_in', 'current_streak', 'longest_streak', 'reminder_sent', 'created_at')

    def validate_due_date(self, value):
        # due_date cannot be in the past on creation
        if not self.instance and value and value < timezone.now():
            raise serializers.ValidationError("Due date cannot be in the past on creation.")
        return value

    def validate_project(self, value):
        # A user cannot assign a task to a project they do not own
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if value.owner != request.user:
                raise serializers.ValidationError("You cannot assign tasks to projects owned by other users.")
        return value

    def validate_depends_on_task(self, value):
        # A user cannot depend on a task owned by a different user
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if value and value.owner != request.user:
                raise serializers.ValidationError("Prerequisite task must be owned by you.")
        
        # Circular dependency check
        if self.instance and value:
            def check_circular(task_id, depends_on_id):
                if task_id == depends_on_id:
                    return True
                try:
                    dep_task = Task.objects.get(id=depends_on_id)
                    if dep_task.depends_on_task_id:
                        return check_circular(task_id, dep_task.depends_on_task_id)
                except Task.DoesNotExist:
                    pass
                return False

            if check_circular(self.instance.id, value.id):
                raise serializers.ValidationError("Circular dependency detected: a task cannot depend on itself directly or indirectly.")
        
        return value

    def validate(self, attrs):
        # Retrieve target status and depends_on_task values
        # Defaulting to self.instance values if not present in patch request
        status_val = attrs.get('status')
        depends_on = attrs.get('depends_on_task')

        if self.instance:
            if status_val is None:
                status_val = self.instance.status
            if depends_on is None:
                depends_on = self.instance.depends_on_task
        else:
            if status_val is None:
                status_val = 'pending'

        if status_val in ['in_progress', 'done'] and depends_on:
            if depends_on.status != 'done':
                raise serializers.ValidationError({
                    "status": f"This task is blocked by {depends_on.title}"
                })

        return attrs

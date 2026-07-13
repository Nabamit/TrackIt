import pytz
from datetime import timedelta
from django.utils import timezone
from django.db.models import Avg
from rest_framework import viewsets, permissions, status, generics, views
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from collections import Counter

from .models import Task, TaskLog
from .serializers import TaskSerializer
from .permissions import IsOwner
from .utils import dispatch_webhook_async

class TaskViewSet(viewsets.ModelViewSet):
    """
    ViewSet for viewing and editing tasks.
    Supports filtering by status and priority, task freezing, and daily checking in.
    """
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'priority']

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Task.objects.filter(owner=self.request.user)
        return Task.objects.none()

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'], url_path='check-in')
    def check_in(self, request, pk=None):
        task = self.get_object()
        if task.type != 'recurring':
            return Response(
                {"detail": "Only recurring habits can be checked in."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user
        user_tz = pytz.timezone(user.timezone)
        now_local = timezone.now().astimezone(user_tz)

        # Calculate current local day start based on reset_hour
        if now_local.hour >= user.reset_hour:
            local_day_start = now_local.replace(hour=user.reset_hour, minute=0, second=0, microsecond=0)
        else:
            local_day_start = (now_local - timedelta(days=1)).replace(hour=user.reset_hour, minute=0, second=0, microsecond=0)

        today_date = local_day_start.date()
        yesterday_date = today_date - timedelta(days=1)

        if task.last_checked_in == today_date:
            return Response(
                {"detail": "Already checked in today."},
                status=status.HTTP_400_BAD_REQUEST
            )
        elif task.last_checked_in == yesterday_date:
            task.current_streak += 1
        else:
            task.current_streak = 1

        # Track longest streak
        if task.current_streak > task.longest_streak:
            task.longest_streak = task.current_streak

        # Grace Day / Token milestones reward (every 15 days)
        if task.current_streak % 15 == 0:
            if user.grace_tokens_balance < 3:
                user.grace_tokens_balance += 1
                user.save()

        task.last_checked_in = today_date
        task.save()

        # Log check-in
        TaskLog.objects.create(
            task=task,
            status_snapshot='checked_in',
            is_frozen_day=False,
            timestamp=timezone.now()
        )

        # Dispatch webhook for milestone events asynchronously
        dispatch_webhook_async(task.id, task.title, task.current_streak)

        serializer = self.get_serializer(task)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='freeze')
    def freeze(self, request, pk=None):
        task = self.get_object()
        if task.type != 'recurring':
            return Response(
                {"detail": "Only recurring habits can be frozen."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user
        user_tz = pytz.timezone(user.timezone)
        now_local = timezone.now().astimezone(user_tz)

        if now_local.hour >= user.reset_hour:
            local_day_start = now_local.replace(hour=user.reset_hour, minute=0, second=0, microsecond=0)
        else:
            local_day_start = (now_local - timedelta(days=1)).replace(hour=user.reset_hour, minute=0, second=0, microsecond=0)

        today_date = local_day_start.date()
        local_day_end = local_day_start + timedelta(days=1)

        # Check if already checked in today
        if task.last_checked_in == today_date:
            return Response(
                {"detail": "Cannot freeze a task that has already been checked in today."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if already frozen today
        if TaskLog.objects.filter(task=task, is_frozen_day=True, timestamp__gte=local_day_start, timestamp__lt=local_day_end).exists():
            return Response(
                {"detail": "Already frozen today."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check token balance
        if user.grace_tokens_balance <= 0:
            return Response(
                {"detail": "No grace tokens available."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Deduct token
        user.grace_tokens_balance -= 1
        user.save()

        # Log frozen day
        TaskLog.objects.create(
            task=task,
            status_snapshot='frozen',
            is_frozen_day=True,
            timestamp=timezone.now()
        )

        # Mark checked in for today to preserve the streak chain
        task.last_checked_in = today_date
        task.save()

        serializer = self.get_serializer(task)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='predict')
    def predict(self, request, pk=None):
        task = self.get_object()
        from .ml import TaskCompletionPredictor
        predictor = TaskCompletionPredictor()
        prediction = predictor.predict(task)
        return Response(prediction, status=status.HTTP_200_OK)


from drf_spectacular.utils import extend_schema
from rest_framework import serializers

class FailureVolatilitySerializer(serializers.Serializer):
    danger_day = serializers.CharField(allow_null=True)
    percentage = serializers.FloatField()
    message = serializers.CharField()

class AnalyticsDashboardResponseSerializer(serializers.Serializer):
    completion_velocity_hours = serializers.FloatField()
    failure_volatility = FailureVolatilitySerializer()
    consistency_score = serializers.FloatField()


class AnalyticsDashboardView(views.APIView):
    """
    APIView for fetching personal productivity metrics.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        responses={200: AnalyticsDashboardResponseSerializer},
        description="Retrieve personal productivity analytics."
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        
        # 1. Completion Velocity (One-off tasks PENDING -> DONE average hours)
        done_tasks = Task.objects.filter(owner=user, type='one_off', status='done')
        durations = []
        for t in done_tasks:
            done_log = t.logs.filter(status_snapshot='done').order_by('timestamp').first()
            if done_log:
                duration = (done_log.timestamp - t.created_at).total_seconds()
                durations.append(duration)
        
        completion_velocity_hours = 0.0
        if durations:
            completion_velocity_hours = round((sum(durations) / len(durations)) / 3600, 2)

        # 2. Failure Volatility (Danger Days)
        failed_logs = TaskLog.objects.filter(task__owner=user, status_snapshot='failed')
        days = [log.timestamp.strftime('%A') for log in failed_logs]
        failure_volatility_message = "No streak failures recorded yet."
        most_common_day = None
        percentage = 0.0
        
        if days:
            counts = Counter(days)
            most_common_day, count = counts.most_common(1)[0]
            total_failures = len(days)
            percentage = round((count / total_failures) * 100, 2)
            failure_volatility_message = f"Your habit failure rate increases on {most_common_day}s ({percentage}% of all failures occur on this day)"

        # 3. Consistency Score (Rolling 30-day percentage)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        active_logs = TaskLog.objects.filter(
            task__owner=user,
            timestamp__gte=thirty_days_ago,
            status_snapshot__in=['checked_in', 'frozen']
        )
        
        user_tz = pytz.timezone(user.timezone)
        unique_dates = set()
        for log in active_logs:
            local_time = log.timestamp.astimezone(user_tz)
            if local_time.hour < user.reset_hour:
                unique_dates.add((local_time - timedelta(days=1)).date())
            else:
                unique_dates.add(local_time.date())
        
        consistency_score = round((len(unique_dates) / 30) * 100, 2)

        payload = {
            "completion_velocity_hours": completion_velocity_hours,
            "failure_volatility": {
                "danger_day": most_common_day,
                "percentage": percentage,
                "message": failure_volatility_message
            },
            "consistency_score": consistency_score
        }

        return Response(payload, status=status.HTTP_200_OK)


class AICopilotView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        task_id = request.data.get('task_id')
        user_prompt = request.data.get('prompt', '')

        task = None
        if task_id:
            try:
                task = Task.objects.get(id=task_id, owner=request.user)
            except Task.DoesNotExist:
                return Response({"detail": "Task not found or access denied."}, status=status.HTTP_404_NOT_FOUND)

        import os
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        
        # Build prompt context
        context_parts = []
        if task:
            context_parts.append(
                f"You are the TrackIt Productivity Assistant. The user is asking about the following task:\n"
                f"- Title: {task.title}\n"
                f"- Description: {task.description or 'No description'}\n"
                f"- Status: {task.status}\n"
                f"- Priority: {task.priority}\n"
                f"- Type: {task.type}\n"
                f"- Current Streak: {task.current_streak} days\n"
                f"- Longest Streak: {task.longest_streak} days"
            )
            if task.depends_on_task:
                context_parts.append(f"- Blocked by (depends on task): {task.depends_on_task.title} (Status: {task.depends_on_task.status})")
        else:
            context_parts.append(
                "You are the TrackIt Productivity Assistant helping the user manage their tasks, projects, and habit streaks."
            )
        
        context_parts.append(f"User request: {user_prompt}")
        full_prompt = "\n\n".join(context_parts)

        # Call Gemini if API key is provided
        if gemini_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_api_key)
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content(full_prompt)
                ai_response = response.text
                is_simulated = False
            except Exception as e:
                # Fallback to simulated response on API error
                ai_response = self._get_simulated_response(task, user_prompt, error_msg=str(e))
                is_simulated = True
        else:
            # Fallback to simulated response when API key is missing
            ai_response = self._get_simulated_response(task, user_prompt)
            is_simulated = True

        return Response({
            "response": ai_response,
            "is_simulated": is_simulated
        }, status=status.HTTP_200_OK)

    def _get_simulated_response(self, task, prompt, error_msg=None):
        prompt_lower = prompt.lower()
        
        if 'breakdown' in prompt_lower or 'break down' in prompt_lower or 'subtask' in prompt_lower or 'decompose' in prompt_lower or 'steps' in prompt_lower:
            title = task.title if task else "your task"
            return (
                f"Here is a suggested breakdown for '{title}':\n\n"
                f"1. **Phase 1: Research & Setup** (30 mins)\n"
                f"   - Gather necessary materials and outline initial objectives.\n"
                f"   - Identify potential obstacles and blocker tasks.\n\n"
                f"2. **Phase 2: Execution & Core Work** (1-2 hours)\n"
                f"   - Complete the primary deliverables of the task in focus chunks.\n"
                f"   - Self-review the output against requirements.\n\n"
                f"3. **Phase 3: Final Polish & Mark Done** (15 mins)\n"
                f"   - Address final styling, formatting, or checks.\n"
                f"   - Mark the task status as 'Done' in the TrackIt dashboard."
            )
            
        elif 'streak' in prompt_lower or 'fail' in prompt_lower or 'miss' in prompt_lower or 'recover' in prompt_lower:
            title = task.title if task else "your habit"
            return (
                f"I noticed you are asking about streak recovery for '{title}'. Here is your Habit Recovery Plan:\n\n"
                f"1. **Analyze the Root Cause:** Pinpoint why the habit was missed (e.g. fatigue, bad timing, or blocker tasks).\n"
                f"2. **Lower the Barrier:** Aim for a 'micro-completion' tomorrow. If it's reading 30 pages, read just 1 page.\n"
                f"3. **Schedule Protection:** Set a primary calendar block and set a custom 'Reset Hour' in your settings to give yourself more grace time.\n"
                f"4. **Leverage Grace Tokens:** Earn a new Grace Token by checking in consecutively for 15 days, which will auto-freeze and protect your streak next time!"
            )
            
        else:
            feedback = f" (Note: API request fell back to simulation due to: {error_msg})" if error_msg else ""
            title = task.title if task else "productivity"
            return (
                f"Hello! I am your TrackIt AI Copilot. Here is some productivity advice for '{title}':\n\n"
                f"- **Prioritize Blocks:** Focus on high priority items first. Blockers should be cleared as early as possible in your workday.\n"
                f"- **Keep Momentum:** Don't let a single miss break your spirit. Consistency is a rolling average, not a perfect streak.\n"
                f"- **Decompose Work:** If you feel overwhelmed, ask me to 'break down this task into subtasks'!\n"
                f"{feedback}"
            )

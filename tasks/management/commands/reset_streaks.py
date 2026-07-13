import pytz
from datetime import timedelta
from django.utils import timezone
from django.core.management.base import BaseCommand
from tasks.models import Task, TaskLog

class Command(BaseCommand):
    help = "Evaluate recurring tasks to reset streaks or consume grace days"

    def handle(self, *args, **options):
        now = timezone.now()
        recurring_tasks = Task.objects.filter(type='recurring')
        
        for task in recurring_tasks:
            user = task.owner
            tz = pytz.timezone(user.timezone)
            now_local = now.astimezone(tz)

            # Determine start of the user's current day
            if now_local.hour >= user.reset_hour:
                local_day_start = now_local.replace(hour=user.reset_hour, minute=0, second=0, microsecond=0)
            else:
                local_day_start = (now_local - timedelta(days=1)).replace(hour=user.reset_hour, minute=0, second=0, microsecond=0)

            # Yesterday window
            yesterday_start = local_day_start - timedelta(days=1)
            yesterday_end = local_day_start
            today_end = local_day_start + timedelta(days=1)

            # Check if user had a completion log (check-in or freeze) during yesterday's window
            has_yesterday_completion = TaskLog.objects.filter(
                task=task,
                status_snapshot__in=['checked_in', 'frozen'],
                timestamp__gte=yesterday_start,
                timestamp__lt=yesterday_end
            ).exists()

            if not has_yesterday_completion:
                # Check if we already processed a reset or freeze during today's window
                already_processed_today = TaskLog.objects.filter(
                    task=task,
                    status_snapshot__in=['failed', 'frozen'],
                    timestamp__gte=local_day_start,
                    timestamp__lt=today_end
                ).exists()

                if not already_processed_today:
                    # Attempt to rescue with a grace token
                    if user.grace_tokens_balance > 0:
                        # Deduct token
                        user.grace_tokens_balance -= 1
                        user.save()

                        # Write a retroactive freeze log inside yesterday's window (e.g. 1 second before end)
                        TaskLog.objects.create(
                            task=task,
                            status_snapshot='frozen',
                            is_frozen_day=True,
                            timestamp=yesterday_end - timedelta(seconds=1)
                        )

                        # Set task's last checked in date to yesterday's date
                        yesterday_date = (local_day_start - timedelta(days=1)).date()
                        task.last_checked_in = yesterday_date
                        task.save()

                        self.stdout.write(self.style.SUCCESS(
                            f"Rescued streak for task '{task.title}' using a grace token. "
                            f"User '{user.username}' remaining tokens: {user.grace_tokens_balance}."
                        ))
                    else:
                        # No tokens, streak breaks
                        task.current_streak = 0
                        task.save()

                        # Log failure at the current time
                        TaskLog.objects.create(
                            task=task,
                            status_snapshot='failed',
                            is_frozen_day=False,
                            timestamp=now
                        )

                        self.stdout.write(self.style.WARNING(
                            f"Reset streak to 0 for task '{task.title}' (User '{user.username}')."
                        ))

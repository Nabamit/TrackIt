from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from tasks.models import Task

class Command(BaseCommand):
    help = "Send email reminders for high priority tasks within 3 hours of their due date"

    def handle(self, *args, **options):
        now = timezone.now()
        three_hours_from_now = now + timedelta(hours=3)
        
        # Query high priority pending one-off tasks with due dates in the next 3 hours
        tasks = Task.objects.filter(
            type='one_off',
            status='pending',
            priority='high',
            due_date__gte=now,
            due_date__lte=three_hours_from_now,
            reminder_sent=False
        )
        
        for task in tasks:
            # Dispatch email via Django's email utility
            send_mail(
                subject=f"Urgent Reminder: Task '{task.title}' is due in less than 3 hours",
                message=(
                    f"Hi {task.owner.username},\n\n"
                    f"This is a reminder that your high-priority task '{task.title}' "
                    f"is due soon on {task.due_date}.\n\n"
                    f"Don't forget to mark it as in progress or done!\n\n"
                    f"Best,\nTrackIt Team"
                ),
                from_email="reminders@trackit.com",
                recipient_list=[task.owner.email],
                fail_silently=False,
            )
            
            task.reminder_sent = True
            task.save()
            
            self.stdout.write(self.style.SUCCESS(
                f"Dispatched deadline reminder email for task '{task.title}' to '{task.owner.email}'."
            ))

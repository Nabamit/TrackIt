from celery import shared_task
from django.core.management import call_command
from django.core.mail import send_mail

@shared_task
def reset_streaks_task():
    """
    Asynchronous task to evaluate recurring habit tasks and reset streaks or consume grace days.
    """
    call_command('reset_streaks')

@shared_task
def send_deadline_reminders_task():
    """
    Asynchronous task to send deadline reminders for tasks due within 3 hours.
    """
    call_command('send_deadline_reminders')

@shared_task
def send_email_async(subject, message, recipient_list, from_email=None):
    """
    Asynchronous helper task to send emails via Django's mail system.
    """
    send_mail(
        subject=subject,
        message=message,
        from_email=from_email,
        recipient_list=recipient_list,
        fail_silently=False,
    )

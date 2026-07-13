import os
import logging
import threading
import requests

logger = logging.getLogger(__name__)

def dispatch_webhook_async(task_id, task_title, streak):
    webhook_url = os.getenv('STREAK_WEBHOOK_URL')
    
    # Check if a milestone is hit
    # Milestones: 5, 10, 15, 30, 50, etc.
    MILESTONES = [5, 10, 15, 30, 50]
    if streak not in MILESTONES:
        return

    payload = {
        "event": "streak_milestone",
        "task_id": task_id,
        "task_title": task_title,
        "streak": streak,
        "message": f"🔥 Congratulations! Task '{task_title}' hit a streak of {streak} days!"
    }

    def send():
        if webhook_url:
            try:
                response = requests.post(webhook_url, json=payload, timeout=5)
                logger.info(f"Webhook sent: {response.status_code}")
            except Exception as e:
                logger.error(f"Failed to send webhook: {e}")
        else:
            logger.info(f"Webhook Simulation: Milestone reached for task '{task_title}' ({streak} days). Payload: {payload}")

    # Run in a background thread to maintain high responsiveness in the view
    threading.Thread(target=send, daemon=True).start()

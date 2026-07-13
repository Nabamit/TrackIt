import math
from django.utils import timezone
from datetime import timedelta
from collections import Counter
from tasks.models import Task, TaskLog

class TaskCompletionPredictor:
    def __init__(self):
        # Default heuristic weights (trained on simulated productivity data)
        self.w_priority = 1.0       # High priority increases motivation
        self.w_consistency = 2.5    # High consistency strongly predicts future success
        self.w_streak = 1.2         # Longer streaks encourage check-ins
        self.w_danger = -1.5        # Danger days (weekday failure) reduces success
        self.bias = -0.5

    def _sigmoid(self, z):
        try:
            return 1.0 / (1.0 + math.exp(-z))
        except OverflowError:
            return 0.0 if z < 0 else 1.0

    def get_user_danger_day(self, user):
        """
        Identify the weekday (e.g., 'Friday') with the highest failures.
        """
        failed_logs = TaskLog.objects.filter(task__owner=user, status_snapshot='failed')
        days = [log.timestamp.strftime('%A') for log in failed_logs]
        if not days:
            return None
        counts = Counter(days)
        return counts.most_common(1)[0][0]

    def get_user_consistency(self, user):
        """
        Compute the user's 30-day consistency score (0.0 to 1.0).
        """
        thirty_days_ago = timezone.now() - timedelta(days=30)
        active_logs = TaskLog.objects.filter(
            task__owner=user,
            timestamp__gte=thirty_days_ago,
            status_snapshot__in=['checked_in', 'frozen']
        )
        unique_dates = {log.timestamp.date() for log in active_logs}
        return min(len(unique_dates) / 30.0, 1.0)

    def train_model(self, user):
        """
        Dynamically train the logistic regression weights using the user's task history.
        Uses gradient descent on historical TaskLog snapshots.
        """
        logs = TaskLog.objects.filter(task__owner=user).select_related('task')
        dataset = []
        
        # Build a training dataset from historical log entries
        for log in logs:
            if log.status_snapshot not in ['checked_in', 'done', 'failed']:
                continue
            
            task = log.task
            priority_val = 1.0 if task.priority == 'high' else (0.6 if task.priority == 'medium' else 0.3)
            
            # Label: 1 for success, 0 for failure
            label = 1 if log.status_snapshot in ['checked_in', 'done'] else 0
            
            # Danger day check at log timestamp
            log_day = log.timestamp.strftime('%A')
            danger_day = self.get_user_danger_day(user)
            is_danger_day = 1.0 if danger_day and log_day == danger_day else 0.0
            
            # Streak factor at that time (approximate)
            streak_val = min(task.current_streak, 30) / 30.0
            
            # User consistency score at that time (approximate)
            consistency_val = self.get_user_consistency(user)
            
            dataset.append({
                'x': [priority_val, consistency_val, streak_val, is_danger_day],
                'y': label
            })

        # Train if we have enough historical data points
        if len(dataset) >= 5:
            epochs = 50
            lr = 0.1
            for _ in range(epochs):
                dw_priority = 0.0
                dw_consistency = 0.0
                dw_streak = 0.0
                dw_danger = 0.0
                dbias = 0.0
                
                for item in dataset:
                    x = item['x']
                    y = item['y']
                    z = (self.w_priority * x[0] + 
                         self.w_consistency * x[1] + 
                         self.w_streak * x[2] + 
                         self.w_danger * x[3] + 
                         self.bias)
                    pred = self._sigmoid(z)
                    error = pred - y
                    
                    dw_priority += error * x[0]
                    dw_consistency += error * x[1]
                    dw_streak += error * x[2]
                    dw_danger += error * x[3]
                    dbias += error
                
                n = len(dataset)
                self.w_priority -= lr * (dw_priority / n)
                self.w_consistency -= lr * (dw_consistency / n)
                self.w_streak -= lr * (dw_streak / n)
                self.w_danger -= lr * (dw_danger / n)
                self.bias -= lr * (dbias / n)

    def predict(self, task):
        """
        Predict the probability of completing the task successfully.
        Returns:
            dict containing:
            - success_probability: float (0.0 to 100.0)
            - risk_level: str ('low', 'medium', 'high')
            - insights: list of str explaining factors
        """
        # If task is already completed
        if task.status == 'done':
            return {
                'success_probability': 100.0,
                'risk_level': 'low',
                'insights': ['This task is already completed. Good job!']
            }

        # If blocked by another task
        if task.depends_on_task and task.depends_on_task.status != 'done':
            return {
                'success_probability': 0.0,
                'risk_level': 'high',
                'insights': [f"Blocked: You must first complete prerequisite task '{task.depends_on_task.title}'."]
            }

        user = task.owner
        
        # Train model dynamically using historical user logs
        self.train_model(user)

        # Feature extraction
        priority_val = 1.0 if task.priority == 'high' else (0.6 if task.priority == 'medium' else 0.3)
        consistency_val = self.get_user_consistency(user)
        streak_val = min(task.current_streak, 30) / 30.0
        
        now = timezone.now()
        weekday_name = now.strftime('%A')
        danger_day = self.get_user_danger_day(user)
        is_danger_day_val = 1.0 if danger_day and weekday_name == danger_day else 0.0

        # Calculate prediction logits
        z = (self.w_priority * priority_val + 
             self.w_consistency * consistency_val + 
             self.w_streak * streak_val + 
             self.w_danger * is_danger_day_val + 
             self.bias)
        
        prob = self._sigmoid(z)

        # Heuristic adjustments for due date pressure (one-off tasks)
        insights = []
        if task.type == 'one_off' and task.due_date:
            time_left = task.due_date - now
            hours_left = time_left.total_seconds() / 3600.0
            
            if hours_left < 0:
                prob = 0.0
                insights.append("Task is past its due date.")
            elif hours_left < 6:
                prob *= 0.5  # Critical time penalty
                insights.append("Urgent: Less than 6 hours remaining to complete the task!")
            elif hours_left < 24:
                prob *= 0.8  # Slight time pressure penalty
                insights.append("Due soon: Less than 24 hours remaining.")
            else:
                insights.append("Plenty of time left before due date.")
        
        # Add factor insights
        if consistency_val > 0.7:
            insights.append("Strong habits: Your high overall consistency score boosts completion likelihood.")
        elif consistency_val < 0.3:
            insights.append("Consistency warning: Low active check-in rate is holding you back.")
            
        if task.current_streak >= 5:
            insights.append(f"Streak momentum: You have a solid {task.current_streak}-day streak going on.")

        if is_danger_day_val > 0:
            insights.append(f"Danger day: {weekday_name}s have historically higher streak reset rates for you.")
            
        if task.priority == 'high':
            insights.append("High priority: Historically, you focus on high priority tasks first.")
        elif task.priority == 'low':
            insights.append("Low priority: Low priority tasks face a higher chance of procrastination.")

        success_prob_pct = round(prob * 100.0, 1)

        # Map probability to risk level
        if success_prob_pct >= 70.0:
            risk_level = 'low'
        elif success_prob_pct >= 40.0:
            risk_level = 'medium'
        else:
            risk_level = 'high'

        return {
            'success_probability': success_prob_pct,
            'risk_level': risk_level,
            'insights': insights
        }

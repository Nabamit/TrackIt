from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TaskViewSet, AICopilotView

router = DefaultRouter()
router.register(r'', TaskViewSet, basename='task')

urlpatterns = [
    path('ai-copilot/', AICopilotView.as_view(), name='ai-copilot'),
    path('', include(router.urls)),
]

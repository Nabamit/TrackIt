from rest_framework import viewsets, permissions
from .models import Project
from .serializers import ProjectSerializer
from .permissions import IsOwner

class ProjectViewSet(viewsets.ModelViewSet):
    """
    ViewSet for viewing and editing projects.
    """
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        # Users should only see projects they own
        if self.request.user.is_authenticated:
            return Project.objects.filter(owner=self.request.user)
        return Project.objects.none()

    def perform_create(self, serializer):
        # Associate the new project with the logged-in user
        serializer.save(owner=self.request.user)

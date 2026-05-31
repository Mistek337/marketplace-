from rest_framework.response import Response
from rest_framework.views import APIView


class HealthAPIView(APIView):
    """GET /api/v1/health — проверка доступности сервиса."""

    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        return Response({"status": "ok"})

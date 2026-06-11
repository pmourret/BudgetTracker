from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .services.dashboard import calculer_dashboard
from .serializers import DashboardSerializer


class DashboardView(APIView):
    """
    Agrégat de tous les indicateurs du dashboard.

    GET /api/v1/analytics/dashboard/?nb_mois=6

    Tous les indicateurs financiers sont de fiabilité RÉELLE,
    sauf le bloc patrimoine (estimatif, séparé).
    """

    def get(self, request):
        try:
            nb_mois = int(request.query_params.get("nb_mois", 6))
        except (TypeError, ValueError):
            nb_mois = 6
        nb_mois = max(1, min(nb_mois, 24))  # borné 1-24 mois

        data = calculer_dashboard(nb_mois=nb_mois)
        serializer = DashboardSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)
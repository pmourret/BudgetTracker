from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .services.dashboard import calculer_dashboard
from .services.compte_dashboard import calculer_compte_dashboard
from .services.projection import calculer_previsionnel
from .serializers import (
    DashboardSerializer,
    CompteDashboardSerializer,
    PrevisionnelSerializer,
)


class DashboardView(APIView):
    """
    Agrégat de tous les indicateurs du dashboard.

    GET /api/v1/analytics/dashboard/?nb_mois=6

    Tous les indicateurs financiers sont de fiabilité RÉELLE,
    sauf le bloc patrimoine (estimatif, séparé).
    """

    def get(self, request):
        import datetime

        try:
            nb_mois = int(request.query_params.get("nb_mois", 6))
        except (TypeError, ValueError):
            nb_mois = 6
        nb_mois = max(1, min(nb_mois, 24))  # borné 1-24 mois

        # Mois comptable affiché (libellé YYYY-MM-DD) ; None → mois courant.
        # Le service borne la valeur à [premier mois avec flux, mois courant].
        mois = None
        mois_param = request.query_params.get("mois")
        if mois_param:
            try:
                mois = datetime.date.fromisoformat(mois_param).replace(day=1)
            except (TypeError, ValueError):
                mois = None

        data = calculer_dashboard(nb_mois=nb_mois, mois=mois)
        serializer = DashboardSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CompteDashboardView(APIView):
    """
    Dashboard d'un compte unique (lecture seule, fiabilité RÉELLE).

    GET /api/v1/analytics/compte/<uuid:compte_id>/

    Agrégats du mois courant scopés au compte : soldes, dépenses/revenus,
    ventilation par catégorie, top dépenses. Transferts et ajustements exclus.
    """

    def get(self, request, compte_id):
        from comptes.models import Compte

        try:
            data = calculer_compte_dashboard(compte_id)
        except Compte.DoesNotExist:
            return Response(
                {"detail": "Compte introuvable."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = CompteDashboardSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PrevisionnelView(APIView):
    """
    Prévisionnel financier (phase 10-A) — lecture seule, fiabilité PROJETÉE.

    GET /api/v1/analytics/previsionnel/?nb_mois=6

    Trois blocs : solde_projete (fin de mois courant), capacite_restante,
    trajectoire (épargne projetée sur nb_mois). Une projection n'est jamais
    une vérité comptable : le solde réel reste la seule référence.
    """

    def get(self, request):
        try:
            nb_mois = int(request.query_params.get("nb_mois", 6))
        except (TypeError, ValueError):
            nb_mois = 6
        nb_mois = max(1, min(nb_mois, 24))  # borné 1-24 mois

        data = calculer_previsionnel(nb_mois=nb_mois)
        serializer = PrevisionnelSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)
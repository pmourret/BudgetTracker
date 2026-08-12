from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    AbonnementsAnalyseSerializer,
    AnalyseSerializer,
    CompteDashboardSerializer,
    DashboardSerializer,
    PointsSerializer,
    PrevisionnelSerializer,
    TransfertsAnalyseSerializer,
)
from .services.abonnements import calculer_abonnements
from .services.analyse import calculer_analyse
from .services.compte_dashboard import calculer_compte_dashboard
from .services.dashboard import calculer_dashboard
from .services.projection import calculer_previsionnel


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


class AnalyseView(APIView):
    """
    Analyse rétrospective (Phase 13) — lecture seule, fiabilité RÉELLE.

    GET /api/v1/analytics/analyse/?nb_mois=6

    Trois blocs sur une fenêtre glissante de mois comptables : tendances
    (dépenses/revenus/épargne + comparaison à la période précédente),
    categories (évolution des postes dans le temps), rythme (jour de
    semaine + libellés récurrents). Aucune projection : le solde réel
    reste la seule vérité, le prévisionnel est une vue séparée.
    """

    def get(self, request):
        try:
            nb_mois = int(request.query_params.get("nb_mois", 6))
        except (TypeError, ValueError):
            nb_mois = 6
        nb_mois = max(1, min(nb_mois, 24))  # borné 1-24 mois

        data = calculer_analyse(nb_mois=nb_mois)
        serializer = AnalyseSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AbonnementsAnalyseView(APIView):
    """
    Analyse des abonnements — lecture seule.

    GET /api/v1/analytics/abonnements/?nb_mois=6

    Cinq blocs : synthese (coût mensuel/annuel + poids budget), par_categorie,
    par_titulaire (qui paye quoi), derive_prix (hausses de tarif), a_risque.
    Base référentiel (estimatif) ; derive_prix/a_risque croisent le réel.
    Ne modifie rien, ne crée aucune alerte.
    """

    def get(self, request):
        try:
            nb_mois = int(request.query_params.get("nb_mois", 6))
        except (TypeError, ValueError):
            nb_mois = 6
        nb_mois = max(1, min(nb_mois, 24))  # borné 1-24 mois

        data = calculer_abonnements(nb_mois=nb_mois)
        serializer = AbonnementsAnalyseSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TransfertsAnalyseView(APIView):
    """
    Analyse des transferts internes — lecture seule, fiabilité RÉELLE.

    GET /api/v1/analytics/transferts/?nb_mois=6

    Agrège les virements entre comptes sur une fenêtre glissante de mois
    comptables : graphe nœud-lien (liens source→destination), volume par mois,
    synthèse. Ne modifie rien, ne crée aucune alerte.
    """

    def get(self, request):
        from .services.transferts import calculer_transferts

        try:
            nb_mois = int(request.query_params.get("nb_mois", 6))
        except (TypeError, ValueError):
            nb_mois = 6
        nb_mois = max(1, min(nb_mois, 24))  # borné 1-24 mois

        data = calculer_transferts(nb_mois=nb_mois)
        serializer = TransfertsAnalyseSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PointsView(APIView):
    """
    Système de points — mécanique B, socle 12-B-1 (lecture seule).

    GET /api/v1/analytics/points/?nb_mois=6

    Réserve de points de discipline budgétaire : chaque enveloppe « en jeu »
    rapporte/coûte des points à la clôture. Le mois en cours est PROJETÉ (non figé) ;
    la réserve disponible ne compte que les mois clôturés. Ne modifie rien.
    """

    def get(self, request):
        from budgets.services import calculer_tableau_points

        try:
            nb_mois = int(request.query_params.get("nb_mois", 6))
        except (TypeError, ValueError):
            nb_mois = 6
        nb_mois = max(1, min(nb_mois, 24))  # borné 1-24 mois

        data = calculer_tableau_points(nb_mois=nb_mois)
        serializer = PointsSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)
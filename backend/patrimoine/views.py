from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .models import Actif
from .serializers import (
    ActifSerializer,
    ValorisationInputSerializer,
    PatrimoineTotalSerializer,
)
from .services import calculer_patrimoine_total, mettre_a_jour_valorisation

from .services import calculer_patrimoine_total, mettre_a_jour_valorisation
from .services.valorisation import calculer_historique_patrimoine

class ActifViewSet(viewsets.ModelViewSet):
    """
    CRUD actifs patrimoniaux.

    ⚠️ Toutes les valorisations sont ESTIMATIVES.
    Elles n'impactent jamais les soldes bancaires réels.

    Actions supplémentaires :
    - POST /patrimoine/{id}/valoriser/
      Met à jour la valeur estimative d'un actif.
    - GET  /patrimoine/total/
      Retourne l'agrégation estimative du patrimoine total.
    """
    serializer_class = ActifSerializer
    filter_backends = [
        DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter
    ]
    filterset_fields = ["type_actif", "actif", "fiscalite"]
    search_fields = ["nom", "notes"]
    ordering_fields = [
        "nom", "type_actif", "valeur_actuelle", "date_valorisation"
    ]
    ordering = ["type_actif", "nom"]

    def get_queryset(self):
        return (
            Actif.objects
            .select_related(
                "compte_associe", "fiscalite", "devise"
            )
            .all()
        )

    @action(detail=True, methods=["post"], url_path="valoriser")
    def valoriser(self, request, pk=None):
        """
        Met à jour la valorisation estimative d'un actif.
        Met à jour date_valorisation automatiquement.

        ⚠️ Valeur estimative — pas une vérité comptable.
        """
        actif = self.get_object()
        input_serializer = ValorisationInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        try:
            mettre_a_jour_valorisation(
                actif,
                input_serializer.validated_data["valeur"]
            )
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        actif.refresh_from_db()
        serializer = self.get_serializer(actif)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="total")
    def total(self, request):
        """
        Retourne l'agrégation estimative du patrimoine total.

        Query param optionnel : ?inclure_inactifs=true

        ⚠️ Fiabilité : ESTIMATIVE.
        """
        inclure_inactifs = (
            request.query_params.get("inclure_inactifs", "false").lower()
            == "true"
        )
        result = calculer_patrimoine_total(inclure_inactifs=inclure_inactifs)
        serializer = PatrimoineTotalSerializer(result)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=["get"], url_path="historique")
    def historique(self, request):
        """
        Série temporelle mensuelle de la valeur totale estimée du patrimoine.

        Query param optionnel : ?nb_mois=12 (défaut 12)

        ⚠️ Fiabilité : ESTIMATIVE (convention carry-forward).
        """
        try:
            nb_mois = int(request.query_params.get("nb_mois", 12))
        except (TypeError, ValueError):
            nb_mois = 12
        nb_mois = max(1, min(nb_mois, 60))  # borné entre 1 et 60 mois

        result = calculer_historique_patrimoine(nb_mois=nb_mois)
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="verifier-rappels")
    def verifier_rappels(self, request):
        """
        Vérifie tous les actifs actifs et génère des alertes de rappel
        de valorisation pour ceux entrant dans leur fenêtre de rappel.

        Déclenché à la demande (le rappel dépend du temps, pas d'un événement).
        """
        from alertes.services import detecter_alerte_valorisation_a_faire

        alertes_creees = []
        for actif in Actif.objects.filter(actif=True):
            alerte = detecter_alerte_valorisation_a_faire(actif)
            if alerte:
                alertes_creees.append(actif.nom)

        return Response(
            {
                "detail": f"{len(alertes_creees)} rappel(s) généré(s).",
                "actifs": alertes_creees,
            },
            status=status.HTTP_200_OK,
        )
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .models import Abonnement
from .serializers import (
    AbonnementSerializer,
    VerifierDivergenceSerializer,
    DivergenceResultSerializer,
)
from .services import verifier_divergence


class AbonnementViewSet(viewsets.ModelViewSet):
    """
    CRUD abonnements récurrents.

    Actions supplémentaires :
    - POST /abonnements/{id}/verifier-divergence/
      Vérifie si un montant réel diverge du montant attendu.
    - POST /abonnements/{id}/desactiver/
      Désactive un abonnement sans le supprimer.
    """
    serializer_class = AbonnementSerializer
    filter_backends = [
        DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter
    ]
    filterset_fields = ["actif", "compte", "categorie", "frequence"]
    search_fields = ["nom", "notes"]
    ordering_fields = ["nom", "montant_attendu", "date_debut", "created_at"]
    ordering = ["nom"]

    def get_queryset(self):
        return (
            Abonnement.objects
            .select_related(
                "compte", "categorie", "type_flux",
                "mode_paiement", "frequence"
            )
            .all()
        )

    @action(detail=True, methods=["post"], url_path="verifier-divergence")
    def verifier_divergence_action(self, request, pk=None):
        """
        Vérifie si un montant réel diverge du montant attendu.

        Body : { "montant_reel": "-17.99" }
        Retourne le résultat de la comparaison avec le seuil configuré.
        """
        abonnement = self.get_object()
        input_serializer = VerifierDivergenceSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        result = verifier_divergence(
            abonnement,
            input_serializer.validated_data["montant_reel"]
        )

        output_serializer = DivergenceResultSerializer(result)
        return Response(output_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="desactiver")
    def desactiver(self, request, pk=None):
        """Désactive un abonnement sans le supprimer."""
        abonnement = self.get_object()
        abonnement.actif = False
        abonnement.save(update_fields=["actif", "updated_at"])
        return Response(
            {"detail": f"Abonnement '{abonnement.nom}' désactivé."},
            status=status.HTTP_200_OK
        )
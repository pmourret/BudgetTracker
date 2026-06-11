from rest_framework import viewsets, filters
from rest_framework.response import Response
from rest_framework import status as drf_status  # conservé pour destroy()
from django_filters.rest_framework import DjangoFilterBackend
from .models import Compte
from .serializers import CompteSerializer


class CompteViewSet(viewsets.ModelViewSet):
    """
    CRUD complet sur les comptes.
    - solde_theorique et ecart_solde en lecture seule.
    - Suppression bloquée si des flux sont rattachés (désactiver à la place).
    """
    serializer_class = CompteSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["actif", "titulaire", "type_compte", "etablissement"]
    ordering_fields = ["code", "nom", "solde_reel", "created_at"]
    ordering = ["code"]

    def get_queryset(self):
        return (
            Compte.objects
            .select_related("type_compte", "titulaire", "etablissement", "devise")
            .all()
        )

    def perform_create(self, serializer):
        from comptes.services.solde import calculer_solde
        compte = serializer.save()
        calculer_solde(compte)

    def perform_update(self, serializer):
        from comptes.services.solde import calculer_solde
        compte = serializer.save()
        calculer_solde(compte)

    def destroy(self, request, *args, **kwargs):
        from flux.models import Flux

        compte = self.get_object()

        if Flux.objects.filter(compte=compte).exists():
            return Response(
                {
                    "detail": (
                        "Ce compte est lié à des flux et ne peut pas être supprimé. "
                        "Désactivez-le plutôt (modification → décocher « actif »)."
                    )
                },
                status=drf_status.HTTP_400_BAD_REQUEST,
            )

        return super().destroy(request, *args, **kwargs)


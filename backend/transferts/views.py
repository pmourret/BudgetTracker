from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, status, viewsets
from rest_framework.response import Response

from .filters import TransfertFilterSet
from .models import Transfert
from .serializers import TransfertSerializer


class TransfertViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Transferts internes entre comptes.

    - POST   /transferts/ → crée la paire débit/crédit atomiquement
    - GET    /transferts/ → liste
    - GET    /transferts/{id}/ → détail
    - DELETE /transferts/{id}/ → soft delete des deux flux + recalcul soldes

    Pas de PUT/PATCH : un transfert ne se modifie pas,
    il se supprime et se recrée.
    """
    serializer_class = TransfertSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = TransfertFilterSet
    search_fields = [
        "notes",
        "flux_debit__compte__nom",
        "flux_credit__compte__nom",
    ]
    ordering_fields = ["flux_debit__date_flux", "montant"]
    ordering = ["-flux_debit__date_flux"]

    def get_queryset(self):
        return (
            Transfert.objects
            .select_related(
                "flux_debit__compte__etablissement",
                "flux_debit__statut",
                "flux_credit__compte__etablissement",
            )
            .all()
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
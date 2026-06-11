from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

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
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["flux_debit__compte", "flux_credit__compte"]

    def get_queryset(self):
        return (
            Transfert.objects
            .select_related(
                "flux_debit__compte",
                "flux_credit__compte",
            )
            .all()
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
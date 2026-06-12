from rest_framework import viewsets, filters, status
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as django_filters

from .models import Flux
from .serializers import FluxSerializer


class FluxFilterSet(django_filters.FilterSet):
    date_min = django_filters.DateFilter(field_name="date_flux", lookup_expr="gte")
    date_max = django_filters.DateFilter(field_name="date_flux", lookup_expr="lte")
    mois = django_filters.DateFilter(field_name="mois", lookup_expr="exact")
    montant_min = django_filters.NumberFilter(field_name="montant", lookup_expr="gte")
    montant_max = django_filters.NumberFilter(field_name="montant", lookup_expr="lte")

    class Meta:
        model = Flux
        fields = [
            "compte",
            "categorie",
            "type_flux",
            "statut",
            "titulaire",
            "est_transfert",
            "date_min",
            "date_max",
            "mois",
            "montant_min",
            "montant_max",
        ]


class FluxViewSet(viewsets.ModelViewSet):
    """
    CRUD flux avec filtres avancés.

    Filtres disponibles :
    - compte, categorie, type_flux, statut, titulaire, est_transfert
    - date_min, date_max, mois
    - montant_min, montant_max

    Note : les flux de transfert ne sont pas créés ici —
    passer par /api/v1/transferts/ pour garantir l'atomicité.
    """
    serializer_class = FluxSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_class = FluxFilterSet
    search_fields = ["libelle", "reference_externe", "notes"]
    ordering_fields = ["date_flux", "montant", "mois", "created_at"]
    ordering = ["-date_flux"]

    def get_queryset(self):
        return (
            Flux.objects
            .select_related(
                "compte", "categorie", "type_flux",
                "statut", "titulaire", "devise", "mode_paiement"
            )
            .all()
        )

    def destroy(self, request, *args, **kwargs):
        """
        Soft delete — déclenche automatiquement le recalcul du solde via signal.

        Protections :
        - Un flux de transfert ne se supprime jamais seul (paire débit/crédit) :
          supprimer le Transfert via /api/v1/transferts/{id}/.
        - Un flux d'ajustement (réconciliation) est figé.
        """
        instance = self.get_object()

        if instance.est_transfert:
            return Response(
                {
                    "detail": (
                        "Ce flux fait partie d'un transfert interne. "
                        "Supprimez le transfert via /api/v1/transferts/ "
                        "pour annuler les deux flux ensemble."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if instance.est_ajustement:
            return Response(
                {
                    "detail": (
                        "Ce flux est un ajustement généré par la réconciliation "
                        "et ne peut pas être supprimé."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
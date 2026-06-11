from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as django_filters

from .models import Budget
from .serializers import BudgetSerializer
from .services import calculer_consommation


class BudgetFilterSet(django_filters.FilterSet):
    mois_min = django_filters.DateFilter(field_name="mois", lookup_expr="gte")
    mois_max = django_filters.DateFilter(field_name="mois", lookup_expr="lte")

    class Meta:
        model = Budget
        fields = ["categorie", "mois", "mois_min", "mois_max"]


class BudgetViewSet(viewsets.ModelViewSet):
    """
    CRUD budgets prévisionnels.

    Filtres disponibles :
    - categorie, mois, mois_min, mois_max

    Action supplémentaire :
    - POST /budgets/{id}/recalculer/ — force le recalcul de la consommation
    """
    serializer_class = BudgetSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = BudgetFilterSet
    ordering_fields = ["mois", "taux_consommation", "montant_prevu"]
    ordering = ["-mois"]

    def get_queryset(self):
        return (
            Budget.objects
            .select_related("categorie")
            .all()
        )

    def perform_create(self, serializer):
        budget = serializer.save()
        calculer_consommation(budget)

    def perform_update(self, serializer):
        budget = serializer.save()
        calculer_consommation(budget)

    @action(detail=True, methods=["post"], url_path="recalculer")
    def recalculer(self, request, pk=None):
        """Force le recalcul de la consommation pour ce budget."""
        budget = self.get_object()
        calculer_consommation(budget)
        budget.refresh_from_db()
        serializer = self.get_serializer(budget)
        return Response(serializer.data, status=status.HTTP_200_OK)
import datetime
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as django_filters

from .models import Budget, BudgetTemplate
from .serializers import BudgetSerializer, BudgetTemplateSerializer
from .services import calculer_consommation, reconduire_vers_mois


class BudgetFilterSet(django_filters.FilterSet):
    mois_min = django_filters.DateFilter(field_name="mois", lookup_expr="gte")
    mois_max = django_filters.DateFilter(field_name="mois", lookup_expr="lte")

    class Meta:
        model = Budget
        fields = ["categorie", "mois", "mois_min", "mois_max"]


class BudgetViewSet(viewsets.ModelViewSet):
    """
    CRUD budgets prévisionnels.

    Filtres : categorie, mois, mois_min, mois_max
    Action : POST /budgets/{id}/recalculer/
    """
    serializer_class = BudgetSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = BudgetFilterSet
    ordering_fields = ["mois", "taux_consommation", "montant_prevu"]
    ordering = ["-mois"]

    def get_queryset(self):
        return (
            Budget.objects
            .select_related("categorie", "template")
            .prefetch_related("categories_incluses")
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
        return Response(self.get_serializer(budget).data)


class BudgetTemplateViewSet(viewsets.ModelViewSet):
    """
    CRUD modèles de budget récurrents.

    Action : POST /budget-templates/reconduire/
      Body : { "mois": "2024-04-01" }
      Crée les budgets du mois cible depuis tous les templates actifs (idempotent).
    """
    serializer_class = BudgetTemplateSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["categorie__nom", "montant_defaut", "actif"]
    ordering = ["categorie__nom"]

    def get_queryset(self):
        return (
            BudgetTemplate.objects
            .select_related("categorie")
            .prefetch_related("categories_incluses")
            .all()
        )

    @action(detail=False, methods=["post"], url_path="reconduire")
    def reconduire(self, request):
        """
        Crée les budgets du mois indiqué depuis tous les templates actifs.
        Idempotent : les catégories ayant déjà un budget ce mois sont ignorées.
        """
        mois_str = request.data.get("mois")
        if not mois_str:
            return Response(
                {"mois": "Ce champ est requis (format : YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            mois_cible = datetime.date.fromisoformat(str(mois_str))
        except ValueError:
            return Response(
                {"mois": "Format invalide. Attendu : YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = reconduire_vers_mois(mois_cible)
        return Response(result, status=status.HTTP_200_OK)

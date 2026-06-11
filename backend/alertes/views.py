from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as django_filters

from .models import Alerte
from .serializers import AlerteSerializer


class AlerteFilterSet(django_filters.FilterSet):
    created_after = django_filters.DateFilter(
        field_name="created_at", lookup_expr="date__gte"
    )
    created_before = django_filters.DateFilter(
        field_name="created_at", lookup_expr="date__lte"
    )

    class Meta:
        model = Alerte
        fields = [
            "type_alerte",
            "niveau",
            "acquittee",
            "compte",
            "budget",
            "abonnement",
            "created_after",
            "created_before",
        ]


class AlerteViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Alertes générées automatiquement.

    - Les alertes sont en lecture seule (générées par les services).
    - Seul l'acquittement est possible via l'action dédiée.
    - GET  /alertes/          → liste (filtrée, triée)
    - GET  /alertes/{id}/     → détail
    - POST /alertes/{id}/acquitter/ → acquitte l'alerte

    Filtres disponibles :
    - type_alerte, niveau, acquittee
    - compte, budget, abonnement
    - created_after, created_before
    """
    serializer_class = AlerteSerializer
    filter_backends = [
        DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter
    ]
    filterset_class = AlerteFilterSet
    search_fields = ["explication"]
    ordering_fields = ["created_at", "niveau", "type_alerte"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return (
            Alerte.objects
            .select_related(
                "compte",
                "budget__categorie",
                "abonnement",
            )
            .all()
        )

    @action(detail=True, methods=["post"], url_path="acquitter")
    def acquitter(self, request, pk=None):
        """Acquitte une alerte — indique que l'utilisateur en a pris connaissance."""
        alerte = self.get_object()

        if alerte.acquittee:
            return Response(
                {"detail": "Cette alerte est déjà acquittée."},
                status=status.HTTP_400_BAD_REQUEST
            )

        alerte.acquitter()
        serializer = self.get_serializer(alerte)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="acquitter-tout")
    def acquitter_tout(self, request):
        """
        Acquitte toutes les alertes non acquittées d'un type donné.
        Body optionnel : { "type_alerte": "BUDGET_ALERTE" }
        """
        from django.utils import timezone
        qs = Alerte.objects.filter(acquittee=False)

        type_alerte = request.data.get("type_alerte")
        if type_alerte:
            qs = qs.filter(type_alerte=type_alerte)

        count = qs.count()
        qs.update(acquittee=True, acquittee_le=timezone.now())

        return Response(
            {"detail": f"{count} alerte(s) acquittée(s)."},
            status=status.HTTP_200_OK
        )
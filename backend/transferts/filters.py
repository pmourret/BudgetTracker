import django_filters

from .models import Transfert


class TransfertFilterSet(django_filters.FilterSet):
    """
    Filtres de la liste des transferts.

    Le compte source = ``flux_debit.compte`` ; le compte destination =
    ``flux_credit.compte``. ``compte`` filtre sur l'un OU l'autre côté
    (tous les transferts touchant ce compte).
    """

    compte_source = django_filters.UUIDFilter(field_name="flux_debit__compte")
    compte_destination = django_filters.UUIDFilter(field_name="flux_credit__compte")
    compte = django_filters.UUIDFilter(method="filtre_compte")

    date_min = django_filters.DateFilter(
        field_name="flux_debit__date_flux", lookup_expr="gte"
    )
    date_max = django_filters.DateFilter(
        field_name="flux_debit__date_flux", lookup_expr="lte"
    )
    montant_min = django_filters.NumberFilter(field_name="montant", lookup_expr="gte")
    montant_max = django_filters.NumberFilter(field_name="montant", lookup_expr="lte")

    est_definitif = django_filters.BooleanFilter(
        field_name="flux_debit__statut__est_definitif"
    )

    class Meta:
        model = Transfert
        fields = [
            "compte_source",
            "compte_destination",
            "compte",
            "date_min",
            "date_max",
            "montant_min",
            "montant_max",
            "est_definitif",
        ]

    def filtre_compte(self, queryset, name, value):
        from django.db.models import Q

        return queryset.filter(
            Q(flux_debit__compte=value) | Q(flux_credit__compte=value)
        )

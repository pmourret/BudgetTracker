from decimal import Decimal

from rest_framework import viewsets, filters, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as django_filters

from .models import Flux
from .serializers import FluxSerializer
from .services.remboursement import RemboursementInvalide, rembourser_flux


class RembourserSerializer(serializers.Serializer):
    """Entrée de l'action `rembourser` : montant reçu, date du crédit, libellé optionnel."""
    montant = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )
    date = serializers.DateField()
    libelle = serializers.CharField(required=False, allow_blank=True)


class FluxFilterSet(django_filters.FilterSet):
    date_min = django_filters.DateFilter(field_name="date_flux", lookup_expr="gte")
    date_max = django_filters.DateFilter(field_name="date_flux", lookup_expr="lte")
    mois = django_filters.DateFilter(field_name="mois", lookup_expr="exact")
    montant_min = django_filters.NumberFilter(field_name="montant", lookup_expr="gte")
    montant_max = django_filters.NumberFilter(field_name="montant", lookup_expr="lte")
    # Propriétaire du compte (≠ titulaire du flux, souvent nul) : filtre sur
    # le titulaire du compte rattaché.
    titulaire_compte = django_filters.UUIDFilter(field_name="compte__titulaire")
    # Prévisionnel (False) vs validé/définitif (True) — via le statut du flux.
    est_definitif = django_filters.BooleanFilter(field_name="statut__est_definitif")

    class Meta:
        model = Flux
        fields = [
            "compte",
            "categorie",
            "type_flux",
            "statut",
            "titulaire",
            "titulaire_compte",
            "est_transfert",
            "est_ajustement",
            "est_definitif",
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
    - titulaire_compte (propriétaire du compte), est_definitif (validé/prévisionnel)
    - date_min, date_max, mois
    - montant_min, montant_max
    - search (libellé, référence externe, notes)

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
        # Annotation `est_pointe` (14-B) : le flux est-il rapproché à une ligne
        # de relevé d'un lot vivant ? Import local pour éviter le couplage au
        # chargement des apps (imports référence flux).
        from django.db.models import Exists, OuterRef, Q, Sum, Value
        from django.db.models.functions import Coalesce
        from imports.models import LigneBancaire, StatutRapprochement

        ligne_pointee = LigneBancaire.objects.filter(
            flux=OuterRef("pk"),
            statut=StatutRapprochement.RAPPROCHE,
            import_lot__is_deleted=False,
        )
        return (
            Flux.objects
            .select_related(
                "compte", "categorie", "type_flux",
                "statut", "titulaire", "devise", "mode_paiement"
            )
            .annotate(
                est_pointe=Exists(ligne_pointee),
                # Σ des remboursements (recettes liées) non supprimés. Le front
                # dérive « Remboursé » (Σ ≥ |montant|) vs « partiellement ».
                montant_rembourse=Coalesce(
                    Sum(
                        "remboursements__montant",
                        filter=Q(remboursements__is_deleted=False),
                    ),
                    Value(Decimal("0")),
                ),
            )
            .all()
        )

    @action(detail=True, methods=["post"])
    def rembourser(self, request, pk=None):
        """
        Crée le contre-flux recette qui rembourse (tout ou partie de) cette dépense.

        Body : {montant, date, libelle?}. Renvoie 201 {flux, contre_flux}.
        L'annulation d'un remboursement = suppression normale du contre-flux.
        """
        flux = self.get_object()
        entree = RembourserSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        try:
            contre_flux = rembourser_flux(
                flux,
                montant=entree.validated_data["montant"],
                date=entree.validated_data["date"],
                libelle=entree.validated_data.get("libelle") or None,
            )
        except RemboursementInvalide as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        flux.refresh_from_db()
        return Response(
            {
                "flux": FluxSerializer(self.get_queryset().get(pk=flux.pk)).data,
                "contre_flux": FluxSerializer(
                    self.get_queryset().get(pk=contre_flux.pk)
                ).data,
            },
            status=status.HTTP_201_CREATED,
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
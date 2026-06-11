from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status as drf_status
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

    @action(detail=True, methods=["post"], url_path="reconcilier")
    def reconcilier(self, request, pk=None):
        """
        Crée un flux d'ajustement pour équilibrer solde_theorique et solde_reel.
        Le flux a est_ajustement=True et est exclu de tous les agrégats.
        """
        import datetime
        from flux.models import Flux
        from referentiels.models import TypeFlux, StatutFlux

        compte = self.get_object()
        ecart = compte.ecart_solde

        if ecart == 0:
            return Response(
                {"detail": "Le solde est déjà équilibré."},
                status=drf_status.HTTP_200_OK,
            )

        type_flux = (
            TypeFlux.objects.filter(code="CREDIT" if ecart > 0 else "DEBIT").first()
            or TypeFlux.objects.filter(actif=True).first()
        )
        statut = (
            StatutFlux.objects.filter(code="VALIDE").first()
            or StatutFlux.objects.filter(actif=True).first()
        )

        if not type_flux or not statut:
            return Response(
                {"detail": "Référentiels manquants (TypeFlux/StatutFlux). Lancez seed_demo."},
                status=drf_status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        Flux.objects.create(
            compte=compte,
            montant=ecart,
            date_flux=datetime.date.today(),
            libelle=f"Ajustement de solde — {compte.code}",
            est_transfert=False,
            est_ajustement=True,
            type_flux=type_flux,
            statut=statut,
            devise=compte.devise,
            categorie=None,
        )
        compte.refresh_from_db()

        return Response(
            {
                "detail": f"Flux d'ajustement de {ecart:+} € créé.",
                "ecart_solde": compte.ecart_solde,
                "solde_theorique": compte.solde_theorique,
            },
            status=drf_status.HTTP_201_CREATED,
        )
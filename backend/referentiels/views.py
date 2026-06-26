from rest_framework import viewsets, filters, generics
from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    ParametresBudget,
    TypeCompte, TypeFlux, Titulaire, ModePaiement,
    Frequence, Etablissement, Devise, Fiscalite, StatutFlux
)
from .serializers import (
    ParametresBudgetSerializer,
    TypeCompteSerializer, TypeFluxSerializer,
    TitulaireSerializer, TitulaireWritableSerializer,
    ModePaiementSerializer, FrequenceSerializer,
    EtablissementSerializer, EtablissementWritableSerializer,
    DeviseSerializer, FiscaliteSerializer, StatutFluxSerializer
)


class ParametresBudgetView(generics.RetrieveUpdateAPIView):
    """
    Lecture / mise à jour des paramètres globaux du foyer (singleton).
    GET et PATCH/PUT sur une ressource unique (pas de pk dans l'URL).
    """
    serializer_class = ParametresBudgetSerializer
    # queryset requis par les permissions (DjangoModelPermissions interroge
    # get_queryset() sur les écritures) ; get_object renvoie le singleton.
    queryset = ParametresBudget.objects.all()

    def get_object(self):
        return ParametresBudget.get_solo()

    def perform_update(self, serializer):
        """
        Si le jour de bascule change, remappe tout l'historique des flux
        (mois comptable) de façon transparente : l'utilisateur n'a pas à
        lancer la commande à la main. La logique vit dans la couche services.
        """
        ancien_jour = serializer.instance.jour_debut_mois_comptable
        instance = serializer.save()
        if instance.jour_debut_mois_comptable != ancien_jour:
            from flux.services.recalcul_mois import recalculer_mois_flux

            recalculer_mois_flux()


class ReferentielBaseViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Base read-only pour tous les référentiels.
    Filtre par défaut sur actif=True, triable par ordre.
    """
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["actif"]
    ordering_fields = ["ordre", "libelle"]
    ordering = ["ordre", "libelle"]

    def get_queryset(self):
        return self.queryset_model.objects.all()


class TypeCompteViewSet(ReferentielBaseViewSet):
    queryset_model = TypeCompte
    serializer_class = TypeCompteSerializer


class TypeFluxViewSet(ReferentielBaseViewSet):
    queryset_model = TypeFlux
    serializer_class = TypeFluxSerializer


class TitulaireViewSet(viewsets.ModelViewSet):
    queryset_model = Titulaire
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["actif"]
    ordering_fields = ["ordre", "libelle"]
    ordering = ["ordre", "libelle"]

    def get_queryset(self):
        return Titulaire.objects.all()

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return TitulaireWritableSerializer
        return TitulaireSerializer


class ModePaiementViewSet(ReferentielBaseViewSet):
    queryset_model = ModePaiement
    serializer_class = ModePaiementSerializer


class FrequenceViewSet(ReferentielBaseViewSet):
    queryset_model = Frequence
    serializer_class = FrequenceSerializer


class EtablissementViewSet(viewsets.ModelViewSet):
    queryset_model = Etablissement
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["actif"]
    ordering_fields = ["ordre", "libelle"]
    ordering = ["ordre", "libelle"]

    def get_queryset(self):
        return Etablissement.objects.all()

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return EtablissementWritableSerializer
        return EtablissementSerializer


class DeviseViewSet(ReferentielBaseViewSet):
    queryset_model = Devise
    serializer_class = DeviseSerializer


class FiscaliteViewSet(ReferentielBaseViewSet):
    queryset_model = Fiscalite
    serializer_class = FiscaliteSerializer


class StatutFluxViewSet(ReferentielBaseViewSet):
    queryset_model = StatutFlux
    serializer_class = StatutFluxSerializer
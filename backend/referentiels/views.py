from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    TypeCompte, TypeFlux, Titulaire, ModePaiement,
    Frequence, Etablissement, Devise, Fiscalite, StatutFlux
)
from .serializers import (
    TypeCompteSerializer, TypeFluxSerializer,
    TitulaireSerializer, TitulaireWritableSerializer,
    ModePaiementSerializer, FrequenceSerializer,
    EtablissementSerializer, EtablissementWritableSerializer,
    DeviseSerializer, FiscaliteSerializer, StatutFluxSerializer
)


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
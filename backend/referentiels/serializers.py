import re
from rest_framework import serializers
from .models import (
    ParametresBudget,
    TypeCompte, TypeFlux, Titulaire, ModePaiement,
    Frequence, Etablissement, Devise, Fiscalite, StatutFlux
)


class ParametresBudgetSerializer(serializers.ModelSerializer):
    """Paramètres globaux du foyer (singleton)."""

    class Meta:
        model = ParametresBudget
        fields = ["id", "jour_debut_mois_comptable"]
        read_only_fields = ["id"]


def _auto_code(libelle, prefix, model_class):
    """
    Génère un code unique à partir du libellé (ex: 'BNP Paribas' → 'ETA-BNP-PARIBAS').
    Vérifie aussi les lignes soft-deletées : la contrainte d'unicité en base
    porte sur toutes les lignes, supprimées comprises.
    """
    slug = re.sub(r'[^A-Z0-9]', '-', libelle.upper().strip())
    slug = re.sub(r'-+', '-', slug).strip('-')[:20]
    base = f"{prefix}-{slug}"[:50]
    if not model_class.objects.all_with_deleted().filter(code=base).exists():
        return base
    i = 2
    while model_class.objects.all_with_deleted().filter(code=f"{base}-{i}"[:50]).exists():
        i += 1
    return f"{base}-{i}"[:50]


class ReferentielBaseSerializer(serializers.ModelSerializer):
    """Champs communs à tous les référentiels."""
    class Meta:
        fields = ["id", "code", "libelle", "ordre", "actif"]


class TypeCompteSerializer(ReferentielBaseSerializer):
    class Meta(ReferentielBaseSerializer.Meta):
        model = TypeCompte


class TypeFluxSerializer(ReferentielBaseSerializer):
    class Meta(ReferentielBaseSerializer.Meta):
        model = TypeFlux


class TitulaireSerializer(ReferentielBaseSerializer):
    class Meta(ReferentielBaseSerializer.Meta):
        model = Titulaire


class TitulaireWritableSerializer(serializers.ModelSerializer):
    code = serializers.CharField(required=False, max_length=50, allow_blank=True, default='')

    class Meta:
        model = Titulaire
        fields = ["id", "code", "libelle", "ordre", "actif"]

    def create(self, validated_data):
        if not validated_data.get('code'):
            validated_data['code'] = _auto_code(validated_data['libelle'], 'TIT', Titulaire)
        return super().create(validated_data)


class ModePaiementSerializer(ReferentielBaseSerializer):
    class Meta(ReferentielBaseSerializer.Meta):
        model = ModePaiement


class FrequenceSerializer(ReferentielBaseSerializer):
    class Meta(ReferentielBaseSerializer.Meta):
        model = Frequence
        fields = ["id", "code", "libelle", "ordre", "actif", "nb_jours"]


class EtablissementSerializer(ReferentielBaseSerializer):
    class Meta(ReferentielBaseSerializer.Meta):
        model = Etablissement


class EtablissementWritableSerializer(serializers.ModelSerializer):
    code = serializers.CharField(required=False, max_length=50, allow_blank=True, default='')

    class Meta:
        model = Etablissement
        fields = ["id", "code", "libelle", "ordre", "actif"]

    def create(self, validated_data):
        if not validated_data.get('code'):
            validated_data['code'] = _auto_code(validated_data['libelle'], 'ETA', Etablissement)
        return super().create(validated_data)


class DeviseSerializer(ReferentielBaseSerializer):
    class Meta(ReferentielBaseSerializer.Meta):
        model = Devise
        fields = ["id", "code", "libelle", "ordre", "actif", "symbole", "est_defaut"]


class FiscaliteSerializer(ReferentielBaseSerializer):
    class Meta(ReferentielBaseSerializer.Meta):
        model = Fiscalite


class StatutFluxSerializer(ReferentielBaseSerializer):
    class Meta(ReferentielBaseSerializer.Meta):
        model = StatutFlux
        fields = ["id", "code", "libelle", "ordre", "actif", "est_definitif"]
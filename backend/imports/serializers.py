from rest_framework import serializers

from categories.models import Categorie
from comptes.models import Compte
from .models import Banque, ImportBancaire, LigneBancaire


class ImportBancaireSerializer(serializers.ModelSerializer):
    """Synthèse d'un lot d'import (lecture seule — création via le service)."""

    compte_nom = serializers.CharField(source="compte.nom", read_only=True)

    class Meta:
        model = ImportBancaire
        fields = [
            "id", "compte", "compte_nom", "banque", "nom_fichier",
            "compte_num_source", "nb_lignes", "nb_rapproches",
            "nb_manquants_app", "nb_ambigus", "nb_ignores",
            "nb_doublons_ignores", "created_at",
        ]
        read_only_fields = fields


class FluxResumeSerializer(serializers.Serializer):
    """Vue compacte d'un flux app (apparié ou candidat) pour le rapport."""

    id = serializers.UUIDField()
    date_flux = serializers.DateField()
    montant = serializers.DecimalField(max_digits=12, decimal_places=2)
    libelle = serializers.CharField()
    est_definitif = serializers.SerializerMethodField()
    est_transfert = serializers.BooleanField()
    categorie_nom = serializers.SerializerMethodField()

    def get_est_definitif(self, obj):
        return obj.statut.est_definitif

    def get_categorie_nom(self, obj):
        return obj.categorie.nom if obj.categorie_id else None


class LigneBancaireSerializer(serializers.ModelSerializer):
    """Une ligne de relevé + son verdict de rapprochement (lecture seule)."""

    class Meta:
        model = LigneBancaire
        fields = [
            "id", "import_lot", "date_operation", "date_valeur", "libelle",
            "libelle_suggere", "categorie_banque", "categorie_parent_banque",
            "montant", "solde_apres", "pointe_banque", "statut", "flux",
        ]
        read_only_fields = fields


class ImportUploadSerializer(serializers.Serializer):
    """
    Entrée de l'upload multipart : fichier + banque + compte cible OPTIONNEL.

    Si `compte` est omis, le service résout le compte automatiquement via le
    numéro de compte (`accountNum`) du fichier = `Compte.code`.
    """

    compte = serializers.PrimaryKeyRelatedField(
        queryset=Compte.objects.all(), required=False, allow_null=True
    )
    banque = serializers.ChoiceField(
        choices=Banque.choices, default=Banque.BOURSOBANK
    )
    fichier = serializers.FileField()


class ValiderLigneSerializer(serializers.Serializer):
    """Entrée de la validation d'un ambigu : le flux choisi par l'utilisateur."""

    flux_id = serializers.UUIDField()


class CreerFluxSerializer(serializers.Serializer):
    """Entrée de la création d'un flux depuis une ligne (14-B)."""

    categorie = serializers.PrimaryKeyRelatedField(queryset=Categorie.objects.all())
    libelle = serializers.CharField(required=False, allow_blank=True)

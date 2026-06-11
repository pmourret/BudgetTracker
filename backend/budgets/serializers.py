from rest_framework import serializers
from .models import Budget


class BudgetSerializer(serializers.ModelSerializer):
    categorie_nom = serializers.CharField(
        source="categorie.nom", read_only=True
    )
    montant_consomme = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    taux_consommation = serializers.DecimalField(
        max_digits=6, decimal_places=2, read_only=True
    )
    montant_restant = serializers.SerializerMethodField()
    statut_consommation = serializers.SerializerMethodField()

    # Champs calculés exposés en écriture uniquement pour détecter les tentatives
    _montant_consomme_input = serializers.DecimalField(
        max_digits=12, decimal_places=2,
        write_only=True, required=False
    )
    _taux_consommation_input = serializers.DecimalField(
        max_digits=6, decimal_places=2,
        write_only=True, required=False
    )

    class Meta:
        model = Budget
        fields = [
            "id",
            "categorie",
            "categorie_nom",
            "mois",
            "montant_prevu",
            "montant_consomme",
            "taux_consommation",
            "montant_restant",
            "statut_consommation",
            "_montant_consomme_input",
            "_taux_consommation_input",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "montant_consomme",
            "taux_consommation",
            "created_at",
            "updated_at",
        ]

    def get_montant_restant(self, obj):
        return obj.montant_prevu - obj.montant_consomme

    def get_statut_consommation(self, obj):
        """
        Indicateur qualitatif basé sur le taux de consommation.
        Fiabilité : réel (basé sur les flux saisis).
        """
        taux = obj.taux_consommation
        if taux >= 100:
            return "depasse"
        elif taux >= 80:
            return "alerte"
        elif taux >= 50:
            return "en_cours"
        return "ok"

    def validate_montant_prevu(self, montant):
        if montant <= 0:
            raise serializers.ValidationError(
                "Le montant prévu doit être strictement positif."
            )
        return montant

    def validate(self, data):
        # Protection champs calculés
        if "_montant_consomme_input" in data:
            raise serializers.ValidationError(
                {"montant_consomme": "Ce champ est calculé et non modifiable."}
            )
        if "_taux_consommation_input" in data:
            raise serializers.ValidationError(
                {"taux_consommation": "Ce champ est calculé et non modifiable."}
            )

        # Unicité (categorie, mois) avec normalisation au 1er du mois
        categorie = data.get("categorie", getattr(self.instance, "categorie", None))
        mois = data.get("mois", getattr(self.instance, "mois", None))

        if categorie and mois:
            mois_normalise = mois.replace(day=1)
            qs = Budget.objects.filter(
                categorie=categorie,
                mois=mois_normalise,
            )
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"mois": "Un budget existe déjà pour cette catégorie et ce mois."}
                )

        return data

    def to_internal_value(self, data):
        """
        Détecte les tentatives d'écriture sur les champs calculés
        avant la validation standard.
        """
        errors = {}
        if "montant_consomme" in data:
            errors["montant_consomme"] = "Ce champ est calculé et non modifiable."
        if "taux_consommation" in data:
            errors["taux_consommation"] = "Ce champ est calculé et non modifiable."
        if errors:
            raise serializers.ValidationError(errors)
        return super().to_internal_value(data)
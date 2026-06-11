from rest_framework import serializers
from .models import Alerte


class AlerteSerializer(serializers.ModelSerializer):
    type_alerte_display = serializers.CharField(
        source="get_type_alerte_display", read_only=True
    )
    niveau_display = serializers.CharField(
        source="get_niveau_display", read_only=True
    )

    # Contexte lisible
    compte_nom = serializers.CharField(
        source="compte.nom", read_only=True
    )
    budget_detail = serializers.SerializerMethodField()
    abonnement_nom = serializers.CharField(
        source="abonnement.nom", read_only=True
    )

    class Meta:
        model = Alerte
        fields = [
            "id",
            "type_alerte",
            "type_alerte_display",
            "niveau",
            "niveau_display",
            "compte",
            "compte_nom",
            "budget",
            "budget_detail",
            "abonnement",
            "abonnement_nom",
            "explication",
            "valeur_constatee",
            "valeur_seuil",
            "acquittee",
            "acquittee_le",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "type_alerte",
            "niveau",
            "explication",
            "valeur_constatee",
            "valeur_seuil",
            "acquittee_le",
            "created_at",
            "updated_at",
        ]

    def get_budget_detail(self, obj):
        if obj.budget:
            return {
                "id": str(obj.budget.id),
                "categorie_nom": obj.budget.categorie.nom,
                "mois": obj.budget.mois,
            }
        return None

    def validate(self, data):
        """
        Seul le champ acquittee est modifiable via l'API.
        Tout le reste est en lecture seule.
        """
        champs_interdits = {
            "type_alerte", "niveau", "explication",
            "valeur_constatee", "valeur_seuil"
        }
        tentatives = champs_interdits & set(self.initial_data.keys())
        if tentatives:
            raise serializers.ValidationError(
                {champ: "Ce champ n'est pas modifiable."
                 for champ in tentatives}
            )
        return data
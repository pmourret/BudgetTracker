from rest_framework import serializers
from .models import Abonnement
from .services import verifier_divergence
from decimal import Decimal


class AbonnementSerializer(serializers.ModelSerializer):
    # Représentations lisibles
    compte_nom = serializers.CharField(source="compte.nom", read_only=True)
    categorie_nom = serializers.CharField(
        source="categorie.nom", read_only=True
    )
    frequence_libelle = serializers.CharField(
        source="frequence.libelle", read_only=True
    )
    frequence_nb_jours = serializers.IntegerField(
        source="frequence.nb_jours", read_only=True
    )

    # Champs calculés
    est_en_retard = serializers.BooleanField(read_only=True)
    derniere_occurrence = serializers.DateField(read_only=True)

    class Meta:
        model = Abonnement
        fields = [
            "id",
            "nom",
            "compte",
            "compte_nom",
            "categorie",
            "categorie_nom",
            "type_flux",
            "mode_paiement",
            "frequence",
            "frequence_libelle",
            "frequence_nb_jours",
            "montant_attendu",
            "seuil_divergence_pct",
            "date_debut",
            "date_fin",
            "jour_echeance",
            "derniere_occurrence",   # read_only
            "est_en_retard",         # read_only
            "actif",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "derniere_occurrence",
            "created_at",
            "updated_at",
        ]

    def validate(self, data):
        """
        - date_fin doit être postérieure à date_debut.
        - montant_attendu ne peut pas être nul.
        - jour_echeance entre 1 et 31.
        """
        date_debut = data.get(
            "date_debut", getattr(self.instance, "date_debut", None)
        )
        date_fin = data.get(
            "date_fin", getattr(self.instance, "date_fin", None)
        )

        if date_fin and date_debut and date_fin <= date_debut:
            raise serializers.ValidationError(
                {"date_fin": "La date de fin doit être postérieure à la date de début."}
            )

        montant = data.get(
            "montant_attendu",
            getattr(self.instance, "montant_attendu", None)
        )
        if montant is not None and montant == 0:
            raise serializers.ValidationError(
                {"montant_attendu": "Le montant attendu ne peut pas être nul."}
            )

        jour = data.get(
            "jour_echeance",
            getattr(self.instance, "jour_echeance", None)
        )
        if jour is not None and not (1 <= jour <= 31):
            raise serializers.ValidationError(
                {"jour_echeance": "Le jour d'échéance doit être compris entre 1 et 31."}
            )

        return data


class VerifierDivergenceSerializer(serializers.Serializer):
    """Serializer pour l'action de vérification de divergence."""
    montant_reel = serializers.DecimalField(max_digits=12, decimal_places=2)


class DivergenceResultSerializer(serializers.Serializer):
    """Serializer pour le résultat de vérification de divergence."""
    divergence_pct = serializers.DecimalField(max_digits=5, decimal_places=2)
    en_divergence = serializers.BooleanField()
    montant_attendu = serializers.DecimalField(max_digits=12, decimal_places=2)
    montant_reel = serializers.DecimalField(max_digits=12, decimal_places=2)
    seuil_pct = serializers.DecimalField(max_digits=5, decimal_places=2)
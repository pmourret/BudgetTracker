from rest_framework import serializers
from .models import Flux


class FluxSerializer(serializers.ModelSerializer):
    # Représentations lisibles
    compte_nom = serializers.CharField(source="compte.nom", read_only=True)
    categorie_nom = serializers.CharField(source="categorie.nom", read_only=True)
    type_flux_code = serializers.CharField(source="type_flux.code", read_only=True)
    statut_code = serializers.CharField(source="statut.code", read_only=True)
    devise_symbole = serializers.CharField(source="devise.symbole", read_only=True)

    # Champ calculé — jamais éditable
    mois = serializers.DateField(read_only=True)

    class Meta:
        model = Flux
        fields = [
            "id",
            "compte",
            "compte_nom",
            "categorie",
            "categorie_nom",
            "type_flux",
            "type_flux_code",
            "statut",
            "statut_code",
            "titulaire",
            "mode_paiement",
            "devise",
            "devise_symbole",
            "montant",
            "date_flux",
            "mois",           # read_only
            "est_transfert",
            "est_ajustement",
            "libelle",
            "notes",
            "reference_externe",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "mois", "est_ajustement", "created_at", "updated_at"]

    def validate_montant(self, montant):
        """Le montant ne peut pas être nul."""
        if montant == 0:
            raise serializers.ValidationError("Le montant ne peut pas être zéro.")
        return montant

    def validate(self, data):
        """
        Un flux non-transfert doit avoir une catégorie.
        Les flux de transfert sont gérés exclusivement via /api/v1/transferts/
        (paire débit/crédit atomique) : ni création directe, ni modification ici.
        Les flux d'ajustement (générés par la réconciliation) sont figés.
        """
        if self.instance is not None:
            if self.instance.est_transfert:
                raise serializers.ValidationError(
                    {
                        "detail": (
                            "Ce flux fait partie d'un transfert interne. "
                            "Supprimez le transfert et recréez-le via /api/v1/transferts/."
                        )
                    }
                )
            if self.instance.est_ajustement:
                raise serializers.ValidationError(
                    {
                        "detail": (
                            "Ce flux est un ajustement généré par la réconciliation. "
                            "Il ne peut pas être modifié."
                        )
                    }
                )

        if data.get("est_transfert", False):
            raise serializers.ValidationError(
                {
                    "est_transfert": (
                        "Un flux de transfert ne se crée pas directement. "
                        "Utilisez /api/v1/transferts/ pour garantir la paire débit/crédit."
                    )
                }
            )

        categorie = data.get(
            "categorie", getattr(self.instance, "categorie", None)
        )
        if categorie is None:
            raise serializers.ValidationError(
                {"categorie": "Une catégorie est obligatoire pour un flux non-transfert."}
            )
        return data
import datetime
from decimal import Decimal
from rest_framework import serializers
from .models import Transfert
from transferts.services import creer_transfert
from referentiels.models import TypeFlux, StatutFlux, Devise
from comptes.models import Compte


class TransfertSerializer(serializers.ModelSerializer):
    # Lecture
    compte_source_nom = serializers.CharField(
        source="flux_debit.compte.nom", read_only=True
    )
    compte_source_id = serializers.UUIDField(
        source="flux_debit.compte.id", read_only=True
    )
    compte_source_etablissement = serializers.CharField(
        source="flux_debit.compte.etablissement.libelle", read_only=True, default=None
    )
    compte_destination_nom = serializers.CharField(
        source="flux_credit.compte.nom", read_only=True
    )
    compte_destination_id = serializers.UUIDField(
        source="flux_credit.compte.id", read_only=True
    )
    compte_destination_etablissement = serializers.CharField(
        source="flux_credit.compte.etablissement.libelle", read_only=True, default=None
    )
    date_flux = serializers.DateField(source="flux_debit.date_flux", read_only=True)
    statut_libelle = serializers.CharField(
        source="flux_debit.statut.libelle", read_only=True
    )
    est_definitif = serializers.BooleanField(
        source="flux_debit.statut.est_definitif", read_only=True
    )

    # Écriture uniquement
    compte_source = serializers.PrimaryKeyRelatedField(
        queryset=Compte.objects.all(), write_only=True
    )
    compte_destination = serializers.PrimaryKeyRelatedField(
        queryset=Compte.objects.all(), write_only=True
    )
    date = serializers.DateField(write_only=True)
    type_flux_debit = serializers.PrimaryKeyRelatedField(
        queryset=TypeFlux.objects.all(), write_only=True
    )
    type_flux_credit = serializers.PrimaryKeyRelatedField(
        queryset=TypeFlux.objects.all(), write_only=True
    )
    statut = serializers.PrimaryKeyRelatedField(
        queryset=StatutFlux.objects.all(), write_only=True
    )
    devise = serializers.PrimaryKeyRelatedField(
        queryset=Devise.objects.all(), write_only=True
    )

    class Meta:
        model = Transfert
        fields = [
            "id",
            "compte_source",
            "compte_source_nom",
            "compte_source_id",
            "compte_source_etablissement",
            "compte_destination",
            "compte_destination_nom",
            "compte_destination_id",
            "compte_destination_etablissement",
            "montant",
            "date",
            "date_flux",
            "statut_libelle",
            "est_definitif",
            "type_flux_debit",
            "type_flux_credit",
            "statut",
            "devise",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "date_flux", "created_at", "updated_at"]

    def validate(self, data):
        if data["compte_source"] == data["compte_destination"]:
            raise serializers.ValidationError(
                {"compte_destination": "Source et destination doivent être différents."}
            )
        if data["montant"] <= Decimal("0"):
            raise serializers.ValidationError(
                {"montant": "Le montant doit être strictement positif."}
            )
        return data

    def create(self, validated_data):
        """Délègue la création au service — garantit l'atomicité."""
        return creer_transfert(
            compte_source=validated_data["compte_source"],
            compte_destination=validated_data["compte_destination"],
            montant=validated_data["montant"],
            date_flux=validated_data["date"],
            type_flux_debit=validated_data["type_flux_debit"],
            type_flux_credit=validated_data["type_flux_credit"],
            statut=validated_data["statut"],
            devise=validated_data["devise"],
            notes=validated_data.get("notes", ""),
        )
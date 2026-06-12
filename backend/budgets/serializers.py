from rest_framework import serializers
from categories.models import Categorie
from .models import Budget, BudgetTemplate


def _auto_detect_est_budget_majeur(categorie):
    """Majeure = racine avec au moins une sous-catégorie active."""
    return (
        categorie.parent_id is None
        and categorie.sous_categories.filter(actif=True).exists()
    )


def _valider_appartenance_mineures(categorie, categories_incluses):
    """Chaque catégorie incluse doit être une sous-catégorie directe de la majeure."""
    for mineure in categories_incluses:
        if mineure.parent_id != categorie.id:
            raise serializers.ValidationError({
                "categories_incluses": (
                    f"« {mineure.nom} » n'est pas une sous-catégorie "
                    f"de « {categorie.nom} »."
                )
            })


class BudgetTemplateSerializer(serializers.ModelSerializer):
    categorie_nom = serializers.CharField(source="categorie.nom", read_only=True)
    categories_incluses = serializers.PrimaryKeyRelatedField(
        many=True,
        required=False,
        queryset=Categorie.objects.all(),
    )
    categories_incluses_detail = serializers.SerializerMethodField()
    nb_budgets_mensuels = serializers.SerializerMethodField()

    class Meta:
        model = BudgetTemplate
        fields = [
            "id",
            "categorie",
            "categorie_nom",
            "montant_defaut",
            "est_budget_majeur",
            "categories_incluses",
            "categories_incluses_detail",
            "actif",
            "notes",
            "nb_budgets_mensuels",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "est_budget_majeur",
            "categories_incluses_detail",
            "nb_budgets_mensuels",
            "created_at",
            "updated_at",
        ]

    def get_categories_incluses_detail(self, obj):
        return [{"id": str(c.id), "nom": c.nom} for c in obj.categories_incluses.all()]

    def get_nb_budgets_mensuels(self, obj):
        return obj.budgets_mensuels.count()

    def validate_montant_defaut(self, montant):
        if montant <= 0:
            raise serializers.ValidationError(
                "Le montant par défaut doit être strictement positif."
            )
        return montant

    def validate(self, data):
        categorie = data.get("categorie", getattr(self.instance, "categorie", None))
        if not categorie:
            return data

        data["est_budget_majeur"] = _auto_detect_est_budget_majeur(categorie)
        est_budget_majeur = data["est_budget_majeur"]

        # Unicité catégorie
        qs = BudgetTemplate.objects.filter(categorie=categorie)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {"categorie": "Un modèle de budget existe déjà pour cette catégorie."}
            )

        if est_budget_majeur:
            if "categories_incluses" not in data and self.instance is None:
                data["categories_incluses"] = list(
                    categorie.sous_categories.filter(actif=True)
                )
            categories_incluses = data.get(
                "categories_incluses",
                list(self.instance.categories_incluses.all()) if self.instance else [],
            )
            if not categories_incluses:
                raise serializers.ValidationError({
                    "categories_incluses": (
                        "Un modèle de catégorie majeure doit inclure au moins une sous-catégorie."
                    )
                })
            _valider_appartenance_mineures(categorie, categories_incluses)
        else:
            # Pas de mineures incluses sur un modèle non majeur
            data["categories_incluses"] = []

        return data

    def create(self, validated_data):
        categories_incluses = validated_data.pop("categories_incluses", [])
        instance = super().create(validated_data)
        instance.categories_incluses.set(categories_incluses)
        return instance

    def update(self, instance, validated_data):
        categories_incluses = validated_data.pop("categories_incluses", None)
        instance = super().update(instance, validated_data)
        if categories_incluses is not None:
            instance.categories_incluses.set(categories_incluses)
        return instance


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

    _montant_consomme_input = serializers.DecimalField(
        max_digits=12, decimal_places=2, write_only=True, required=False
    )
    _taux_consommation_input = serializers.DecimalField(
        max_digits=6, decimal_places=2, write_only=True, required=False
    )

    categories_incluses = serializers.PrimaryKeyRelatedField(
        many=True,
        required=False,
        queryset=Categorie.objects.all(),
    )
    categories_incluses_detail = serializers.SerializerMethodField()
    template_id = serializers.PrimaryKeyRelatedField(
        source="template", read_only=True, allow_null=True,
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
            "est_budget_majeur",
            "categories_incluses",
            "categories_incluses_detail",
            "template_id",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "montant_consomme",
            "taux_consommation",
            "est_budget_majeur",
            "categories_incluses_detail",
            "template_id",
            "created_at",
            "updated_at",
        ]

    def get_montant_restant(self, obj):
        return obj.montant_prevu - obj.montant_consomme

    def get_statut_consommation(self, obj):
        """Fiabilité : réel (basé sur les flux saisis)."""
        taux = obj.taux_consommation
        if taux >= 100:
            return "depasse"
        elif taux >= 80:
            return "alerte"
        elif taux >= 50:
            return "en_cours"
        return "ok"

    def get_categories_incluses_detail(self, obj):
        return [{"id": str(c.id), "nom": c.nom} for c in obj.categories_incluses.all()]

    def validate_montant_prevu(self, montant):
        if montant <= 0:
            raise serializers.ValidationError(
                "Le montant prévu doit être strictement positif."
            )
        return montant

    def validate(self, data):
        if "_montant_consomme_input" in data:
            raise serializers.ValidationError(
                {"montant_consomme": "Ce champ est calculé et non modifiable."}
            )
        if "_taux_consommation_input" in data:
            raise serializers.ValidationError(
                {"taux_consommation": "Ce champ est calculé et non modifiable."}
            )

        categorie = data.get("categorie", getattr(self.instance, "categorie", None))
        mois = data.get("mois", getattr(self.instance, "mois", None))

        if not (categorie and mois):
            return data

        mois_normalise = mois.replace(day=1)
        est_budget_majeur = _auto_detect_est_budget_majeur(categorie)
        data["est_budget_majeur"] = est_budget_majeur

        qs = Budget.objects.filter(categorie=categorie, mois=mois_normalise)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {"mois": "Un budget existe déjà pour cette catégorie et ce mois."}
            )

        if est_budget_majeur:
            if "categories_incluses" not in data and self.instance is None:
                data["categories_incluses"] = list(
                    categorie.sous_categories.filter(actif=True)
                )
            categories_incluses = data.get(
                "categories_incluses",
                list(self.instance.categories_incluses.all()) if self.instance else [],
            )
            if not categories_incluses:
                raise serializers.ValidationError({
                    "categories_incluses": (
                        "Un budget de catégorie majeure doit inclure au moins une sous-catégorie."
                    )
                })
            _valider_appartenance_mineures(categorie, categories_incluses)
            for mineure in categories_incluses:
                qs_conflict = Budget.objects.filter(categorie=mineure, mois=mois_normalise)
                if self.instance:
                    qs_conflict = qs_conflict.exclude(pk=self.instance.pk)
                if qs_conflict.exists():
                    raise serializers.ValidationError({
                        "categories_incluses": (
                            f"La catégorie « {mineure.nom} » possède déjà un budget propre "
                            f"ce mois-ci. Supprimez-le avant de l'inclure dans un budget majeur."
                        )
                    })
        else:
            qs_majeur = Budget.objects.filter(
                mois=mois_normalise,
                est_budget_majeur=True,
                categories_incluses=categorie,
            )
            if self.instance:
                qs_majeur = qs_majeur.exclude(pk=self.instance.pk)
            if qs_majeur.exists():
                raise serializers.ValidationError({
                    "categorie": (
                        "Cette catégorie est déjà incluse dans un budget de catégorie "
                        "majeure pour ce mois."
                    )
                })
            # Pas de mineures incluses sur un budget non majeur
            data["categories_incluses"] = []

        return data

    def create(self, validated_data):
        categories_incluses = validated_data.pop("categories_incluses", [])
        instance = super().create(validated_data)
        instance.categories_incluses.set(categories_incluses)
        return instance

    def update(self, instance, validated_data):
        categories_incluses = validated_data.pop("categories_incluses", None)
        instance = super().update(instance, validated_data)
        if categories_incluses is not None:
            instance.categories_incluses.set(categories_incluses)
        return instance

    def to_internal_value(self, data):
        errors = {}
        if "montant_consomme" in data:
            errors["montant_consomme"] = "Ce champ est calculé et non modifiable."
        if "taux_consommation" in data:
            errors["taux_consommation"] = "Ce champ est calculé et non modifiable."
        if errors:
            raise serializers.ValidationError(errors)
        return super().to_internal_value(data)

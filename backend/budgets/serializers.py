from rest_framework import serializers
from categories.models import Categorie
from .models import Budget, BudgetTemplate


def _auto_detect_est_budget_majeur(categorie):
    """Majeure = racine avec au moins une sous-catégorie active."""
    return (
        categorie.parent_id is None
        and categorie.sous_categories.filter(actif=True).exists()
    )


def _est_feuille(categorie):
    """Feuille = catégorie qui n'agrège pas d'autres catégories (non majeure)."""
    return not _auto_detect_est_budget_majeur(categorie)


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


def _categories_couvertes(obj):
    """
    Feuilles réellement couvertes par un budget/template :
    - ses categories_incluses si non vide (majeur ou thématique) ;
    - sinon sa catégorie ancre (budget simple).
    """
    inc = list(obj.categories_incluses.all())
    if inc:
        return [c.id for c in inc]
    return [obj.categorie_id] if obj.categorie_id else []


def _premier_conflit_couverture(cible_ids, existants):
    """
    Retourne (categorie_id, instance) du premier chevauchement entre les
    catégories cibles et celles déjà couvertes par un `existants`, sinon (None, None).
    """
    cible = set(cible_ids)
    for obj in existants:
        for cid in _categories_couvertes(obj):
            if cid in cible:
                return cid, obj
    return None, None


def _libelle_budget(obj):
    if getattr(obj, "categorie_id", None):
        return obj.categorie.nom
    return obj.nom or "?"


class BudgetTemplateSerializer(serializers.ModelSerializer):
    categorie_nom = serializers.SerializerMethodField()
    libelle = serializers.SerializerMethodField()
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
            "nom",
            "libelle",
            "montant_defaut",
            "est_budget_majeur",
            "categories_incluses",
            "categories_incluses_detail",
            "en_jeu",
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
        # Unicité gérée manuellement dans validate() (conditionnée à
        # categorie null/non-null) : on neutralise les validateurs
        # UniqueConstraint auto-générés par DRF, qui ignorent la condition
        # et rendraient `nom` obligatoire via UniqueTogetherValidator.
        validators = []

    def get_categorie_nom(self, obj):
        return obj.categorie.nom if obj.categorie_id else None

    def get_libelle(self, obj):
        return _libelle_budget(obj)

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
        nom = data.get("nom", getattr(self.instance, "nom", "") or "")
        incluses_fournies = "categories_incluses" in data
        categories_incluses = data.get(
            "categories_incluses",
            list(self.instance.categories_incluses.all()) if self.instance else [],
        )

        if categorie is None:
            # --- Modèle thématique ---
            nom = (nom or "").strip()
            if not nom:
                raise serializers.ValidationError(
                    {"nom": "Un modèle thématique doit avoir un nom."}
                )
            if not categories_incluses:
                raise serializers.ValidationError({
                    "categories_incluses": (
                        "Un modèle thématique doit inclure au moins une catégorie."
                    )
                })
            for cat in categories_incluses:
                if not _est_feuille(cat):
                    raise serializers.ValidationError({
                        "categories_incluses": (
                            f"« {cat.nom} » est une catégorie majeure ; "
                            f"sélectionnez plutôt ses sous-catégories."
                        )
                    })
            data["est_budget_majeur"] = False
            data["nom"] = nom
            cible_ids = [c.id for c in categories_incluses]
            champ_conflit = "categories_incluses"

            qs_nom = BudgetTemplate.objects.filter(nom=nom, categorie__isnull=True)
            if self.instance:
                qs_nom = qs_nom.exclude(pk=self.instance.pk)
            if qs_nom.exists():
                raise serializers.ValidationError(
                    {"nom": "Un modèle thématique porte déjà ce nom."}
                )
        else:
            est_budget_majeur = _auto_detect_est_budget_majeur(categorie)
            data["est_budget_majeur"] = est_budget_majeur

            qs = BudgetTemplate.objects.filter(categorie=categorie)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"categorie": "Un modèle de budget existe déjà pour cette catégorie."}
                )

            if est_budget_majeur:
                if not incluses_fournies and self.instance is None:
                    categories_incluses = list(
                        categorie.sous_categories.filter(actif=True)
                    )
                    data["categories_incluses"] = categories_incluses
                if not categories_incluses:
                    raise serializers.ValidationError({
                        "categories_incluses": (
                            "Un modèle de catégorie majeure doit inclure au moins une sous-catégorie."
                        )
                    })
                _valider_appartenance_mineures(categorie, categories_incluses)
                cible_ids = [c.id for c in categories_incluses]
                champ_conflit = "categories_incluses"
            else:
                data["categories_incluses"] = []
                cible_ids = [categorie.id]
                champ_conflit = "categorie"

        # --- Exclusivité : aucune catégorie déjà couverte par un autre modèle actif ---
        existants = (
            BudgetTemplate.objects.filter(actif=True)
            .prefetch_related("categories_incluses")
            .select_related("categorie")
        )
        if self.instance:
            existants = existants.exclude(pk=self.instance.pk)
        conflit_id, autre = _premier_conflit_couverture(cible_ids, existants)
        if conflit_id:
            nom_cat = (
                Categorie.objects.filter(pk=conflit_id)
                .values_list("nom", flat=True).first()
            )
            raise serializers.ValidationError({
                champ_conflit: (
                    f"La catégorie « {nom_cat} » est déjà couverte par le modèle "
                    f"« {_libelle_budget(autre)} »."
                )
            })

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
    categorie = serializers.PrimaryKeyRelatedField(
        queryset=Categorie.objects.all(), required=False, allow_null=True,
    )
    nom = serializers.CharField(required=False, allow_blank=True, max_length=120)
    categorie_nom = serializers.SerializerMethodField()
    libelle = serializers.SerializerMethodField()
    montant_consomme = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    taux_consommation = serializers.DecimalField(
        max_digits=6, decimal_places=2, read_only=True
    )
    montant_restant = serializers.SerializerMethodField()
    montant_prevu_effectif = serializers.SerializerMethodField()
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
            "nom",
            "libelle",
            "mois",
            "montant_prevu",
            "montant_prevu_effectif",
            "montant_consomme",
            "taux_consommation",
            "montant_restant",
            "statut_consommation",
            "_montant_consomme_input",
            "_taux_consommation_input",
            "est_budget_majeur",
            "categories_incluses",
            "categories_incluses_detail",
            "en_jeu",
            "points_alloues",
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
            "points_alloues",
            "template_id",
            "created_at",
            "updated_at",
        ]
        # Unicité (categorie, mois) et (nom, mois) gérée manuellement dans
        # validate() (conditionnée à categorie null/non-null) : on neutralise
        # les UniqueTogetherValidator auto-générés par DRF qui, sinon, rendent
        # `nom` obligatoire sur toute création de budget ancré à une catégorie.
        validators = []

    def get_categorie_nom(self, obj):
        return obj.categorie.nom if obj.categorie_id else None

    def get_libelle(self, obj):
        return _libelle_budget(obj)

    @property
    def _vp(self):
        """Valeur du point, lue une seule fois par sérialisation."""
        if not hasattr(self, "_vp_cache"):
            from .services.points import valeur_point
            self._vp_cache = valeur_point()
        return self._vp_cache

    def get_montant_prevu_effectif(self, obj):
        """Prévu de base + bonus distribué (points_alloues × valeur_point)."""
        if not obj.points_alloues:
            return obj.montant_prevu
        return obj.montant_prevu + (obj.points_alloues * self._vp)

    def get_montant_restant(self, obj):
        return self.get_montant_prevu_effectif(obj) - obj.montant_consomme

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
        nom = data.get("nom", getattr(self.instance, "nom", "") or "")

        if not mois:
            return data

        mois_normalise = mois.replace(day=1)
        incluses_fournies = "categories_incluses" in data
        categories_incluses = data.get(
            "categories_incluses",
            list(self.instance.categories_incluses.all()) if self.instance else [],
        )

        if categorie is None:
            # --- Budget thématique ---
            nom = (nom or "").strip()
            if not nom:
                raise serializers.ValidationError(
                    {"nom": "Un budget thématique doit avoir un nom."}
                )
            if not categories_incluses:
                raise serializers.ValidationError({
                    "categories_incluses": (
                        "Un budget thématique doit inclure au moins une catégorie."
                    )
                })
            for cat in categories_incluses:
                if not _est_feuille(cat):
                    raise serializers.ValidationError({
                        "categories_incluses": (
                            f"« {cat.nom} » est une catégorie majeure ; "
                            f"sélectionnez plutôt ses sous-catégories."
                        )
                    })
            data["est_budget_majeur"] = False
            data["nom"] = nom
            cible_ids = [c.id for c in categories_incluses]
            champ_conflit = "categories_incluses"

            qs_nom = Budget.objects.filter(
                nom=nom, categorie__isnull=True, mois=mois_normalise
            )
            if self.instance:
                qs_nom = qs_nom.exclude(pk=self.instance.pk)
            if qs_nom.exists():
                raise serializers.ValidationError(
                    {"nom": "Un budget thématique porte déjà ce nom ce mois-ci."}
                )
        else:
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
                if not incluses_fournies and self.instance is None:
                    categories_incluses = list(
                        categorie.sous_categories.filter(actif=True)
                    )
                    data["categories_incluses"] = categories_incluses
                if not categories_incluses:
                    raise serializers.ValidationError({
                        "categories_incluses": (
                            "Un budget de catégorie majeure doit inclure au moins une sous-catégorie."
                        )
                    })
                _valider_appartenance_mineures(categorie, categories_incluses)
                cible_ids = [c.id for c in categories_incluses]
                champ_conflit = "categories_incluses"
            else:
                data["categories_incluses"] = []
                cible_ids = [categorie.id]
                champ_conflit = "categorie"

        # --- Exclusivité générale : aucune catégorie déjà couverte ce mois ---
        existants = (
            Budget.objects.filter(mois=mois_normalise)
            .prefetch_related("categories_incluses")
            .select_related("categorie")
        )
        if self.instance:
            existants = existants.exclude(pk=self.instance.pk)
        conflit_id, autre = _premier_conflit_couverture(cible_ids, existants)
        if conflit_id:
            nom_cat = (
                Categorie.objects.filter(pk=conflit_id)
                .values_list("nom", flat=True).first()
            )
            raise serializers.ValidationError({
                champ_conflit: (
                    f"La catégorie « {nom_cat} » est déjà couverte par le budget "
                    f"« {_libelle_budget(autre)} » ce mois-ci."
                )
            })

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

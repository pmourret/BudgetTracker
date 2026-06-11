import re
import unicodedata

from rest_framework import serializers

from .models import Categorie


def _auto_code(nom, exclude_id=None):
    """Génère un code unique en slug depuis un nom."""
    slug = unicodedata.normalize("NFD", nom).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]", "", slug).upper()[:10] or "CAT"
    code = slug
    suffix = 1
    while True:
        qs = Categorie.objects.filter(code=code)
        if exclude_id:
            qs = qs.exclude(id=exclude_id)
        if not qs.exists():
            break
        code = f"{slug[:8]}-{suffix}"
        suffix += 1
    return code


class CategorieSerializer(serializers.ModelSerializer):
    niveau = serializers.IntegerField(read_only=True)
    est_racine = serializers.BooleanField(read_only=True)
    parent_nom = serializers.CharField(source="parent.nom", read_only=True)
    nb_sous_categories = serializers.SerializerMethodField()
    code = serializers.CharField(required=False, max_length=50, allow_blank=False)

    class Meta:
        model = Categorie
        fields = [
            "id",
            "code",
            "nom",
            "parent",
            "parent_nom",
            "niveau",
            "est_racine",
            "nb_sous_categories",
            "description",
            "ordre",
            "actif",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_nb_sous_categories(self, obj):
        if obj.est_racine:
            return obj.sous_categories.count()
        return 0

    def validate_parent(self, parent):
        """
        Enforce la profondeur maximale de 2 niveaux.
        Une sous-catégorie ne peut pas être parente d'une autre catégorie.
        """
        if parent is not None and parent.parent is not None:
            raise serializers.ValidationError(
                "Profondeur maximale atteinte : une sous-catégorie "
                "ne peut pas être parente d'une autre catégorie."
            )
        return parent

    def validate(self, data):
        """Vérifie qu'une catégorie racine ne devient pas sa propre parente."""
        instance = self.instance
        parent = data.get("parent", getattr(instance, "parent", None))

        if instance and parent and str(parent.id) == str(instance.id):
            raise serializers.ValidationError(
                {"parent": "Une catégorie ne peut pas être sa propre parente."}
            )
        return data

    def create(self, validated_data):
        if not validated_data.get("code"):
            validated_data["code"] = _auto_code(validated_data.get("nom", ""))
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "code" in validated_data and not validated_data["code"]:
            validated_data["code"] = _auto_code(
                validated_data.get("nom", instance.nom), exclude_id=instance.id
            )
        return super().update(instance, validated_data)
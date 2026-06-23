from rest_framework import serializers


class DashboardMetriquesSerializer(serializers.Serializer):
    solde_total = serializers.DecimalField(max_digits=14, decimal_places=2)
    depenses_mois = serializers.DecimalField(max_digits=14, decimal_places=2)
    revenus_mois = serializers.DecimalField(max_digits=14, decimal_places=2)
    epargne_nette = serializers.DecimalField(max_digits=14, decimal_places=2)
    taux_epargne = serializers.DecimalField(max_digits=6, decimal_places=1)
    fiabilite = serializers.CharField()


class DashboardSerializer(serializers.Serializer):
    """Serializer de sortie pour l'agrégat dashboard."""
    mois_courant = serializers.CharField()
    metriques = DashboardMetriquesSerializer()
    evolution_solde = serializers.ListField()
    depenses_par_categorie = serializers.ListField()
    depenses_par_jour = serializers.ListField()
    budgets = serializers.ListField()
    derniers_flux = serializers.ListField()
    alertes = serializers.ListField()
    patrimoine = serializers.DictField()


class CompteDashboardSerializer(serializers.Serializer):
    """
    Serializer de sortie pour le dashboard d'un compte unique.
    Lecture seule, fiabilité RÉELLE (agrégats du mois courant scopés au compte).
    """
    mois_courant = serializers.CharField()
    compte = serializers.DictField()
    metriques = serializers.DictField()
    depenses_par_categorie = serializers.ListField()
    top_depenses = serializers.ListField()


class PrevisionnelSerializer(serializers.Serializer):
    """
    Serializer de sortie pour le prévisionnel (phase 10-A).
    Lecture seule : chaque bloc porte 'fiabilite' et 'definition' —
    une projection n'est jamais une vérité comptable.
    """
    date_calcul = serializers.CharField()
    mois_courant = serializers.CharField()
    solde_projete = serializers.DictField()
    capacite_restante = serializers.DictField()
    trajectoire = serializers.DictField()
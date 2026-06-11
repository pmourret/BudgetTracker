from decimal import Decimal
from django.db.models import Sum


def calculer_patrimoine_total(inclure_inactifs: bool = False) -> dict:
    """
    Agrège la valorisation estimative de tous les actifs.

    Retourne un dict structuré par type d'actif et totaux globaux.

    Fiabilité : ESTIMATIVE — basée sur des valorisations manuelles.
    Fréquence : à la demande (pas de recalcul automatique).

    Ne touche JAMAIS aux soldes bancaires réels.
    """
    from patrimoine.models import Actif

    qs = Actif.objects.all()
    if not inclure_inactifs:
        qs = qs.filter(actif=True)

    # Agrégation par type
    par_type = {}
    for type_actif, libelle in _get_types_actif():
        actifs_type = qs.filter(type_actif=type_actif)
        total = (
            actifs_type.aggregate(total=Sum("valeur_actuelle"))["total"]
            or Decimal("0.00")
        )
        plus_value = _calculer_plus_value_type(actifs_type)
        par_type[type_actif] = {
            "libelle": libelle,
            "total_estime": total,
            "plus_value_latente_estimee": plus_value,
            "nb_actifs": actifs_type.count(),
        }

    # Totaux globaux
    total_global = (
        qs.aggregate(total=Sum("valeur_actuelle"))["total"]
        or Decimal("0.00")
    )
    total_acquisition = (
        qs.exclude(valeur_acquisition__isnull=True)
        .aggregate(total=Sum("valeur_acquisition"))["total"]
        or Decimal("0.00")
    )

    return {
        "total_estime": total_global,
        "plus_value_latente_globale_estimee": (
            total_global - total_acquisition
            if total_acquisition > 0
            else None
        ),
        "par_type": par_type,
        "fiabilite": "estimative",
        "avertissement": (
            "Ces valorisations sont estimatives et basées sur des "
            "saisies manuelles. Elles ne constituent pas une vérité "
            "comptable et peuvent ne pas refléter la valeur de marché réelle."
        ),
    }


def _get_types_actif():
    """Retourne les choix du modèle Actif."""
    from patrimoine.models import TypeActif
    return TypeActif.choices


def _calculer_plus_value_type(qs) -> Decimal | None:
    """
    Calcule la plus-value latente estimative pour un queryset d'actifs.
    Retourne None si aucun actif n'a de valeur d'acquisition.
    """
    qs_avec_acquisition = qs.exclude(valeur_acquisition__isnull=True)

    if not qs_avec_acquisition.exists():
        return None

    total_actuel = (
        qs_avec_acquisition.aggregate(total=Sum("valeur_actuelle"))["total"]
        or Decimal("0.00")
    )
    total_acquisition = (
        qs_avec_acquisition.aggregate(total=Sum("valeur_acquisition"))["total"]
        or Decimal("0.00")
    )
    return total_actuel - total_acquisition


def mettre_a_jour_valorisation(actif, valeur: Decimal) -> None:
    """
    Met à jour la valorisation manuelle d'un actif ET enregistre
    un point d'historique.

    Règle : la date de valorisation est toujours mise à jour
    en même temps que la valeur — pour tracer la fraîcheur.

    Fiabilité : estimative.
    """
    import datetime
    from django.db import transaction
    from patrimoine.models import HistoriqueValorisation

    if valeur < 0:
        raise ValueError(
            "La valeur d'un actif ne peut pas être négative."
        )

    aujourd_hui = datetime.date.today()

    with transaction.atomic():
        # Mise à jour de la valeur courante
        actif.valeur_actuelle = valeur
        actif.date_valorisation = aujourd_hui
        actif.save(update_fields=[
            "valeur_actuelle", "date_valorisation", "updated_at"
        ])

        # Enregistrement du point d'historique (granularité fine)
        HistoriqueValorisation.objects.create(
            actif=actif,
            valeur=valeur,
            date_valorisation=aujourd_hui,
        )

def calculer_historique_patrimoine(nb_mois: int = 12) -> dict:
    """
    Construit une série temporelle mensuelle de la valeur totale estimée
    du patrimoine sur les `nb_mois` derniers mois.

    Convention « carry-forward » : pour un mois sans nouvelle valorisation
    d'un actif, on reporte sa dernière valeur connue. Cette hypothèse
    suppose une valeur stable entre deux saisies — à afficher clairement.

    Fiabilité : ESTIMATIVE.
    Ne touche jamais aux soldes bancaires réels.
    """
    import datetime
    from dateutil.relativedelta import relativedelta
    from patrimoine.models import Actif, HistoriqueValorisation

    aujourd_hui = datetime.date.today()
    premier_mois = (aujourd_hui.replace(day=1)
                    - relativedelta(months=nb_mois - 1))

    # Liste des mois à couvrir (1er de chaque mois)
    mois_list = []
    curseur = premier_mois
    while curseur <= aujourd_hui.replace(day=1):
        mois_list.append(curseur)
        curseur = curseur + relativedelta(months=1)

    actifs = Actif.objects.filter(actif=True)

    serie = []
    for mois in mois_list:
        # Fin du mois considéré
        fin_mois = mois + relativedelta(months=1) - datetime.timedelta(days=1)
        total_mois = Decimal("0.00")

        for actif in actifs:
            # Dernière valorisation connue à la fin de ce mois
            derniere = (
                HistoriqueValorisation.objects
                .filter(actif=actif, date_valorisation__lte=fin_mois)
                .order_by("-date_valorisation", "-created_at")
                .first()
            )
            if derniere:
                total_mois += derniere.valeur

        serie.append({
            "mois": mois.isoformat(),
            "valeur_estimee": total_mois,
        })

    return {
        "serie": serie,
        "fiabilite": "estimative",
        "convention": "carry-forward",
        "avertissement": (
            "Valeurs estimatives. Pour les mois sans nouvelle valorisation, "
            "la dernière valeur connue est reportée."
        ),
    }
from decimal import Decimal
import datetime
from dateutil.relativedelta import relativedelta
from django.db.models import Sum, Q


def _mois_courant():
    from core.services.periode import mois_comptable_courant

    return mois_comptable_courant()


def calculer_dashboard(nb_mois: int = 6, mois: datetime.date = None) -> dict:
    """
    Agrège tous les indicateurs du dashboard pour un mois comptable donné.

    `mois` (libellé = 1er du mois comptable) permet de naviguer dans
    l'historique ; par défaut le mois comptable courant. Il est borné entre
    le premier mois ayant des flux (`mois_min`) et le mois courant
    (`mois_max`) : le dashboard reste un agrégat RÉEL, pas une projection.

    Tous les indicateurs sont de fiabilité RÉELLE (basés sur les flux saisis).
    Les transferts sont exclus des dépenses/revenus (règle métier 4).
    Le patrimoine estimatif est calculé séparément et ne se mélange jamais
    au solde bancaire (règle métier 10).
    """
    from comptes.models import Compte
    from flux.models import Flux
    from budgets.models import Budget
    from alertes.models import Alerte

    mois_max = _mois_courant()
    mois_min = (
        Flux.objects.order_by("mois").values_list("mois", flat=True).first()
        or mois_max
    )
    # Mois ciblé, borné à [mois_min, mois_max] (pas de navigation dans le futur)
    mois_courant = mois or mois_max
    mois_courant = max(mois_min, min(mois_courant, mois_max))

    # --- Solde total (réel) à la fin du mois sélectionné ---
    solde_total = _solde_fin_de_mois(mois_courant)

    # --- Dépenses / revenus du mois (hors transferts et ajustements) ---
    flux_mois = Flux.objects.filter(
        mois=mois_courant, est_transfert=False, est_ajustement=False
    )

    depenses = (
        flux_mois.filter(montant__lt=0).aggregate(t=Sum("montant"))["t"]
        or Decimal("0.00")
    )
    revenus = (
        flux_mois.filter(montant__gt=0).aggregate(t=Sum("montant"))["t"]
        or Decimal("0.00")
    )
    epargne_nette = revenus + depenses  # depenses est négatif
    taux_epargne = (
        (epargne_nette / revenus * 100).quantize(Decimal("0.1"))
        if revenus > 0 else Decimal("0.0")
    )

    # --- Évolution du solde (N derniers mois, se terminant au mois affiché) ---
    evolution = _calculer_evolution_solde(nb_mois, mois_fin=mois_courant)

    # --- Budgets du mois ---
    budgets = list(
        Budget.objects.filter(mois=mois_courant)
        .select_related("categorie")
        .order_by("-taux_consommation")
    )
    budgets_data = [
        {
            "id": str(b.id),
            "categorie_nom": b.categorie.nom,
            "montant_prevu": b.montant_prevu,
            "montant_consomme": b.montant_consomme,
            "taux_consommation": b.taux_consommation,
        }
        for b in budgets
    ]

    # --- Derniers flux du mois affiché (5 plus récents, hors transferts) ---
    derniers_flux = list(
        Flux.objects.filter(mois=mois_courant, est_transfert=False)
        .select_related("compte", "categorie")
        .order_by("-date_flux", "-created_at")[:5]
    )
    flux_data = [
        {
            "id": str(f.id),
            "libelle": f.libelle,
            "montant": f.montant,
            "date_flux": f.date_flux,
            "categorie_nom": f.categorie.nom if f.categorie else None,
        }
        for f in derniers_flux
    ]

    # --- Alertes non acquittées (5 plus récentes) ---
    alertes = list(
        Alerte.objects.filter(acquittee=False)
        .order_by("-created_at")[:5]
    )
    alertes_data = [
        {
            "id": str(a.id),
            "type_alerte_display": a.get_type_alerte_display(),
            "niveau": a.niveau,
            "explication": a.explication,
        }
        for a in alertes
    ]

    return {
        "mois_courant": mois_courant.isoformat(),
        "mois_min": mois_min.isoformat(),
        "mois_max": mois_max.isoformat(),
        "metriques": {
            "solde_total": solde_total,
            "depenses_mois": abs(depenses),
            "revenus_mois": revenus,
            "epargne_nette": epargne_nette,
            "taux_epargne": taux_epargne,
            "fiabilite": "reel",
        },
        "evolution_solde": evolution,
        "depenses_par_categorie": _calculer_depenses_par_categorie(mois_courant, compte_id=None),
        "depenses_par_jour": _calculer_depenses_par_jour(mois_courant),
        "budgets": budgets_data,
        "derniers_flux": flux_data,
        "alertes": alertes_data,
        "patrimoine": _calculer_bloc_patrimoine(),
    }


def _calculer_depenses_par_categorie(mois: datetime.date, compte_id=None) -> list:
    """
    Dépenses du mois regroupées par catégorie principale.
    Chaque majeure contient ses sous-catégories avec leurs montants.
    Transferts exclus. Fiabilité : réelle.

    Si `compte_id` est fourni, l'agrégation est restreinte à ce compte
    (utilisé par le dashboard par compte) ; sinon tous les comptes (dashboard global).
    """
    from flux.models import Flux

    filtres = dict(
        mois=mois,
        montant__lt=0,
        est_transfert=False,
        est_ajustement=False,
        categorie__isnull=False,
    )
    if compte_id is not None:
        filtres["compte_id"] = compte_id

    par_cat = (
        Flux.objects.filter(**filtres)
        .values(
            "categorie",
            "categorie__nom",
            "categorie__parent",
            "categorie__parent__nom",
        )
        .annotate(total=Sum("montant"))
    )

    par_majeure = {}
    for row in par_cat:
        montant_abs = abs(row["total"])
        cat_id = str(row["categorie"])
        cat_nom = row["categorie__nom"]
        parent_id = row["categorie__parent"]
        parent_nom = row["categorie__parent__nom"]

        if parent_id is None:
            maj_key, maj_nom = cat_id, cat_nom
            min_entry = None
        else:
            maj_key, maj_nom = str(parent_id), parent_nom
            min_entry = {"id": cat_id, "nom": cat_nom, "total": montant_abs}

        if maj_key not in par_majeure:
            par_majeure[maj_key] = {
                "id": maj_key,
                "nom": maj_nom,
                "total": Decimal("0.00"),
                "sous_categories": [],
            }

        par_majeure[maj_key]["total"] += montant_abs
        if min_entry:
            par_majeure[maj_key]["sous_categories"].append(min_entry)

    result = sorted(par_majeure.values(), key=lambda x: x["total"], reverse=True)
    for item in result:
        item["sous_categories"] = sorted(
            item["sous_categories"], key=lambda x: x["total"], reverse=True
        )
    return result


def _calculer_depenses_par_jour(mois: datetime.date) -> list:
    """
    Dépenses du mois ventilées par jour (heatmap calendaire).
    Transferts et ajustements exclus. Fiabilité : réelle.

    Renvoie une liste `[{"date": "YYYY-MM-DD", "total": Decimal}, ...]`
    triée par date, avec une entrée uniquement pour les jours effectivement
    dépensés (les jours vides sont reconstitués côté front via la grille
    calendaire). Les montants sont rendus en valeur absolue.
    """
    from flux.models import Flux

    par_jour = (
        Flux.objects.filter(
            mois=mois,
            montant__lt=0,
            est_transfert=False,
            est_ajustement=False,
        )
        .values("date_flux")
        .annotate(total=Sum("montant"))
    )
    jours = [
        {"date": row["date_flux"].isoformat(), "total": abs(row["total"])}
        for row in par_jour
    ]
    jours.sort(key=lambda x: x["date"])
    return jours


def _solde_fin_de_mois(mois: datetime.date) -> Decimal:
    """
    Solde théorique cumulé de tous les comptes actifs à la fin du mois
    comptable `mois` : solde_initial total + Σ flux jusqu'au dernier jour
    de la période. Fiabilité : réelle.

    Avec le mois courant et aucun flux daté au-delà de la période, ce solde
    égale `Σ solde_theorique` (cohérence avec l'état affiché des comptes).
    """
    from comptes.models import Compte
    from flux.models import Flux
    from core.services.periode import bornes_mois_comptable, jour_bascule_actif

    fin_mois = bornes_mois_comptable(mois, jour_bascule_actif())[1]
    solde_initial_total = (
        Compte.objects.filter(actif=True)
        .aggregate(t=Sum("solde_initial"))["t"]
        or Decimal("0.00")
    )
    flux_cumul = (
        Flux.objects.filter(
            compte__actif=True,
            date_flux__lte=fin_mois,
        ).aggregate(t=Sum("montant"))["t"]
        or Decimal("0.00")
    )
    return solde_initial_total + flux_cumul


def _calculer_evolution_solde(nb_mois: int, mois_fin: datetime.date = None) -> list:
    """
    Solde théorique cumulé à la fin de chaque mois sur nb_mois, se terminant
    au mois `mois_fin` (par défaut le mois comptable courant).

    Fiabilité : réelle.
    """
    from core.services.periode import mois_comptable_courant

    mois_fin = mois_fin or mois_comptable_courant()
    premier_mois = mois_fin - relativedelta(months=nb_mois - 1)

    serie = []
    curseur = premier_mois
    while curseur <= mois_fin:
        serie.append({
            "mois": curseur.isoformat(),
            "solde": _solde_fin_de_mois(curseur),
        })
        curseur = curseur + relativedelta(months=1)

    return serie


def _calculer_bloc_patrimoine() -> dict:
    """
    Bloc patrimoine ESTIMATIF, séparé du solde bancaire.
    Fiabilité : estimative. Ne se mélange jamais au solde réel.
    """
    from patrimoine.services.valorisation import calculer_patrimoine_total

    total = calculer_patrimoine_total()
    return {
        "total_estime": total["total_estime"],
        "fiabilite": "estimative",
    }
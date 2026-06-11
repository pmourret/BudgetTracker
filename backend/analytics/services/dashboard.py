from decimal import Decimal
import datetime
from dateutil.relativedelta import relativedelta
from django.db.models import Sum, Q


def _mois_courant():
    return datetime.date.today().replace(day=1)


def calculer_dashboard(nb_mois: int = 6) -> dict:
    """
    Agrège tous les indicateurs du dashboard.

    Tous les indicateurs sont de fiabilité RÉELLE (basés sur les flux saisis).
    Les transferts sont exclus des dépenses/revenus (règle métier 4).
    Le patrimoine estimatif est calculé séparément et ne se mélange jamais
    au solde bancaire (règle métier 10).
    """
    from comptes.models import Compte
    from flux.models import Flux
    from budgets.models import Budget
    from alertes.models import Alerte

    mois_courant = _mois_courant()

    # --- Solde total (réel) ---
    solde_total = (
        Compte.objects.filter(actif=True)
        .aggregate(total=Sum("solde_theorique"))["total"]
        or Decimal("0.00")
    )

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

    # --- Évolution du solde (N derniers mois) ---
    evolution = _calculer_evolution_solde(nb_mois)

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

    # --- Derniers flux (5 plus récents, hors transferts) ---
    derniers_flux = list(
        Flux.objects.filter(est_transfert=False)
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
        "metriques": {
            "solde_total": solde_total,
            "depenses_mois": abs(depenses),
            "revenus_mois": revenus,
            "epargne_nette": epargne_nette,
            "taux_epargne": taux_epargne,
            "fiabilite": "reel",
        },
        "evolution_solde": evolution,
        "depenses_par_categorie": _calculer_depenses_par_categorie(mois_courant),
        "budgets": budgets_data,
        "derniers_flux": flux_data,
        "alertes": alertes_data,
        "patrimoine": _calculer_bloc_patrimoine(),
    }


def _calculer_depenses_par_categorie(mois: datetime.date) -> list:
    """
    Dépenses du mois regroupées par catégorie principale.
    Chaque majeure contient ses sous-catégories avec leurs montants.
    Transferts exclus. Fiabilité : réelle.
    """
    from flux.models import Flux

    par_cat = (
        Flux.objects.filter(
            mois=mois,
            montant__lt=0,
            est_transfert=False,
            est_ajustement=False,
            categorie__isnull=False,
        )
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


def _calculer_evolution_solde(nb_mois: int) -> list:
    """
    Solde théorique cumulé à la fin de chaque mois sur nb_mois.

    Pour chaque mois : solde_initial de tous les comptes
    + somme de tous les flux jusqu'à la fin de ce mois.

    Fiabilité : réelle.
    """
    from comptes.models import Compte
    from flux.models import Flux

    aujourd_hui = datetime.date.today()
    premier_mois = aujourd_hui.replace(day=1) - relativedelta(months=nb_mois - 1)

    solde_initial_total = (
        Compte.objects.filter(actif=True)
        .aggregate(t=Sum("solde_initial"))["t"]
        or Decimal("0.00")
    )

    serie = []
    curseur = premier_mois
    while curseur <= aujourd_hui.replace(day=1):
        fin_mois = curseur + relativedelta(months=1) - datetime.timedelta(days=1)
        flux_cumul = (
            Flux.objects.filter(
                compte__actif=True,
                date_flux__lte=fin_mois,
            ).aggregate(t=Sum("montant"))["t"]
            or Decimal("0.00")
        )
        serie.append({
            "mois": curseur.isoformat(),
            "solde": solde_initial_total + flux_cumul,
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
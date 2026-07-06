"""
Mécanique B — Système de points « façon JDR » (spec CLAUDE.md §6 Phase 12-B).

Lecture seule (socle 12-B-1) : lit les budgets `en_jeu` et le paramètre
`valeur_point`, ne modifie rien, ne génère aucune alerte. Une projection
n'est jamais une vérité comptable (le mois en cours est étiqueté « projeté »).

Points d'une enveloppe (à la clôture du mois comptable) :
    ecart = prevu_effectif - montant_consomme
    points = signe(ecart) × ⌈ |ecart| / valeur_point ⌉   (arrondi magnitude vers le haut)

Réserve disponible = Σ(deltas des mois clôturés) − Σ(points alloués).
Calcul à la volée, déterministe (aucune table ledger).
"""

from decimal import Decimal, ROUND_CEILING

from dateutil.relativedelta import relativedelta

from core.services.periode import mois_comptable_courant


def valeur_point() -> Decimal:
    """Valeur d'un point en € (paramètre administrable, défaut 10)."""
    from referentiels.models import ParametresBudget
    val = ParametresBudget.get_solo().valeur_point
    return val if isinstance(val, Decimal) else Decimal(str(val))


def prevu_effectif(budget, vp: Decimal) -> Decimal:
    """Prévu de base + bonus distribué (points_alloues × valeur_point)."""
    return budget.montant_prevu + (budget.points_alloues * vp)


def points_enveloppe(budget, vp: Decimal) -> int:
    """
    Points générés par une enveloppe à la clôture.
    Positif si sous-consommée, négatif si dépassée. Arrondi magnitude vers le haut.
    """
    ecart = prevu_effectif(budget, vp) - budget.montant_consomme
    if ecart == 0:
        return 0
    magnitude = int((abs(ecart) / vp).to_integral_value(rounding=ROUND_CEILING))
    return magnitude if ecart > 0 else -magnitude


def _deltas_par_mois(vp: Decimal) -> dict:
    """
    {mois (1er du mois comptable): delta de points} pour chaque mois ayant
    au moins une enveloppe en jeu.
    """
    from budgets.models import Budget

    deltas = {}
    budgets = Budget.objects.filter(en_jeu=True).only(
        "mois", "montant_prevu", "montant_consomme", "points_alloues"
    )
    for budget in budgets:
        deltas[budget.mois] = deltas.get(budget.mois, 0) + points_enveloppe(budget, vp)
    return deltas


def delta_mois(mois, vp: Decimal = None) -> int:
    """Delta de points d'un mois donné (Σ des enveloppes en jeu de ce mois)."""
    from budgets.models import Budget

    if vp is None:
        vp = valeur_point()
    return sum(
        points_enveloppe(b, vp)
        for b in Budget.objects.filter(mois=mois, en_jeu=True).only(
            "montant_prevu", "montant_consomme", "points_alloues"
        )
    )


def _total_points_alloues() -> int:
    """Somme de tous les points distribués (débités de la réserve)."""
    from django.db.models import Sum
    from budgets.models import Budget

    return (
        Budget.objects.filter(en_jeu=True).aggregate(t=Sum("points_alloues"))["t"] or 0
    )


def solde_disponible(aujourd_hui=None, vp: Decimal = None) -> int:
    """
    Réserve disponible = Σ(deltas des mois clôturés) − Σ(points alloués).
    Mois clôturé = mois comptable strictement antérieur au mois courant.
    """
    if vp is None:
        vp = valeur_point()
    courant = mois_comptable_courant(aujourd_hui)
    deltas = _deltas_par_mois(vp)
    clotures = sum(d for mois, d in deltas.items() if mois < courant)
    return clotures - _total_points_alloues()


class AllocationInvalide(ValueError):
    """Erreur métier d'allocation de points (à traduire en 400 côté API)."""


def allouer(budget, points: int, aujourd_hui=None):
    """
    Distribue `points` de la réserve vers une enveloppe (mécanique B, 12-B-2).

    Règles :
    - l'enveloppe doit être « en jeu » et appartenir au mois comptable courant ;
    - `points` entier ≥ 0 (0 = tout rendre à la réserve) ;
    - plafonné à la réserve disponible : on ne distribue que des points possédés.

    L'allocation gonfle le prévu effectif (montant_prevu + points × valeur_point)
    et se déduit de la réserve disponible. Recalcule la consommation (le taux
    baisse d'autant). Renvoie le budget mis à jour.
    """
    from .consommation import calculer_consommation

    if not budget.en_jeu:
        raise AllocationInvalide("Cette enveloppe n'est pas « en jeu ».")

    courant = mois_comptable_courant(aujourd_hui)
    if budget.mois != courant:
        raise AllocationInvalide(
            "On ne distribue des points que sur les enveloppes du mois en cours."
        )

    try:
        points = int(points)
    except (TypeError, ValueError):
        raise AllocationInvalide("Le nombre de points doit être un entier.")
    if points < 0:
        raise AllocationInvalide("Le nombre de points doit être positif ou nul.")

    vp = valeur_point()
    dispo = solde_disponible(aujourd_hui=aujourd_hui, vp=vp)
    # Réserve mobilisable pour CETTE enveloppe = disponible + ce qu'elle a déjà
    # (rendre son allocation courante libère d'autant).
    max_allouable = dispo + budget.points_alloues
    if points > max_allouable:
        raise AllocationInvalide(
            f"Réserve insuffisante : {max_allouable} point(s) mobilisable(s) "
            f"pour cette enveloppe."
        )

    budget.points_alloues = points
    budget.save(update_fields=["points_alloues", "updated_at"])
    calculer_consommation(budget)
    return budget


def calculer_tableau_points(nb_mois: int = 6, aujourd_hui=None) -> dict:
    """
    Tableau de bord des points (socle 12-B-1, lecture seule).

    Retourne : valeur_point, réserve disponible (points + €), historique mensuel
    (delta + cumul + drapeau provisoire), enveloppes en jeu du mois courant avec
    leurs points provisoires.
    """
    vp = valeur_point()
    courant = mois_comptable_courant(aujourd_hui)
    deltas = _deltas_par_mois(vp)

    # --- Historique : fenêtre des nb_mois derniers mois jusqu'au mois courant ---
    labels = [courant - relativedelta(months=i) for i in range(nb_mois - 1, -1, -1)]
    debut = labels[0]

    # Cumul vrai : on part de la somme des deltas AVANT la fenêtre.
    cumul = sum(d for mois, d in deltas.items() if mois < debut)
    historique = []
    for label in labels:
        delta = deltas.get(label, 0)
        cumul += delta
        provisoire = label >= courant
        historique.append({
            "mois": label,
            "delta": delta,
            "cumul": cumul,
            "provisoire": provisoire,
            "fiabilite": "faible" if provisoire else "elevee",
        })

    disponible = solde_disponible(aujourd_hui=aujourd_hui, vp=vp)

    # --- Enveloppes en jeu du mois courant (points provisoires) ---
    from budgets.models import Budget

    enveloppes = []
    budgets_courant = (
        Budget.objects.filter(mois=courant, en_jeu=True)
        .select_related("categorie")
        .order_by("montant_prevu")
    )
    for b in budgets_courant:
        libelle = b.categorie.nom if b.categorie_id else b.nom
        enveloppes.append({
            "id": str(b.id),
            "libelle": libelle,
            "montant_prevu": b.montant_prevu,
            "prevu_effectif": prevu_effectif(b, vp),
            "montant_consomme": b.montant_consomme,
            "points": points_enveloppe(b, vp),
        })

    return {
        "valeur_point": vp,
        "solde_disponible": disponible,
        "solde_disponible_euros": (disponible * vp).quantize(Decimal("0.01")),
        "mois_courant": courant,
        "delta_courant_provisoire": deltas.get(courant, 0),
        "historique": historique,
        "enveloppes_courantes": enveloppes,
        "fiabilite_mois_courant": "faible",
        "definition": (
            "Points de discipline budgétaire (mécanique B). Une enveloppe « en jeu » "
            "rapporte des points si elle n'est pas dépassée, en fait perdre sinon "
            "(1 point = valeur_point €, arrondi à l'entier supérieur). Le mois en cours "
            "est projeté (non figé) ; la réserve disponible ne compte que les mois clôturés."
        ),
    }

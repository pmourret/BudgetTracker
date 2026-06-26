"""
Découpage en mois comptables — point unique de vérité.

Le « mois comptable » d'un foyer ne commence pas forcément le 1er
calendaire : il peut démarrer au jour de perception du salaire (paramètre
administrable `jour_debut_mois_comptable`, règle métier 1 — jamais de
seuil codé en dur). Toutes les agrégations mensuelles (flux, budgets,
dashboard, prévisionnel) reposent sur ce découpage.

Convention retenue (arbitrage du foyer validé) : une période qui démarre
en fin de mois calendaire porte le libellé du mois qu'elle *finance*.
Ex. avec un jour de bascule au 25, la période 25 juin → 24 juillet est le
mois comptable « juillet » (libellé 2026-07-01).

Les fonctions de calcul sont PURES (le jour de bascule est injecté) pour
des tests déterministes ; `jour_bascule_actif()` lit le paramètre
administrable, `mois_comptable_courant()` combine les deux.
"""
import datetime

from dateutil.relativedelta import relativedelta

# Le jour de bascule est borné à 28 (présent dans tous les mois, février
# compris) pour que `.replace(day=jour_bascule)` soit toujours valide.
JOUR_BASCULE_MIN = 1
JOUR_BASCULE_MAX = 28


def mois_comptable(d: datetime.date, jour_bascule: int) -> datetime.date:
    """
    Libellé (1er du mois) du mois comptable auquel appartient la date `d`.

    - jour_bascule <= 1 : mois calendaire pur (comportement par défaut,
      rétro-compatible).
    - jour_bascule > 1  : une date dont le jour est >= jour_bascule bascule
      sur le mois suivant (elle ouvre la période qui finance ce mois).
    """
    if jour_bascule <= 1 or d.day < jour_bascule:
        return d.replace(day=1)
    return d.replace(day=1) + relativedelta(months=1)


def bornes_mois_comptable(label: datetime.date, jour_bascule: int):
    """
    Premier et dernier jour (inclus) de la période comptable `label`
    (label = 1er du mois renvoyé par `mois_comptable`).

        jour_bascule <= 1 : [1er, dernier jour calendaire du mois]
        jour_bascule > 1  : [jour_bascule du mois précédent,
                             jour_bascule du mois du label − 1 jour]
    """
    if jour_bascule <= 1:
        debut = label
        fin = label + relativedelta(months=1) - datetime.timedelta(days=1)
    else:
        debut = (label - relativedelta(months=1)).replace(day=jour_bascule)
        fin = label.replace(day=jour_bascule) - datetime.timedelta(days=1)
    return debut, fin


def jour_bascule_actif() -> int:
    """
    Valeur courante du paramètre administrable `jour_debut_mois_comptable`.
    Import local du modèle : évite tout import circulaire (règle d'archi).
    """
    from referentiels.models import ParametresBudget

    return ParametresBudget.get_solo().jour_debut_mois_comptable


def mois_comptable_courant(aujourd_hui: datetime.date = None) -> datetime.date:
    """Libellé du mois comptable en cours (selon le paramètre actif)."""
    aujourd_hui = aujourd_hui or datetime.date.today()
    return mois_comptable(aujourd_hui, jour_bascule_actif())

"""
Mise en forme française des phrases d'alerte.

Une alerte est **lue par un humain**, pas par une machine : elle doit s'écrire
comme le reste de l'interface — `5 636,49 €`, `juillet 2026`, `93,21 %`.
Interpoler un `Decimal` ou un `date` directement dans une f-string produit la
forme Python (`5636.49`, `2026-07-18`, `July 2026`), qui a l'air d'un message
d'erreur. C'est exactement l'inverse de l'effet recherché par la règle métier 13
(« pas d'alertes culpabilisantes »).

Le formatage se fait **à la source**, au moment où la phrase est assemblée : le
texte est ensuite figé en base, et le frontend ne fait que l'afficher. Le
corriger côté React serait le corriger deux fois.

*(D02 de la revue UI/UX du 2026-08-20.)*
"""

from django.utils.formats import date_format, number_format


def euros(valeur) -> str:
    """`Decimal("5636.49")` → `5 636,49 €` — espace insécable des milliers."""
    if valeur is None:
        return "—"
    return f"{number_format(valeur, decimal_pos=2, force_grouping=True)} €"


def pourcent(valeur) -> str:
    """`Decimal("93.21")` → `93,21 %` — espace insécable avant le signe."""
    if valeur is None:
        return "—"
    return f"{number_format(valeur, decimal_pos=2, force_grouping=True)} %"


def mois_annee(valeur) -> str:
    """`date(2026, 7, 1)` → `juillet 2026`."""
    if valeur is None:
        return "—"
    return date_format(valeur, "F Y", use_l10n=True)


def date_courte(valeur) -> str:
    """`date(2026, 7, 18)` → `18 juillet 2026`."""
    if valeur is None:
        return "—"
    return date_format(valeur, "j F Y", use_l10n=True)

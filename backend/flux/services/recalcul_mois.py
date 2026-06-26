"""
Remappage du champ `mois` (mois comptable) de tous les flux.

À déclencher après un changement du paramètre `jour_debut_mois_comptable`
(via la commande `recalculer_mois` ou automatiquement à la sauvegarde du
paramètre). Re-sauvegarde chaque flux : `Flux._calculer_mois()` recalcule
le mois, puis les signaux recalculent soldes et consommations de budgets.

Idempotent : sans changement de paramètre (notamment jour = 1), aucun
flux n'est remappé.
"""
from django.db import transaction


@transaction.atomic
def recalculer_mois_flux() -> dict:
    """Remappe le `mois` de tous les flux ; renvoie {total, modifies}."""
    from flux.models import Flux

    total = 0
    modifies = 0
    for flux in Flux.objects.all().iterator():
        ancien = flux.mois
        flux.save()  # recalcule mois + déclenche les signaux (solde, budgets)
        total += 1
        if flux.mois != ancien:
            modifies += 1
    return {"total": total, "modifies": modifies}

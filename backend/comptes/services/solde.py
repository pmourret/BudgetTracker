from decimal import Decimal
from django.db import transaction
from django.db.models import Sum


def calculer_solde(compte) -> None:
    """
    Recalcule solde_theorique et ecart_solde pour un compte donné.

    Règles :
        solde_theorique = solde_initial + Σ(montant des flux non supprimés)
        ecart_solde     = solde_reel - solde_theorique

    Appelé par signal après chaque CREATE / UPDATE / DELETE de Flux.
    Atomique : les deux champs sont mis à jour ensemble ou pas du tout.
    """
    # Import ici pour éviter la circularité au chargement des apps
    # mais on l'expose via une fonction injectable pour les tests
    from flux.models import Flux as FluxModel
    _calculer_solde_avec_model(compte, FluxModel)


def _calculer_solde_avec_model(compte, FluxModel) -> None:
    """
    Logique pure — séparée pour être testable sans dépendance à Flux.

    solde_theorique = solde_initial + Σ(tous les flux)
    solde_reel      = solde_initial + Σ(flux dont statut.est_definitif=True)
    ecart_solde     = solde_reel - solde_theorique  (= -Σ flux prévisionnels)
    """
    with transaction.atomic():
        total_flux = (
            FluxModel.objects
            .filter(compte=compte)
            .aggregate(total=Sum("montant"))
            ["total"]
        ) or Decimal("0.00")

        total_flux_definitifs = (
            FluxModel.objects
            .filter(compte=compte, statut__est_definitif=True)
            .aggregate(total=Sum("montant"))
            ["total"]
        ) or Decimal("0.00")

        compte.solde_theorique = compte.solde_initial + total_flux
        compte.solde_reel = compte.solde_initial + total_flux_definitifs
        compte.ecart_solde = compte.solde_reel - compte.solde_theorique

        compte.save(update_fields=["solde_theorique", "solde_reel", "ecart_solde", "updated_at"])
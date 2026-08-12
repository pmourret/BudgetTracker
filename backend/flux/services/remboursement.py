"""
Remboursement d'un flux — création d'un contre-flux recette.

Mécanisme validé (arbitrage foyer) : un remboursement reçu SUR LE COMPTE est
matérialisé par un vrai flux recette lié à la dépense d'origine (FK
`flux_rembourse`), et non par un simple drapeau. Le foyer fait du rapprochement
bancaire : la banque montre le débit d'origine ET le crédit de remboursement ;
le contre-flux permet aux deux lignes de se rapprocher naturellement (§ phase 14).

Analytics inchangé : même compte, même catégorie des deux côtés → le net par
catégorie est correct automatiquement.
"""
from decimal import Decimal


class RemboursementInvalide(Exception):
    """Remboursement impossible sur ce flux (pas une dépense, montant hors reste…)."""


def montant_deja_rembourse(flux):
    """
    Σ des remboursements (recettes liées) non supprimés d'une dépense.
    Positif (les remboursements sont des recettes à montant > 0).
    """
    from django.db.models import Sum

    total = flux.remboursements.aggregate(s=Sum("montant"))["s"]
    return total or Decimal("0")


def reste_a_rembourser(flux):
    """Part de la dépense pas encore remboursée : |montant| − Σ remboursements."""
    return abs(flux.montant) - montant_deja_rembourse(flux)


def rembourser_flux(flux, montant, date, libelle=None):
    """
    Crée le contre-flux recette qui rembourse (tout ou partie de) `flux`.

    - `flux` doit être une **dépense** (montant < 0), ni transfert ni ajustement.
    - `montant` > 0 et ≤ reste à rembourser (empêche le sur-remboursement).
    - Le contre-flux : recette (type_flux CREDIT), statut définitif, même compte,
      même catégorie, même devise, `flux_rembourse=flux`. Libellé auto
      « Remboursement — <libellé d'origine> » si absent.

    Atomique. Le signal post_save recalcule le solde du compte.
    Lève RemboursementInvalide si les conditions ne sont pas réunies.
    """
    from django.db import transaction

    from referentiels.models import StatutFlux, TypeFlux

    if flux.est_transfert:
        raise RemboursementInvalide(
            "Un transfert interne ne se rembourse pas. Annulez-le via /transferts/."
        )
    if flux.est_ajustement:
        raise RemboursementInvalide(
            "Un flux d'ajustement ne se rembourse pas."
        )
    if flux.montant >= 0:
        raise RemboursementInvalide(
            "Seule une dépense (montant négatif) peut être remboursée."
        )

    montant = Decimal(str(montant))
    if montant <= 0:
        raise RemboursementInvalide("Le montant du remboursement doit être positif.")

    reste = reste_a_rembourser(flux)
    if montant > reste:
        raise RemboursementInvalide(
            f"Le montant dépasse le reste à rembourser ({reste} €)."
        )

    type_flux = TypeFlux.objects.filter(code="CREDIT").first()
    if type_flux is None:
        raise RemboursementInvalide("Référentiel TypeFlux « CREDIT » manquant.")

    statut = StatutFlux.objects.filter(est_definitif=True).first()
    if statut is None:
        raise RemboursementInvalide("Aucun statut définitif configuré.")

    libelle_final = (libelle or f"Remboursement — {flux.libelle or 'dépense'}")[:255]

    with transaction.atomic():
        contre_flux = flux.__class__.objects.create(
            compte=flux.compte,
            categorie=flux.categorie,
            type_flux=type_flux,
            statut=statut,
            devise=flux.devise,
            montant=montant,
            date_flux=date,
            libelle=libelle_final,
            flux_rembourse=flux,
        )

    return contre_flux

from decimal import Decimal
from django.db import transaction


def creer_transfert(
    compte_source,
    compte_destination,
    montant: Decimal,
    date_flux,
    type_flux_debit,
    type_flux_credit,
    statut,
    devise,
    libelle: str = "",
    notes: str = "",
):
    """
    Crée un transfert interne entre deux comptes de façon atomique.

    - Crée le flux débit (négatif) sur le compte source.
    - Crée le flux crédit (positif) sur le compte destination.
    - Crée le Transfert liant les deux flux.
    - Les signals déclenchent le recalcul des soldes des deux comptes.

    Raises :
        ValueError : si source == destination ou montant <= 0.
    """
    from flux.models import Flux
    from transferts.models import Transfert

    if compte_source == compte_destination:
        raise ValueError("Le compte source et le compte destination doivent être différents.")

    if montant <= Decimal("0"):
        raise ValueError("Le montant d'un transfert doit être strictement positif.")

    with transaction.atomic():
        flux_debit = Flux.objects.create(
            compte=compte_source,
            type_flux=type_flux_debit,
            statut=statut,
            devise=devise,
            montant=-abs(montant),
            date_flux=date_flux,
            est_transfert=True,
            libelle=libelle or f"Transfert vers {compte_destination.nom}",
            notes=notes,
        )

        flux_credit = Flux.objects.create(
            compte=compte_destination,
            type_flux=type_flux_credit,
            statut=statut,
            devise=devise,
            montant=abs(montant),
            date_flux=date_flux,
            est_transfert=True,
            libelle=libelle or f"Transfert depuis {compte_source.nom}",
            notes=notes,
        )

        transfert = Transfert.objects.create(
            flux_debit=flux_debit,
            flux_credit=flux_credit,
            montant=montant,
            notes=notes,
        )

    return transfert
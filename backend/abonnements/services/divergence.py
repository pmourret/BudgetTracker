from decimal import Decimal


def calculer_divergence_pct(montant_attendu: Decimal, montant_reel: Decimal) -> Decimal:
    """
    Calcule l'écart en pourcentage entre le montant attendu et le montant réel.

    Formule : abs((montant_reel - montant_attendu) / montant_attendu) * 100

    Retourne 0 si montant_attendu = 0 (pas de division par zéro).
    Fiabilité : réel (basé sur les flux saisis).
    """
    if montant_attendu == 0:
        return Decimal("0.00")

    divergence = abs(
        (montant_reel - montant_attendu) / montant_attendu * 100
    ).quantize(Decimal("0.01"))

    return divergence


def verifier_divergence(abonnement, montant_reel: Decimal) -> dict:
    """
    Vérifie si le montant réel d'un flux diverge du montant attendu
    au-delà du seuil configuré sur l'abonnement.

    Retourne un dict :
    {
        "divergence_pct": Decimal,
        "en_divergence": bool,
        "montant_attendu": Decimal,
        "montant_reel": Decimal,
        "seuil_pct": Decimal,
    }

    Fiabilité : réel.
    """
    divergence_pct = calculer_divergence_pct(
        abonnement.montant_attendu, montant_reel
    )
    return {
        "divergence_pct": divergence_pct,
        "en_divergence": divergence_pct > abonnement.seuil_divergence_pct,
        "montant_attendu": abonnement.montant_attendu,
        "montant_reel": montant_reel,
        "seuil_pct": abonnement.seuil_divergence_pct,
    }


def mettre_a_jour_derniere_occurrence(abonnement, date_flux) -> None:
    """
    Met à jour derniere_occurrence si date_flux est plus récente.
    Appelé quand un flux est rattaché à un abonnement.
    """
    from django.db import transaction

    with transaction.atomic():
        if (
            abonnement.derniere_occurrence is None
            or date_flux > abonnement.derniere_occurrence
        ):
            abonnement.derniere_occurrence = date_flux
            abonnement.save(update_fields=["derniere_occurrence", "updated_at"])
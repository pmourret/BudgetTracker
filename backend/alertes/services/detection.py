from decimal import Decimal
from alertes.models import Alerte, TypeAlerte, NiveauAlerte


# ---------------------------------------------------------------------------
# Détection budget
# ---------------------------------------------------------------------------

def detecter_alertes_budget(budget) -> list[Alerte]:
    """
    Génère des alertes si le taux de consommation du budget
    dépasse les seuils d'alerte ou de dépassement.

    Seuils :
    - >= 100% → BUDGET_DEPASSE / CRITIQUE
    - >= 80%  → BUDGET_ALERTE / AVERTISSEMENT

    Une alerte non acquittée du même type sur le même budget
    n'est pas recréée (dédoublonnage).

    Fiabilité : réel (basé sur les flux saisis).
    """
    alertes_creees = []

    if budget.taux_consommation >= 100:
        type_a = TypeAlerte.BUDGET_DEPASSE
        niveau = NiveauAlerte.CRITIQUE
        explication = (
            f"Le budget '{budget.categorie.nom}' pour {budget.mois:%B %Y} "
            f"est dépassé : {budget.montant_consomme} € consommés "
            f"sur {budget.montant_prevu} € prévus "
            f"({budget.taux_consommation} %)."
        )
    elif budget.taux_consommation >= 80:
        type_a = TypeAlerte.BUDGET_ALERTE
        niveau = NiveauAlerte.AVERTISSEMENT
        explication = (
            f"Le budget '{budget.categorie.nom}' pour {budget.mois:%B %Y} "
            f"atteint {budget.taux_consommation} % de consommation "
            f"({budget.montant_consomme} € sur {budget.montant_prevu} €)."
        )
    else:
        return alertes_creees

    # Dédoublonnage — pas de doublon si alerte identique non acquittée
    existe = Alerte.objects.filter(
        type_alerte=type_a,
        budget=budget,
        acquittee=False,
    ).exists()

    if not existe:
        alerte = Alerte.objects.create(
            type_alerte=type_a,
            niveau=niveau,
            budget=budget,
            explication=explication,
            valeur_constatee=budget.taux_consommation,
            valeur_seuil=Decimal("100.00") if type_a == TypeAlerte.BUDGET_DEPASSE else Decimal("80.00"),
        )
        alertes_creees.append(alerte)

    return alertes_creees


# ---------------------------------------------------------------------------
# Détection solde bas
# ---------------------------------------------------------------------------

def detecter_alerte_solde_bas(compte, seuil: Decimal) -> Alerte | None:
    """
    Génère une alerte si le solde théorique du compte
    est inférieur au seuil fourni.

    Le seuil est passé en paramètre — jamais codé en dur.
    Fiabilité : réel (basé sur solde_theorique calculé).
    """
    if compte.solde_theorique >= seuil:
        return None

    existe = Alerte.objects.filter(
        type_alerte=TypeAlerte.SOLDE_BAS,
        compte=compte,
        acquittee=False,
    ).exists()

    if existe:
        return None

    return Alerte.objects.create(
        type_alerte=TypeAlerte.SOLDE_BAS,
        niveau=NiveauAlerte.AVERTISSEMENT,
        compte=compte,
        explication=(
            f"Le solde théorique du compte '{compte.nom}' "
            f"({compte.solde_theorique} €) "
            f"est inférieur au seuil configuré ({seuil} €)."
        ),
        valeur_constatee=compte.solde_theorique,
        valeur_seuil=seuil,
    )


# ---------------------------------------------------------------------------
# Détection abonnement en retard
# ---------------------------------------------------------------------------

def detecter_alerte_abonnement_en_retard(abonnement) -> Alerte | None:
    """
    Génère une alerte si l'abonnement est en retard
    (aucun flux saisi depuis plus d'un cycle).

    Fiabilité : estimative (dépend de la saisie manuelle).
    """
    if not abonnement.est_en_retard:
        return None

    existe = Alerte.objects.filter(
        type_alerte=TypeAlerte.ABONNEMENT_EN_RETARD,
        abonnement=abonnement,
        acquittee=False,
    ).exists()

    if existe:
        return None

    return Alerte.objects.create(
        type_alerte=TypeAlerte.ABONNEMENT_EN_RETARD,
        niveau=NiveauAlerte.AVERTISSEMENT,
        abonnement=abonnement,
        explication=(
            f"L'abonnement '{abonnement.nom}' n'a pas été constaté "
            f"depuis plus d'un cycle ({abonnement.frequence.libelle}). "
            f"Dernière occurrence : {abonnement.derniere_occurrence}."
        ),
        valeur_constatee=None,
        valeur_seuil=None,
    )


# ---------------------------------------------------------------------------
# Détection divergence abonnement
# ---------------------------------------------------------------------------

def detecter_alerte_divergence_abonnement(
    abonnement, montant_reel: Decimal
) -> Alerte | None:
    """
    Génère une alerte si le montant réel d'un flux rattaché
    à un abonnement dépasse le seuil de divergence configuré.

    Fiabilité : réel.
    """
    from abonnements.services import verifier_divergence

    result = verifier_divergence(abonnement, montant_reel)

    if not result["en_divergence"]:
        return None

    existe = Alerte.objects.filter(
        type_alerte=TypeAlerte.ABONNEMENT_DIVERGENCE,
        abonnement=abonnement,
        acquittee=False,
    ).exists()

    if existe:
        return None

    return Alerte.objects.create(
        type_alerte=TypeAlerte.ABONNEMENT_DIVERGENCE,
        niveau=NiveauAlerte.AVERTISSEMENT,
        abonnement=abonnement,
        explication=(
            f"Le montant constaté pour l'abonnement '{abonnement.nom}' "
            f"({montant_reel} €) s'écarte de {result['divergence_pct']} % "
            f"du montant attendu ({abonnement.montant_attendu} €). "
            f"Seuil configuré : {abonnement.seuil_divergence_pct} %."
        ),
        valeur_constatee=result["divergence_pct"],
        valeur_seuil=abonnement.seuil_divergence_pct,
    )


# ---------------------------------------------------------------------------
# Détection écart de solde
# ---------------------------------------------------------------------------

def detecter_alerte_ecart_solde(compte, seuil: Decimal) -> Alerte | None:
    """
    Génère une alerte si l'écart entre solde réel et solde théorique
    dépasse le seuil fourni (en valeur absolue).

    Fiabilité : réel.
    """
    if abs(compte.ecart_solde) <= seuil:
        return None

    existe = Alerte.objects.filter(
        type_alerte=TypeAlerte.ECART_SOLDE,
        compte=compte,
        acquittee=False,
    ).exists()

    if existe:
        return None

    return Alerte.objects.create(
        type_alerte=TypeAlerte.ECART_SOLDE,
        niveau=NiveauAlerte.AVERTISSEMENT,
        compte=compte,
        explication=(
            f"Un écart de {compte.ecart_solde} € a été détecté "
            f"sur le compte '{compte.nom}' "
            f"(solde réel : {compte.solde_reel} €, "
            f"solde théorique : {compte.solde_theorique} €). "
            f"Seuil configuré : {seuil} €."
        ),
        valeur_constatee=abs(compte.ecart_solde),
        valeur_seuil=seuil,
    )

# ---------------------------------------------------------------------------
# Détection rappel de valorisation patrimoniale
# ---------------------------------------------------------------------------

def detecter_alerte_valorisation_a_faire(actif) -> "Alerte | None":
    """
    Génère une alerte si un actif entre dans sa fenêtre de rappel
    de re-valorisation (échéance - rappel_jours_avant <= aujourd'hui).

    Le seuil vient de la fréquence + rappel_jours_avant configurés
    sur l'actif — jamais codé en dur.

    Fiabilité : estimative (dépend de la saisie manuelle des valorisations).
    """
    if not actif.actif or not actif.valorisation_a_faire:
        return None

    existe = Alerte.objects.filter(
        type_alerte=TypeAlerte.VALORISATION_A_FAIRE,
        actif=actif,
        acquittee=False,
    ).exists()

    if existe:
        return None

    prochaine = actif.date_prochaine_valorisation

    return Alerte.objects.create(
        type_alerte=TypeAlerte.VALORISATION_A_FAIRE,
        niveau=NiveauAlerte.INFO,
        actif=actif,
        explication=(
            f"L'actif « {actif.nom} » est à re-valoriser "
            f"(échéance estimée : {prochaine}). "
            f"Sa dernière valorisation date du {actif.date_valorisation}."
        ),
        valeur_constatee=None,
        valeur_seuil=None,
    )
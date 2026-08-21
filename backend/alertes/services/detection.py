from decimal import Decimal

from alertes.models import Alerte, NiveauAlerte, TypeAlerte
from alertes.services.formatage import date_courte, euros, mois_annee, pourcent

# ---------------------------------------------------------------------------
# Détection budget
# ---------------------------------------------------------------------------

def refermer_alertes_budget_perimees(budget) -> int:
    """
    Acquitte les alertes budget dont le seuil **n'est plus franchi**.

    Une alerte porte une phrase assemblée **une fois** puis figée en base. Le
    budget, lui, se recalcule à chaque flux. Sans ce ménage, un budget retombé
    à 60 % continue d'afficher « atteint 93,21 % » : deux vérités concurrentes
    sur le même écran, et le lecteur cesse de croire les deux.

    Le critère est le seuil **de l'alerte elle-même** (`valeur_seuil`), pas un
    seuil global : à 85 %, l'alerte de dépassement (seuil 100) se referme, celle
    d'avertissement (seuil 80) reste ouverte, ce qui est exact dans les deux cas.

    Renvoie le nombre d'alertes refermées.

    *(D01 de la revue UI/UX du 2026-08-20.)*
    """
    ouvertes = Alerte.objects.filter(
        budget=budget,
        acquittee=False,
        type_alerte__in=(TypeAlerte.BUDGET_ALERTE, TypeAlerte.BUDGET_DEPASSE),
    )
    referme = 0
    for alerte in ouvertes:
        if alerte.valeur_seuil is None:
            continue
        if budget.taux_consommation < alerte.valeur_seuil:
            alerte.acquitter()
            referme += 1
    return referme


def detecter_alertes_budget(budget) -> list[Alerte]:
    """
    Génère des alertes si le taux de consommation du budget
    dépasse les seuils d'alerte ou de dépassement.

    Seuils :
    - >= 100% → BUDGET_DEPASSE / CRITIQUE
    - >= 80%  → BUDGET_ALERTE / AVERTISSEMENT

    Une alerte non acquittée du même type sur le même budget
    n'est pas recréée (dédoublonnage).

    ⚠️ **Referme d'abord les alertes périmées.** La détection est appelée à
    chaque mouvement sur le budget : c'est le seul endroit qui sait que la
    consommation a baissé.

    Fiabilité : réel (basé sur les flux saisis).
    """
    alertes_creees = []

    refermer_alertes_budget_perimees(budget)

    if budget.taux_consommation >= 100:
        type_a = TypeAlerte.BUDGET_DEPASSE
        niveau = NiveauAlerte.CRITIQUE
        explication = (
            f"Le budget « {budget.libelle} » pour {mois_annee(budget.mois)} "
            f"est dépassé : {euros(budget.montant_consomme)} consommés "
            f"sur {euros(budget.montant_prevu)} prévus "
            f"({pourcent(budget.taux_consommation)})."
        )
    elif budget.taux_consommation >= 80:
        type_a = TypeAlerte.BUDGET_ALERTE
        niveau = NiveauAlerte.AVERTISSEMENT
        explication = (
            f"Le budget « {budget.libelle} » pour {mois_annee(budget.mois)} "
            f"atteint {pourcent(budget.taux_consommation)} de consommation "
            f"({euros(budget.montant_consomme)} sur {euros(budget.montant_prevu)})."
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
            f"Le solde théorique du compte « {compte.nom} » "
            f"({euros(compte.solde_theorique)}) "
            f"est inférieur au seuil configuré ({euros(seuil)})."
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
            f"L'abonnement « {abonnement.nom} » n'a pas été constaté "
            f"depuis plus d'un cycle ({abonnement.frequence.libelle}). "
            f"Dernière occurrence : {date_courte(abonnement.derniere_occurrence)}."
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
            f"Le montant constaté pour l'abonnement « {abonnement.nom} » "
            f"({euros(montant_reel)}) s'écarte de {pourcent(result['divergence_pct'])} "
            f"du montant attendu ({euros(abonnement.montant_attendu)}). "
            f"Seuil configuré : {pourcent(abonnement.seuil_divergence_pct)}."
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
            f"Un écart de {euros(compte.ecart_solde)} a été détecté "
            f"sur le compte « {compte.nom} » "
            f"(solde réel : {euros(compte.solde_reel)}, "
            f"solde théorique : {euros(compte.solde_theorique)}). "
            f"Seuil configuré : {euros(seuil)}."
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
            f"(échéance estimée : {date_courte(prochaine)}). "
            f"Sa dernière valorisation date du {date_courte(actif.date_valorisation)}."
        ),
        valeur_constatee=None,
        valeur_seuil=None,
    )
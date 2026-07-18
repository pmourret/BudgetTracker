"""
Moteur de rapprochement bancaire (brique ③).

Confronte les lignes d'un relevé (vérité BANQUE) aux flux de l'app (vérité
FOYER) et produit un diagnostic par ligne, sans jamais modifier un flux
(lecture seule, phase 14-A). Seul l'état de rapprochement de la ligne
(`LigneBancaire.statut`/`flux`) est écrit.

Deux couches :
  - Fonctions PURES (`filtrer_doublons`, `apparier`) : aucun accès DB,
    testables en isolation → c'est là que vit la règle métier.
  - Orchestration DB (`executer_rapprochement`, `candidats_pour`,
    `valider_ligne`, `rejeter_ligne`) : charge les flux, persiste les statuts.

Règles de matching (validées foyer) :
  - STRICT d'abord : passe 1 = montant ET date exacts.
  - Tolérance ensuite : passe 2 = montant exact, date à ± N jours
    (paramètre administrable `tolerance_jours_rapprochement`).
  - Une ligne avec PLUSIEURS candidats en tolérance reste `ambigu` :
    on ne devine pas, l'utilisateur tranche (valider/rejeter).
  - Un flux est consommé au plus une fois (pas de double appariement).
  - Les virements internes se rapprochent naturellement : le flux
    `est_transfert` du compte a le bon montant/date, il est dans le vivier.
  - Les flux `est_ajustement` sont exclus du vivier (pas de contrepartie banque).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from ..models import StatutRapprochement


# --- Couche PURE -------------------------------------------------------------

@dataclass
class Decision:
    """Verdict de rapprochement pour une ligne (parallèle à la liste d'entrée)."""

    statut: str                       # StatutRapprochement.*
    flux_id: object | None = None     # flux apparié si RAPPROCHE
    candidats_ids: list = field(default_factory=list)  # flux plausibles si AMBIGU


@dataclass
class ResultatRapprochement:
    decisions: list[Decision]         # une par ligne, dans l'ordre d'entrée
    flux_non_apparies_ids: list       # flux app sans ligne banque (à qualifier)


def filtrer_doublons(lignes, compteur_existant: Counter):
    """
    Écarte les lignes déjà présentes dans un import précédent (anti-doublon).

    `compteur_existant` = multiset des hash déjà connus pour le compte. On
    raisonne en OCCURRENCES : si un hash est présent 2 fois en base, 2 lignes
    entrantes de même hash sont des doublons, mais une 3ᵉ occurrence est une
    vraie nouvelle opération (BoursoBank peut réémettre un mouvement identique).

    Retourne (nouvelles_lignes, nb_doublons). Ne mute pas l'entrée.
    """
    restant = Counter(compteur_existant)
    nouvelles = []
    nb_doublons = 0
    for ligne in lignes:
        h = ligne.hash_dedup
        if restant.get(h, 0) > 0:
            restant[h] -= 1
            nb_doublons += 1
        else:
            nouvelles.append(ligne)
    return nouvelles, nb_doublons


def _candidats(ligne, flux, consommes, delta_max):
    """Flux disponibles au montant exact et à |Δdate| <= delta_max (jours)."""
    return [
        f for f in flux
        if f.id not in consommes
        and f.montant == ligne.montant
        and abs((f.date_flux - ligne.date_operation).days) <= delta_max
    ]


def apparier(lignes, flux, tolerance_jours: int) -> ResultatRapprochement:
    """
    Apparie des `lignes` (banque) à des `flux` (app). Fonction pure.

    `lignes` : objets exposant .montant (Decimal) et .date_operation (date).
    `flux`   : objets exposant .id, .montant (Decimal) et .date_flux (date).
    """
    flux = list(flux)
    consommes: set = set()
    decisions: list[Decision | None] = [None] * len(lignes)

    # Passe 1 — STRICT : montant ET date exacts. Plusieurs correspondances
    # exactes = mouvements interchangeables → on en consomme un (déterministe).
    for i, ligne in enumerate(lignes):
        exacts = [
            f for f in _candidats(ligne, flux, consommes, delta_max=0)
        ]
        if exacts:
            choisi = min(exacts, key=lambda f: str(f.id))
            consommes.add(choisi.id)
            decisions[i] = Decision(StatutRapprochement.RAPPROCHE, choisi.id)

    # Passe 2 — TOLÉRANCE : propagation de contraintes. On résout d'abord les
    # lignes n'ayant qu'UN seul candidat (les consommer peut lever d'autres
    # ambiguïtés), en boucle jusqu'à stabilité.
    non_resolues = [i for i, d in enumerate(decisions) if d is None]
    progres = True
    while progres:
        progres = False
        for i in list(non_resolues):
            cands = _candidats(lignes[i], flux, consommes, tolerance_jours)
            if len(cands) == 1:
                choisi = cands[0]
                consommes.add(choisi.id)
                decisions[i] = Decision(StatutRapprochement.RAPPROCHE, choisi.id)
                non_resolues.remove(i)
                progres = True

    # Reliquat : 0 candidat = manquant dans l'app ; ≥2 = ambigu (à trancher).
    for i in non_resolues:
        cands = _candidats(lignes[i], flux, consommes, tolerance_jours)
        if not cands:
            decisions[i] = Decision(StatutRapprochement.MANQUANT_APP)
        else:
            decisions[i] = Decision(
                StatutRapprochement.AMBIGU,
                candidats_ids=[f.id for f in cands],
            )

    flux_non_apparies = [f.id for f in flux if f.id not in consommes]
    return ResultatRapprochement(decisions=decisions, flux_non_apparies_ids=flux_non_apparies)


# --- Couche ORCHESTRATION (DB) ----------------------------------------------

def _tolerance_jours():
    from referentiels.models import ParametresBudget
    return ParametresBudget.get_solo().tolerance_jours_rapprochement


def _flux_du_compte(compte, date_min, date_max, tolerance):
    """
    Vivier de flux candidats : ceux du compte dans la fenêtre du relevé,
    élargie de la tolérance de part et d'autre. Transferts inclus (règle §14),
    ajustements exclus. `statut` préchargé pour qualifier les non-appariés.
    """
    from flux.models import Flux

    marge = timedelta(days=tolerance)
    return list(
        Flux.objects
        .filter(
            compte=compte,
            est_ajustement=False,
            date_flux__gte=date_min - marge,
            date_flux__lte=date_max + marge,
        )
        .select_related("statut")
    )


def executer_rapprochement(import_lot):
    """
    Lance le rapprochement d'un lot déjà peuplé de `LigneBancaire`, persiste
    les statuts et les compteurs, renvoie un rapport structuré.

    Ne crée ni ne modifie AUCUN flux (14-A). Idempotent : relancer recalcule.
    """
    from django.db import transaction

    lignes = list(import_lot.lignes.all())
    if not lignes:
        return construire_rapport(import_lot)

    tolerance = _tolerance_jours()
    dates = [l.date_operation for l in lignes]
    flux = _flux_du_compte(import_lot.compte, min(dates), max(dates), tolerance)

    resultat = apparier(lignes, flux, tolerance)

    compteurs = Counter()
    with transaction.atomic():
        for ligne, decision in zip(lignes, resultat.decisions):
            ligne.statut = decision.statut
            ligne.flux_id = decision.flux_id
            ligne.save(update_fields=["statut", "flux", "updated_at"])
            compteurs[decision.statut] += 1

        import_lot.nb_lignes = len(lignes)
        import_lot.nb_rapproches = compteurs[StatutRapprochement.RAPPROCHE]
        import_lot.nb_manquants_app = compteurs[StatutRapprochement.MANQUANT_APP]
        import_lot.nb_ambigus = compteurs[StatutRapprochement.AMBIGU]
        import_lot.nb_ignores = compteurs[StatutRapprochement.IGNORE]
        import_lot.save(update_fields=[
            "nb_lignes", "nb_rapproches", "nb_manquants_app",
            "nb_ambigus", "nb_ignores", "updated_at",
        ])

    return construire_rapport(import_lot)


def candidats_pour(ligne):
    """
    Flux candidats d'une ligne (pour l'écran de validation d'un ambigu) :
    montant exact, date à ± tolérance, non déjà rapprochés dans ce lot.
    """
    from flux.models import Flux

    lot = ligne.import_lot
    tolerance = _tolerance_jours()
    marge = timedelta(days=tolerance)
    deja_lies = (
        lot.lignes
        .filter(statut=StatutRapprochement.RAPPROCHE)
        .exclude(flux=None)
        .values_list("flux_id", flat=True)
    )
    return list(
        Flux.objects
        .filter(
            compte=lot.compte,
            est_ajustement=False,
            montant=ligne.montant,
            date_flux__gte=ligne.date_operation - marge,
            date_flux__lte=ligne.date_operation + marge,
        )
        .exclude(id__in=list(deja_lies))
        .select_related("statut", "categorie")
    )


class ValidationInvalide(Exception):
    """Validation d'une ligne impossible (flux non candidat, etc.)."""


def valider_ligne(ligne, flux):
    """
    L'utilisateur confirme un appariement ambigu : la ligne pointe le flux
    choisi et passe `rapproche`. Le flux doit être un candidat valide.
    """
    candidats_ids = {f.id for f in candidats_pour(ligne)}
    if flux.id not in candidats_ids:
        raise ValidationInvalide(
            "Ce flux n'est pas un candidat valide pour cette ligne."
        )
    ligne.flux = flux
    ligne.statut = StatutRapprochement.RAPPROCHE
    ligne.save(update_fields=["flux", "statut", "updated_at"])
    _resynchroniser_compteurs(ligne.import_lot)
    return ligne


def rejeter_ligne(ligne):
    """
    L'utilisateur écarte les candidats d'un ambigu : la ligne devient
    `manquant_app` (oubli de saisie probable), sans flux rattaché.
    """
    ligne.flux = None
    ligne.statut = StatutRapprochement.MANQUANT_APP
    ligne.save(update_fields=["flux", "statut", "updated_at"])
    _resynchroniser_compteurs(ligne.import_lot)
    return ligne


def _resynchroniser_compteurs(import_lot):
    from django.db.models import Count

    par_statut = dict(
        import_lot.lignes.values_list("statut").annotate(n=Count("id"))
    )
    import_lot.nb_lignes = sum(par_statut.values())
    import_lot.nb_rapproches = par_statut.get(StatutRapprochement.RAPPROCHE, 0)
    import_lot.nb_manquants_app = par_statut.get(StatutRapprochement.MANQUANT_APP, 0)
    import_lot.nb_ambigus = par_statut.get(StatutRapprochement.AMBIGU, 0)
    import_lot.nb_ignores = par_statut.get(StatutRapprochement.IGNORE, 0)
    import_lot.save(update_fields=[
        "nb_lignes", "nb_rapproches", "nb_manquants_app",
        "nb_ambigus", "nb_ignores", "updated_at",
    ])


# --- Contrôle de solde -------------------------------------------------------

def controle_solde(import_lot):
    """
    Contrôle de cohérence globale : compare le solde du relevé (accountbalance
    de la ligne la plus récente) au solde réel de l'app À CETTE DATE.

        solde_app(date) = solde_initial + Σ(flux définitifs, date_flux ≤ date)

    C'est le pendant « macro » du rapprochement ligne à ligne : si les deux
    soldes concordent au centime, le journal de l'app est complet sur la
    période ; un écart pointe des opérations non saisies ou mal saisies (le
    détail est dans les sections d'écarts). Fiabilité : **contrôle** — le
    solde réel de l'app reste la vérité, l'écart n'est pas une erreur en soi.

    Renvoie None si aucune ligne du relevé ne porte de solde bancaire.
    """
    from django.db.models import Sum
    from flux.models import Flux

    ligne = (
        import_lot.lignes
        .exclude(solde_apres=None)
        .order_by("-date_operation", "-created_at")
        .first()
    )
    if ligne is None:
        return None

    compte = import_lot.compte
    total_definitifs = (
        Flux.objects
        .filter(
            compte=compte,
            statut__est_definitif=True,
            date_flux__lte=ligne.date_operation,
        )
        .aggregate(t=Sum("montant"))["t"]
    ) or Decimal("0.00")

    solde_app = compte.solde_initial + total_definitifs
    ecart = solde_app - ligne.solde_apres
    return {
        "date_reference": ligne.date_operation,
        "solde_banque": ligne.solde_apres,
        "solde_app": solde_app,
        "ecart": ecart,
        # Comparaison exacte au centime : concordance = fait arithmétique,
        # pas un seuil arbitraire (règle 1). Pas de tolérance codée en dur.
        "coherent": ecart == Decimal("0.00"),
    }


# --- Construction du rapport (état PERSISTÉ) ---------------------------------

def flux_orphelins(import_lot):
    """
    Flux du vivier non rattachés à une ligne rapprochée de ce lot, qualifiés.

    Recalculé sur l'état PERSISTÉ (tient donc compte des validations manuelles :
    un flux validé sur un ambigu disparaît des orphelins). Chaque entrée :
    {"flux": <Flux>, "motif": ...}.
      - previsionnel_non_passe : flux prévisionnel non encore au relevé (normal).
      - erreur_saisie_probable : flux définitif absent du relevé (oubli banque ?
        ou erreur de saisie côté app).
    """
    lignes = list(import_lot.lignes.all())
    if not lignes:
        return []
    tolerance = _tolerance_jours()
    dates = [l.date_operation for l in lignes]
    vivier = _flux_du_compte(import_lot.compte, min(dates), max(dates), tolerance)
    lies = set(
        import_lot.lignes
        .filter(statut=StatutRapprochement.RAPPROCHE)
        .exclude(flux=None)
        .values_list("flux_id", flat=True)
    )
    orphelins = []
    for f in vivier:
        if f.id in lies:
            continue
        motif = ("previsionnel_non_passe" if not f.statut.est_definitif
                 else "erreur_saisie_probable")
        orphelins.append({"flux": f, "motif": motif})
    return orphelins


def construire_rapport(import_lot):
    """
    Rapport lisible (id-based, découplé des serializers), lu depuis l'état
    persisté. Les ambigus embarquent la liste d'ids candidats.
    """
    lignes = list(import_lot.lignes.select_related("flux").all())
    lignes_out = []
    for ligne in lignes:
        candidats_ids = []
        if ligne.statut == StatutRapprochement.AMBIGU:
            candidats_ids = [f.id for f in candidats_pour(ligne)]
        lignes_out.append({
            "ligne_id": ligne.id,
            "date_operation": ligne.date_operation,
            "libelle": ligne.libelle,
            "montant": ligne.montant,
            "statut": ligne.statut,
            "flux_id": ligne.flux_id,
            "candidats_ids": candidats_ids,
        })

    flux_sans_ligne = [
        {
            "flux_id": o["flux"].id,
            "date_flux": o["flux"].date_flux,
            "libelle": o["flux"].libelle,
            "montant": o["flux"].montant,
            "motif": o["motif"],
        }
        for o in flux_orphelins(import_lot)
    ]

    return {
        "lot_id": import_lot.id,
        "compte_id": import_lot.compte_id,
        "tolerance_jours": _tolerance_jours(),
        "controle_solde": controle_solde(import_lot),
        "lignes": lignes_out,
        "flux_sans_ligne": flux_sans_ligne,
    }

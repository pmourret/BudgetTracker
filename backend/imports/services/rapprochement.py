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


def flux_ids_deja_pointes(compte, sauf_lot=None):
    """
    Flux du compte DÉJÀ pointés par un rapprochement (14-B, anti-re-match) :
    ils sont rattachés à une ligne rapprochée d'un lot vivant. On les exclut du
    vivier des AUTRES lots pour ne pas re-proposer un flux déjà rapproché quand
    deux relevés se chevauchent. `sauf_lot` retire le lot courant (qu'on
    recalcule à neuf).
    """
    from ..models import LigneBancaire

    qs = (
        LigneBancaire.objects
        .filter(
            import_lot__compte=compte,
            import_lot__is_deleted=False,
            statut=StatutRapprochement.RAPPROCHE,
        )
        .exclude(flux=None)
    )
    if sauf_lot is not None:
        qs = qs.exclude(import_lot=sauf_lot)
    return set(qs.values_list("flux_id", flat=True))


def _flux_du_compte(compte, date_min, date_max, tolerance, exclure_ids=()):
    """
    Vivier de flux candidats : ceux du compte dans la fenêtre du relevé,
    élargie de la tolérance de part et d'autre. Transferts inclus (règle §14),
    ajustements exclus, flux déjà pointés par un autre lot exclus (14-B).
    `statut` préchargé pour qualifier les non-appariés.
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
        .exclude(id__in=list(exclure_ids))
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
    exclure = flux_ids_deja_pointes(import_lot.compte, sauf_lot=import_lot)
    flux = _flux_du_compte(
        import_lot.compte, min(dates), max(dates), tolerance, exclure_ids=exclure
    )

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
    # Exclure : flux déjà rapprochés dans CE lot + flux pointés par un AUTRE
    # lot vivant (14-B anti-re-match).
    deja_lies = set(
        lot.lignes
        .filter(statut=StatutRapprochement.RAPPROCHE)
        .exclude(flux=None)
        .values_list("flux_id", flat=True)
    )
    deja_lies |= flux_ids_deja_pointes(lot.compte, sauf_lot=lot)
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


class CreationFluxInvalide(Exception):
    """Création de flux impossible depuis cette ligne (déjà rapprochée, etc.)."""


def _reference_bancaire(ligne):
    """Trace lisible posée dans `Flux.reference_externe` d'un flux créé depuis
    le relevé (traçabilité ; jamais écrasée pour un flux existant)."""
    lot = ligne.import_lot
    return f"Relevé {lot.get_banque_display()} du {ligne.date_operation:%d/%m/%Y}"[:100]


def creer_flux_depuis_ligne(ligne, categorie, libelle=None, statut=None):
    """
    14-B — crée le flux manquant correspondant à une ligne de relevé, puis
    rattache la ligne (→ rapproché). **Seule** écriture de flux du module.

    - `categorie` obligatoire (flux normal, jamais transfert : un virement doit
      passer par /transferts/ — l'UI avertit sur les libellés « VIR »).
    - type_flux dérivé du signe (négatif → DEBIT, positif → CREDIT).
    - statut par défaut = définitif (la ligne est sur le relevé = réel).
    - `reference_externe` reçoit une trace bancaire lisible.

    Atomique. Lève CreationFluxInvalide si la ligne est déjà rapprochée.
    """
    from django.db import transaction
    from flux.models import Flux
    from referentiels.models import StatutFlux, TypeFlux

    if ligne.statut == StatutRapprochement.RAPPROCHE or ligne.flux_id:
        raise CreationFluxInvalide("Cette ligne est déjà rapprochée à un flux.")

    code_type = "DEBIT" if ligne.montant < 0 else "CREDIT"
    type_flux = TypeFlux.objects.filter(code=code_type).first()
    if type_flux is None:
        raise CreationFluxInvalide(f"Référentiel TypeFlux « {code_type} » manquant.")

    if statut is None:
        statut = StatutFlux.objects.filter(est_definitif=True).first()
    if statut is None:
        raise CreationFluxInvalide("Aucun statut définitif configuré.")

    compte = ligne.import_lot.compte
    with transaction.atomic():
        flux = Flux.objects.create(
            compte=compte,
            categorie=categorie,
            type_flux=type_flux,
            statut=statut,
            devise=compte.devise,
            montant=ligne.montant,
            date_flux=ligne.date_operation,
            libelle=(libelle or ligne.libelle_suggere or ligne.libelle)[:255],
            reference_externe=_reference_bancaire(ligne),
        )
        ligne.flux = flux
        ligne.statut = StatutRapprochement.RAPPROCHE
        ligne.save(update_fields=["flux", "statut", "updated_at"])
        _resynchroniser_compteurs(ligne.import_lot)

    return flux


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
    Contrôle de cohérence globale : compare le **solde actuel confirmé** de
    l'app au **dernier solde connu du relevé** (accountbalance de la ligne la
    plus récente).

        solde_app = solde_initial + Σ(TOUS les flux définitifs du compte)
                  = solde_reel actuel

    ⚠️ On compare au solde ACTUEL, pas au solde de l'app « à la date du relevé ».
    Raison (retour d'usage prod) : un contrôle ancré à la date du relevé est
    faussé par le **décalage de dates de saisie** — une opération que la banque
    a passée avant la date du relevé mais saisie plus tard dans l'app crée un
    faux écart, alors que les soldes finaux concordent. Comparer le solde
    actuel neutralise ce bruit tout en détectant un vrai manque (une opération
    jamais saisie fait diverger le solde actuel). Le contrôle est donc le plus
    fiable quand le relevé est à jour (dernier point ≈ aujourd'hui) ; pour un
    relevé ancien, l'écart reflète simplement les mouvements survenus depuis.

    Fiabilité : **contrôle** — le solde réel de l'app reste la vérité, l'écart
    n'est pas une erreur en soi ; le détail est dans les sections d'écarts.

    Renvoie None si aucune ligne du relevé ne porte de solde bancaire.
    """
    ligne = (
        import_lot.lignes
        .exclude(solde_apres=None)
        .order_by("-date_operation", "-created_at")
        .first()
    )
    return _comparer_au_releve(import_lot.compte, ligne)


def _comparer_au_releve(compte, ligne):
    """Cœur du contrôle : le solde actuel du compte face à un point de relevé.

    Extrait de `controle_solde` quand le contrôle a dû être exposé **hors de la
    page d'import** (`dernier_controle_pour_compte`). Les deux appelants
    diffèrent par la ligne de référence qu'ils choisissent, pas par le calcul —
    le dupliquer aurait laissé deux réponses possibles à la même question.
    """
    from django.db.models import Sum
    from flux.models import Flux

    if ligne is None:
        return None

    total_definitifs = (
        Flux.objects
        .filter(compte=compte, statut__est_definitif=True)
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


def dernier_controle_pour_compte(compte, aujourd_hui=None):
    """Le contrôle de solde d'un compte, **sans passer par un lot d'import**.

    Ajouté en août 2026 : le contrôle n'existait que dans la page d'import,
    c'est-à-dire visible seulement le jour où l'on charge un relevé. Or c'est
    la question qu'on se pose devant un compte — « mon solde est-il juste ? » —
    pas devant un fichier.

    ⚠️ **La référence est le point de relevé le plus récent du compte, tous
    lots confondus**, et non « le dernier lot importé ». Importer un vieux
    relevé après un récent est banal (rattrapage d'un mois oublié) ; ancrer le
    contrôle sur le dernier import ferait alors *reculer* la référence et
    afficherait un faux écart, en donnant toutes les apparences d'un problème
    nouveau.

    ⚠️ **`anciennete_jours` fait partie de la réponse, pas de la décoration.**
    Le contrôle compare au solde ACTUEL (voir `controle_solde`) : sur un relevé
    ancien, un écart ne signale rien d'autre que les mouvements survenus
    depuis. Sans l'âge affiché, le widget crierait à l'erreur chaque fois qu'on
    n'a pas importé de relevé depuis deux semaines. **Aucun seuil ici** (règle
    1) : on donne le nombre de jours, la lecture reste humaine.

    Renvoie None si ce compte n'a aucun relevé portant un solde bancaire.
    """
    from datetime import date

    from imports.models import LigneBancaire

    ligne = (
        LigneBancaire.objects
        .filter(import_lot__compte=compte)
        .exclude(solde_apres=None)
        .order_by("-date_operation", "-created_at")
        .select_related("import_lot")
        .first()
    )
    controle = _comparer_au_releve(compte, ligne)
    if controle is None:
        return None

    # Jour injecté (règle de suite : dépendance temporelle testable).
    reference = aujourd_hui or date.today()
    return {
        **controle,
        "anciennete_jours": (reference - ligne.date_operation).days,
        "import_id": str(ligne.import_lot_id),
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
    exclure = flux_ids_deja_pointes(import_lot.compte, sauf_lot=import_lot)
    vivier = _flux_du_compte(
        import_lot.compte, min(dates), max(dates), tolerance, exclure_ids=exclure
    )
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

"""
Service d'analyse rétrospective — Phase 13 (lecture seule).

Vue analytique multi-mois : comprendre *où* part l'argent, *quand* et
*comment*, sur une fenêtre glissante de mois comptables. 100 % RÉEL (basé
sur les flux saisis), AUCUNE projection — le prévisionnel reste une vue
séparée (règle : ne jamais mélanger réel et projeté). Transferts et flux
d'ajustement exclus de tous les agrégats (règles métier 4).

Trois blocs :
- ``tendances``  : série mensuelle dépenses / revenus / épargne + totaux,
                   moyennes et comparaison *descriptive* à la période
                   précédente (aucun jugement, aucun seuil — règle 13) ;
- ``categories`` : évolution de chaque poste (catégorie majeure, mineures
                   agrégées sous leur parent) dans le temps ;
- ``rythme``     : dépenses par jour de semaine + libellés récurrents.

Toutes les bornes mensuelles passent par ``core/services/periode.py``
(mois comptable, règle §4.3) : filtrer par ``flux.mois`` est auto-correct.
Le service accepte ``aujourd_hui`` injectable pour des tests déterministes.
"""
import datetime
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db.models import Count, Q, Sum
from django.db.models.functions import ExtractIsoWeekDay

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
DIX = Decimal("0.1")


def _fenetre_mois(nb_mois: int, mois_fin: datetime.date) -> list:
    """Labels des mois comptables de la fenêtre [premier … mois_fin]."""
    premier = mois_fin - relativedelta(months=nb_mois - 1)
    mois, curseur = [], premier
    while curseur <= mois_fin:
        mois.append(curseur)
        curseur += relativedelta(months=1)
    return mois


def _taux_epargne(epargne: Decimal, revenus: Decimal) -> Decimal:
    """Part de l'épargne dans les revenus (%), 0 si aucun revenu."""
    if revenus and revenus > 0:
        return (epargne / revenus * 100).quantize(DIX)
    return Decimal("0.0")


# --------------------------------------------------------------------------
# Bloc « tendances »
# --------------------------------------------------------------------------
def _serie_mensuelle(mois_labels: list) -> list:
    """Dépenses / revenus / épargne / taux, mois par mois."""
    from flux.models import Flux

    lignes = (
        Flux.objects.filter(
            mois__in=mois_labels, est_transfert=False, est_ajustement=False
        )
        .values("mois")
        .annotate(
            depenses=Sum("montant", filter=Q(montant__lt=0)),
            revenus=Sum("montant", filter=Q(montant__gt=0)),
        )
    )
    par_mois = {ligne["mois"]: ligne for ligne in lignes}

    serie = []
    for mois in mois_labels:
        ligne = par_mois.get(mois, {})
        depenses = -(ligne.get("depenses") or ZERO)
        revenus = ligne.get("revenus") or ZERO
        epargne = revenus - depenses
        serie.append({
            "mois": mois.isoformat(),
            "depenses": depenses,
            "revenus": revenus,
            "epargne_nette": epargne,
            "taux_epargne": _taux_epargne(epargne, revenus),
        })
    return serie


def _totaux(mois_labels: list) -> dict:
    """Totaux dépenses / revenus / épargne (positifs) sur la fenêtre."""
    from flux.models import Flux

    agg = Flux.objects.filter(
        mois__in=mois_labels, est_transfert=False, est_ajustement=False
    ).aggregate(
        depenses=Sum("montant", filter=Q(montant__lt=0)),
        revenus=Sum("montant", filter=Q(montant__gt=0)),
    )
    depenses = -(agg["depenses"] or ZERO)
    revenus = agg["revenus"] or ZERO
    return {
        "depenses": depenses,
        "revenus": revenus,
        "epargne_nette": revenus - depenses,
    }


def _comparaison(actuel: dict, precedent: dict) -> dict:
    """
    Δ descriptif période N vs N-1 pour chaque agrégat.
    ``variation_pct`` = None si la période précédente est nulle (pas de
    base de comparaison). Aucun jugement : le front affiche neutre.
    """
    def variation(a: Decimal, p: Decimal):
        if p and p != 0:
            return ((a - p) / abs(p) * 100).quantize(DIX)
        return None

    return {
        cle: {
            "actuel": actuel[cle],
            "precedent": precedent[cle],
            "variation_pct": variation(actuel[cle], precedent[cle]),
        }
        for cle in ("depenses", "revenus", "epargne_nette")
    }


def _bloc_tendances(mois_labels: list, mois_precedents: list) -> dict:
    nb = len(mois_labels)
    totaux = _totaux(mois_labels)
    totaux["taux_epargne"] = _taux_epargne(totaux["epargne_nette"], totaux["revenus"])
    totaux_prec = _totaux(mois_precedents)

    moyennes = {
        cle: (totaux[cle] / nb).quantize(CENT)
        for cle in ("depenses", "revenus", "epargne_nette")
    }

    return {
        "definition": (
            "Dépenses, revenus et épargne nette agrégés mois par mois sur la "
            "période, avec totaux, moyennes mensuelles et comparaison à la "
            "période précédente. Fiabilité réelle (flux saisis), transferts "
            "et ajustements exclus."
        ),
        "fiabilite": "reel",
        "series": _serie_mensuelle(mois_labels),
        "totaux_periode": totaux,
        "moyennes_mensuelles": moyennes,
        "comparaison_periode_precedente": _comparaison(totaux, totaux_prec),
    }


# --------------------------------------------------------------------------
# Bloc « categories »
# --------------------------------------------------------------------------
def _bloc_categories(mois_labels: list) -> dict:
    """
    Dépenses regroupées par catégorie majeure (mineures agrégées sous leur
    parent), avec total, moyenne mensuelle, part % et série mensuelle.
    """
    from flux.models import Flux

    lignes = (
        Flux.objects.filter(
            mois__in=mois_labels,
            montant__lt=0,
            est_transfert=False,
            est_ajustement=False,
            categorie__isnull=False,
        )
        .values(
            "mois",
            "categorie",
            "categorie__nom",
            "categorie__parent",
            "categorie__parent__nom",
        )
        .annotate(total=Sum("montant"))
    )

    majeures = {}
    for row in lignes:
        montant = -row["total"]  # positif
        parent_id = row["categorie__parent"]
        if parent_id is None:
            key, nom = str(row["categorie"]), row["categorie__nom"]
        else:
            key, nom = str(parent_id), row["categorie__parent__nom"]

        maj = majeures.setdefault(
            key,
            {"id": key, "nom": nom, "total_periode": ZERO, "_serie": {}},
        )
        maj["total_periode"] += montant
        maj["_serie"][row["mois"]] = maj["_serie"].get(row["mois"], ZERO) + montant

    total_global = sum((m["total_periode"] for m in majeures.values()), ZERO)
    nb = len(mois_labels)

    par_categorie = []
    for maj in sorted(majeures.values(), key=lambda x: x["total_periode"], reverse=True):
        serie = [
            {"mois": mois.isoformat(), "total": maj["_serie"].get(mois, ZERO)}
            for mois in mois_labels
        ]
        part = (
            (maj["total_periode"] / total_global * 100).quantize(DIX)
            if total_global > 0 else Decimal("0.0")
        )
        par_categorie.append({
            "id": maj["id"],
            "nom": maj["nom"],
            "total_periode": maj["total_periode"],
            "moyenne_mensuelle": (maj["total_periode"] / nb).quantize(CENT),
            "part_pct": part,
            "serie": serie,
        })

    return {
        "definition": (
            "Dépenses par catégorie majeure sur la période (les mineures sont "
            "regroupées sous leur parent), avec part du total, moyenne "
            "mensuelle et évolution mois par mois. Fiabilité réelle."
        ),
        "fiabilite": "reel",
        "total_periode": total_global,
        "par_categorie": par_categorie,
    }


# --------------------------------------------------------------------------
# Bloc « titulaires » (ventilation par personne du foyer)
# --------------------------------------------------------------------------
def _bloc_titulaires(mois_labels: list) -> dict:
    """
    Dépenses / revenus / épargne regroupés par personne du foyer, selon le
    propriétaire du compte (`compte.titulaire`). Les comptes communs
    (`est_commun=True`) forment un bucket « Commun » distinct — quel que soit
    leur propriétaire — pour éviter d'attribuer un compte joint à une seule
    personne (arbitrage foyer). Un sous-bloc `commun_vs_perso` résume les
    deux natures. Fiabilité réelle ; transferts et ajustements exclus.
    """
    from flux.models import Flux

    lignes = (
        Flux.objects.filter(
            mois__in=mois_labels, est_transfert=False, est_ajustement=False
        )
        .values(
            "compte__est_commun",
            "compte__titulaire",
            "compte__titulaire__libelle",
        )
        .annotate(
            depenses=Sum("montant", filter=Q(montant__lt=0)),
            revenus=Sum("montant", filter=Q(montant__gt=0)),
        )
    )

    buckets = {}
    for row in lignes:
        depenses = -(row["depenses"] or ZERO)
        revenus = row["revenus"] or ZERO
        if row["compte__est_commun"]:
            key, nom, est_commun = "commun", "Commun", True
        else:
            key = str(row["compte__titulaire"])
            nom = row["compte__titulaire__libelle"]
            est_commun = False

        bucket = buckets.setdefault(
            key,
            {"id": key, "nom": nom, "est_commun": est_commun,
             "depenses": ZERO, "revenus": ZERO},
        )
        bucket["depenses"] += depenses
        bucket["revenus"] += revenus

    total_depenses = sum((b["depenses"] for b in buckets.values()), ZERO)

    par_titulaire = []
    for bucket in sorted(buckets.values(), key=lambda x: x["depenses"], reverse=True):
        part = (
            (bucket["depenses"] / total_depenses * 100).quantize(DIX)
            if total_depenses > 0 else Decimal("0.0")
        )
        par_titulaire.append({
            "id": bucket["id"],
            "nom": bucket["nom"],
            "est_commun": bucket["est_commun"],
            "depenses": bucket["depenses"],
            "revenus": bucket["revenus"],
            "epargne_nette": bucket["revenus"] - bucket["depenses"],
            "part_depenses_pct": part,
        })

    commun = buckets.get("commun", {"depenses": ZERO, "revenus": ZERO})
    perso_depenses = sum(
        (b["depenses"] for b in buckets.values() if not b["est_commun"]), ZERO
    )
    perso_revenus = sum(
        (b["revenus"] for b in buckets.values() if not b["est_commun"]), ZERO
    )

    return {
        "definition": (
            "Dépenses, revenus et épargne par personne du foyer (propriétaire "
            "du compte). Les comptes communs forment un groupe « Commun » à "
            "part, jamais rattaché à une seule personne. Fiabilité réelle."
        ),
        "fiabilite": "reel",
        "total_depenses": total_depenses,
        "par_titulaire": par_titulaire,
        "commun_vs_perso": {
            "commun": {"depenses": commun["depenses"], "revenus": commun["revenus"]},
            "perso": {"depenses": perso_depenses, "revenus": perso_revenus},
        },
    }


# --------------------------------------------------------------------------
# Bloc « rythme »
# --------------------------------------------------------------------------
def _par_jour_semaine(mois_labels: list) -> list:
    """Dépenses ventilées par jour de semaine (1=lundi … 7=dimanche)."""
    from flux.models import Flux

    lignes = (
        Flux.objects.filter(
            mois__in=mois_labels,
            montant__lt=0,
            est_transfert=False,
            est_ajustement=False,
        )
        .annotate(jour=ExtractIsoWeekDay("date_flux"))
        .values("jour")
        .annotate(total=Sum("montant"), nb=Count("id"))
    )
    par_jour = {ligne["jour"]: ligne for ligne in lignes}

    resultat = []
    for jour in range(1, 8):
        ligne = par_jour.get(jour)
        total = -(ligne["total"]) if ligne else ZERO
        nb = ligne["nb"] if ligne else 0
        resultat.append({
            "jour": jour,
            "total": total,
            "nb": nb,
            "moyenne": (total / nb).quantize(CENT) if nb else ZERO,
        })
    return resultat


def _normaliser_libelle(libelle: str) -> str:
    """Clé de regroupement : minuscules, espaces normalisés."""
    return " ".join((libelle or "").lower().split())


def _libelles_recurrents(mois_labels: list, limite: int = 15) -> list:
    """
    Postes de dépense qui reviennent (≥ 2 occurrences sur la période),
    regroupés par libellé normalisé, triés par montant cumulé décroissant.
    Purement descriptif — aide à repérer les habitudes, sans jugement.
    """
    from flux.models import Flux

    lignes = Flux.objects.filter(
        mois__in=mois_labels,
        montant__lt=0,
        est_transfert=False,
        est_ajustement=False,
    ).values_list("libelle", "montant")

    groupes = {}
    for libelle, montant in lignes:
        cle = _normaliser_libelle(libelle)
        if not cle:
            continue
        groupe = groupes.setdefault(
            cle, {"libelle": libelle, "occurrences": 0, "total": ZERO}
        )
        groupe["occurrences"] += 1
        groupe["total"] += -montant

    recurrents = [g for g in groupes.values() if g["occurrences"] >= 2]
    for groupe in recurrents:
        groupe["moyenne"] = (groupe["total"] / groupe["occurrences"]).quantize(CENT)
    recurrents.sort(key=lambda x: x["total"], reverse=True)
    return recurrents[:limite]


def _bloc_rythme(mois_labels: list) -> dict:
    return {
        "definition": (
            "Rythme des dépenses : répartition par jour de semaine et postes "
            "récurrents (libellés revenant au moins deux fois sur la période). "
            "Fiabilité réelle, descriptif — aucun jugement ni seuil."
        ),
        "fiabilite": "reel",
        "par_jour_semaine": _par_jour_semaine(mois_labels),
        "libelles_recurrents": _libelles_recurrents(mois_labels),
    }


# --------------------------------------------------------------------------
# Bloc « saisonnalité » (comparaison année sur année)
# --------------------------------------------------------------------------
def _bloc_saisonnalite(mois_courant: datetime.date) -> dict:
    """
    Comparaison année sur année (YoY) sur TOUT l'historique : pour chaque mois
    comptable clôturé, dépenses de ce mois vs celles du même mois un an avant.

    Le mois courant est exclu (partiel → un YoY dessus serait trompeur). Un
    mois n'apparaît que si son homologue année-1 est dans l'historique.
    `variation_pct` = None si l'année précédente est nulle. Fiabilité réelle ;
    transferts et ajustements exclus.
    """
    from flux.models import Flux

    lignes = (
        Flux.objects.filter(
            montant__lt=0, est_transfert=False, est_ajustement=False
        )
        .values("mois")
        .annotate(total=Sum("montant"))
    )
    depenses_par_mois = {row["mois"]: -row["total"] for row in lignes}

    comparaisons = []
    if depenses_par_mois:
        premier = min(depenses_par_mois)
        mois = premier
        while mois < mois_courant:  # mois clôturés uniquement
            an_precedent = mois - relativedelta(years=1)
            if an_precedent >= premier:
                dep = depenses_par_mois.get(mois, ZERO)
                dep_prec = depenses_par_mois.get(an_precedent, ZERO)
                variation = (
                    ((dep - dep_prec) / dep_prec * 100).quantize(DIX)
                    if dep_prec > 0 else None
                )
                comparaisons.append({
                    "mois": mois.isoformat(),
                    "depenses": dep,
                    "depenses_an_precedent": dep_prec,
                    "variation_pct": variation,
                })
            mois += relativedelta(months=1)

    return {
        "definition": (
            "Comparaison année sur année : dépenses de chaque mois comptable "
            "clôturé face au même mois un an plus tôt. Le mois en cours "
            "(partiel) est exclu. Descriptif, sans jugement ni seuil ; "
            "fiabilité réelle."
        ),
        "fiabilite": "reel",
        "comparaisons": comparaisons,
    }


# --------------------------------------------------------------------------
# Bloc « epargne » (épargne réellement mise de côté)
# --------------------------------------------------------------------------
def _bloc_epargne(mois_labels: list) -> dict:
    """
    Épargne RÉELLEMENT mise de côté, mesurée par les **versements nets** vers
    les comptes marqués `est_epargne` : Σ(montant des flux de transfert sur ces
    comptes) par mois (entrées +, sorties −). À distinguer de l'« épargne nette »
    budgétaire (revenus − dépenses) du bloc tendances : ici c'est l'argent
    effectivement transféré sur un livret.

    - `encours_total`      : solde actuel cumulé des comptes d'épargne (stock) ;
    - `versements_par_mois`: versement net + cumul, mois par mois (fenêtre) ;
    - `ecart_budgetaire`   : par mois, épargne budgétaire (rev − dép) vs
                             versement réel — révèle si le « reste » finit épargné ;
    - `par_compte`         : par livret, encours + versements sur la période + taux.

    Le taux est renvoyé (informatif) mais n'entre PAS dans les mesures : la
    projection des intérêts est prévue côté prévisionnel (à venir). Fiabilité
    réelle. Les transferts entre deux comptes d'épargne se neutralisent (un −,
    un +), donc ne gonflent pas les versements.
    """
    from comptes.models import Compte
    from flux.models import Flux

    comptes = list(Compte.objects.filter(est_epargne=True))
    encours_total = sum((c.solde_theorique for c in comptes), ZERO)

    # Versements nets par mois (tous comptes d'épargne confondus).
    versements = {
        row["mois"]: (row["net"] or ZERO)
        for row in (
            Flux.objects.filter(
                est_transfert=True, compte__est_epargne=True, mois__in=mois_labels
            )
            .values("mois")
            .annotate(net=Sum("montant"))
        )
    }

    versements_par_mois, cumul = [], ZERO
    serie_budget = {p["mois"]: p for p in _serie_mensuelle(mois_labels)}
    ecart_budgetaire = []
    for mois in mois_labels:
        net = versements.get(mois, ZERO)
        cumul += net
        versements_par_mois.append({
            "mois": mois.isoformat(),
            "versement_net": net,
            "cumul": cumul,
        })
        budget = serie_budget[mois.isoformat()]
        ecart_budgetaire.append({
            "mois": mois.isoformat(),
            "epargne_budgetaire": budget["epargne_nette"],
            "versement_reel": net,
        })

    # Versements par compte sur la période.
    versements_compte = {
        row["compte"]: (row["net"] or ZERO)
        for row in (
            Flux.objects.filter(
                est_transfert=True, compte__est_epargne=True, mois__in=mois_labels
            )
            .values("compte")
            .annotate(net=Sum("montant"))
        )
    }
    par_compte = [
        {
            "id": str(c.id),
            "nom": c.nom,
            "taux_annuel": c.taux_annuel,
            "encours": c.solde_theorique,
            "versements_nets": versements_compte.get(c.id, ZERO),
        }
        for c in sorted(comptes, key=lambda x: x.solde_theorique, reverse=True)
    ]

    return {
        "definition": (
            "Épargne réellement mise de côté = versements nets (transferts) vers "
            "les comptes d'épargne, à distinguer de l'épargne budgétaire "
            "(revenus − dépenses). Encours = solde actuel des livrets. Le taux "
            "est informatif (projection des intérêts à venir). Fiabilité réelle."
        ),
        "fiabilite": "reel",
        "encours_total": encours_total,
        "versements_par_mois": versements_par_mois,
        "ecart_budgetaire": ecart_budgetaire,
        "par_compte": par_compte,
    }


# --------------------------------------------------------------------------
# Point d'entrée
# --------------------------------------------------------------------------
def calculer_analyse(nb_mois: int = 6, aujourd_hui: datetime.date = None) -> dict:
    """
    Agrège les trois blocs de la vue Analyse sur une fenêtre glissante de
    ``nb_mois`` mois comptables se terminant au mois courant. Lecture seule,
    fiabilité réelle. ``aujourd_hui`` injectable pour des tests déterministes.
    """
    from core.services.periode import mois_comptable_courant

    aujourd_hui = aujourd_hui or datetime.date.today()
    mois_fin = mois_comptable_courant(aujourd_hui)
    mois_labels = _fenetre_mois(nb_mois, mois_fin)
    mois_precedents = _fenetre_mois(nb_mois, mois_fin - relativedelta(months=nb_mois))

    return {
        "nb_mois": nb_mois,
        "mois_debut": mois_labels[0].isoformat(),
        "mois_fin": mois_labels[-1].isoformat(),
        "fiabilite": "reel",
        "tendances": _bloc_tendances(mois_labels, mois_precedents),
        "epargne": _bloc_epargne(mois_labels),
        "titulaires": _bloc_titulaires(mois_labels),
        "categories": _bloc_categories(mois_labels),
        "rythme": _bloc_rythme(mois_labels),
        "saisonnalite": _bloc_saisonnalite(mois_fin),
    }

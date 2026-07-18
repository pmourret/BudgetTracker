"""
Service d'analyse des transferts internes — lecture seule.

Vue analytique dédiée aux virements entre comptes du foyer : *combien* circule,
*d'où vers où* (graphe nœud-lien), et *quand* (volume par mois). Sert notamment
à visualiser l'alimentation de l'épargne (courant → livret) au fil du temps.

Base de calcul : les paires ``Transfert`` (débit/crédit atomiques) réellement
enregistrées → fiabilité **RÉELLE**. Les transferts ne sont ni des dépenses ni
des revenus (règle métier 4) : ils ne pèsent sur aucun agrégat dépenses/revenus,
et cette vue les traite comme un flux d'argent *interne* au patrimoine bancaire.

Toutes les bornes mensuelles passent par ``core/services/periode.py`` (mois
comptable, règle §4.3) : filtrer par ``flux_debit.mois`` est auto-correct.
Le service accepte ``aujourd_hui`` injectable pour des tests déterministes.
Ne modifie rien, ne génère aucune alerte.
"""
import datetime
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db.models import Count, Sum

from core.services.periode import mois_comptable_courant

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def _fenetre_mois(nb_mois: int, mois_fin: datetime.date) -> list:
    """Labels des mois comptables de la fenêtre [premier … mois_fin]."""
    premier = mois_fin - relativedelta(months=nb_mois - 1)
    mois, curseur = [], premier
    while curseur <= mois_fin:
        mois.append(curseur)
        curseur += relativedelta(months=1)
    return mois


def calculer_transferts(nb_mois: int = 6, aujourd_hui: datetime.date = None) -> dict:
    """
    Agrège les transferts internes sur une fenêtre glissante de mois comptables.

    Renvoie :
    - ``periode``   : bornes de la fenêtre (mois comptables) ;
    - ``synthese``  : volume total, nb de virements, nb de comptes, moyenne/mois ;
    - ``noeuds``    : comptes impliqués (entrant / sortant / solde net des virements) ;
    - ``liens``     : arêtes source→destination (total + nb) pour le graphe fléché ;
    - ``par_mois``  : volume et nombre de virements par mois comptable.
    """
    from transferts.models import Transfert

    mois_fin = mois_comptable_courant(aujourd_hui)
    mois_labels = _fenetre_mois(nb_mois, mois_fin)

    base = Transfert.objects.filter(flux_debit__mois__in=mois_labels)

    # --- Liens (arêtes du graphe) : agrégation par paire (source, destination) ---
    paires = (
        base.values(
            "flux_debit__compte__id",
            "flux_debit__compte__nom",
            "flux_credit__compte__id",
            "flux_credit__compte__nom",
        )
        .annotate(total=Sum("montant"), nb=Count("id"))
        .order_by("-total")
    )

    liens = []
    noeuds = {}

    def _noeud(cid, nom):
        if cid not in noeuds:
            noeuds[cid] = {
                "id": str(cid),
                "nom": nom,
                "entrant": ZERO,
                "sortant": ZERO,
                "nb": 0,
            }
        return noeuds[cid]

    total_global = ZERO
    nb_global = 0
    for p in paires:
        src_id = p["flux_debit__compte__id"]
        dst_id = p["flux_credit__compte__id"]
        total = (p["total"] or ZERO).quantize(CENT)
        nb = p["nb"]
        liens.append({
            "source": str(src_id),
            "source_nom": p["flux_debit__compte__nom"],
            "destination": str(dst_id),
            "destination_nom": p["flux_credit__compte__nom"],
            "total": total,
            "nb": nb,
        })
        src = _noeud(src_id, p["flux_debit__compte__nom"])
        dst = _noeud(dst_id, p["flux_credit__compte__nom"])
        src["sortant"] += total
        src["nb"] += nb
        dst["entrant"] += total
        dst["nb"] += nb
        total_global += total
        nb_global += nb

    # Enrichissement des nœuds (établissement / drapeaux) + solde net.
    _enrichir_noeuds(noeuds)
    noeuds_liste = sorted(
        noeuds.values(),
        key=lambda n: n["entrant"] + n["sortant"],
        reverse=True,
    )
    for n in noeuds_liste:
        n["solde_net"] = (n["entrant"] - n["sortant"]).quantize(CENT)

    # --- Volume par mois ---
    par_mois_brut = {
        row["flux_debit__mois"]: row
        for row in base.values("flux_debit__mois").annotate(
            total=Sum("montant"), nb=Count("id")
        )
    }
    par_mois = []
    for mois in mois_labels:
        row = par_mois_brut.get(mois, {})
        par_mois.append({
            "mois": mois.isoformat(),
            "total": (row.get("total") or ZERO).quantize(CENT),
            "nb": row.get("nb", 0),
        })

    moyenne = (total_global / Decimal(nb_mois)).quantize(CENT) if nb_mois else ZERO

    return {
        "periode": {
            "debut": mois_labels[0].isoformat(),
            "fin": mois_labels[-1].isoformat(),
            "nb_mois": nb_mois,
        },
        "synthese": {
            "total": total_global.quantize(CENT),
            "nb": nb_global,
            "nb_comptes": len(noeuds_liste),
            "moyenne_mensuelle": moyenne,
        },
        "noeuds": noeuds_liste,
        "liens": liens,
        "par_mois": par_mois,
        "fiabilite": "reelle",
    }


def _enrichir_noeuds(noeuds: dict) -> None:
    """Ajoute établissement + drapeaux (commun / épargne) sur chaque nœud."""
    if not noeuds:
        return
    from comptes.models import Compte

    infos = (
        Compte.objects.filter(id__in=list(noeuds.keys()))
        .select_related("etablissement")
        .values("id", "etablissement__libelle", "est_commun", "est_epargne")
    )
    for info in infos:
        n = noeuds.get(info["id"])
        if n is None:
            continue
        n["etablissement"] = info["etablissement__libelle"]
        n["est_commun"] = info["est_commun"]
        n["est_epargne"] = info["est_epargne"]
    # Comptes soft-deletés éventuels : valeurs par défaut.
    for n in noeuds.values():
        n.setdefault("etablissement", None)
        n.setdefault("est_commun", False)
        n.setdefault("est_epargne", False)

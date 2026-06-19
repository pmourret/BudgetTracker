from decimal import Decimal
import datetime

from django.db.models import Sum

from .dashboard import _calculer_depenses_par_categorie


def _mois_courant(aujourd_hui: datetime.date) -> datetime.date:
    return aujourd_hui.replace(day=1)


def calculer_compte_dashboard(compte_id, aujourd_hui: datetime.date = None) -> dict:
    """
    Dashboard scopé à un seul compte — lecture seule, fiabilité RÉELLE.

    Tous les agrégats (dépenses/revenus du mois, ventilation par catégorie,
    top dépenses) sont restreints aux flux de ce compte et excluent les
    transferts et les ajustements (règle métier 4). Les soldes du compte
    (théorique/réel/écart) sont lus tels quels — ils sont calculés ailleurs
    (comptes/services/solde.py) et ne sont jamais recalculés ici.

    `aujourd_hui` est injectable pour des tests déterministes.

    Lève `Compte.DoesNotExist` si le compte n'existe pas (404 côté view).
    """
    from comptes.models import Compte
    from flux.models import Flux

    if aujourd_hui is None:
        aujourd_hui = datetime.date.today()
    mois_courant = _mois_courant(aujourd_hui)

    compte = Compte.objects.select_related(
        "etablissement", "type_compte", "titulaire"
    ).get(id=compte_id)

    # --- Flux du mois courant pour ce compte (hors transferts/ajustements) ---
    flux_mois = Flux.objects.filter(
        compte_id=compte_id,
        mois=mois_courant,
        est_transfert=False,
        est_ajustement=False,
    )

    depenses = (
        flux_mois.filter(montant__lt=0).aggregate(t=Sum("montant"))["t"]
        or Decimal("0.00")
    )
    revenus = (
        flux_mois.filter(montant__gt=0).aggregate(t=Sum("montant"))["t"]
        or Decimal("0.00")
    )
    epargne_nette = revenus + depenses  # depenses est négatif
    nb_flux = flux_mois.count()

    # --- Top 5 dépenses du mois (la plus négative en premier) ---
    top_depenses = list(
        flux_mois.filter(montant__lt=0)
        .select_related("categorie")
        .order_by("montant")[:5]
    )
    top_depenses_data = [
        {
            "id": str(f.id),
            "libelle": f.libelle,
            "montant": f.montant,
            "date_flux": f.date_flux,
            "categorie_nom": f.categorie.nom if f.categorie else None,
        }
        for f in top_depenses
    ]

    return {
        "mois_courant": mois_courant.isoformat(),
        "compte": {
            "id": str(compte.id),
            "nom": compte.nom,
            "etablissement_libelle": (
                compte.etablissement.libelle if compte.etablissement else None
            ),
            "type_compte_libelle": (
                compte.type_compte.libelle if compte.type_compte else None
            ),
            "titulaire_libelle": (
                compte.titulaire.libelle if compte.titulaire else None
            ),
            "solde_theorique": compte.solde_theorique,
            "solde_reel": compte.solde_reel,
            "ecart_solde": compte.ecart_solde,
            "est_commun": compte.est_commun,
            "actif": compte.actif,
        },
        "metriques": {
            "depenses_mois": abs(depenses),
            "revenus_mois": revenus,
            "epargne_nette": epargne_nette,
            "nb_flux": nb_flux,
            "fiabilite": "reel",
        },
        "depenses_par_categorie": _calculer_depenses_par_categorie(
            mois_courant, compte_id=compte_id
        ),
        "top_depenses": top_depenses_data,
    }

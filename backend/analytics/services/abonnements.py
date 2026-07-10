"""
Service d'analyse des abonnements — lecture seule.

Vue analytique dédiée aux prélèvements récurrents : *combien* ils coûtent
(mensuel + annuel), *par catégorie*, *qui paye quoi*, leur *poids* dans le
budget réel, et les signaux de *dérive de prix* / *risque*.

Base de calcul : le **référentiel** `Abonnement` (montant_attendu normalisé).
Ces montants sont donc de fiabilité **estimative** (saisis à la main, décrivent
le plan de prélèvements), à distinguer du réel. Deux blocs croisent le réel :
`derive_prix` et `a_risque` s'appuient sur les flux réellement générés
(FK `Flux.abonnement`) et sont de fiabilité **réelle**.

Périmètre : seuls les abonnements de **dépense** (`montant_attendu < 0`) sont
agrégés dans les coûts — les revenus récurrents (salaire, loyer perçu) sont un
autre sujet et ne « pèsent » pas sur les finances au sens de ce module.
Seuls les abonnements **actifs** entrent dans la synthèse/catégories/titulaires.

Toutes les bornes mensuelles passent par ``core/services/periode.py`` (mois
comptable). ``aujourd_hui`` est injectable pour des tests déterministes.
Ne modifie rien, ne génère aucune alerte.
"""
import datetime
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db.models import Q, Sum

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
DIX = Decimal("0.1")

# Jours moyens pour normaliser une fréquence quelconque en mensuel / annuel.
JOURS_PAR_MOIS = Decimal("30.4375")   # 365.25 / 12
JOURS_PAR_AN = Decimal("365.25")


# --------------------------------------------------------------------------
# Normalisation d'un abonnement
# --------------------------------------------------------------------------
def _cout_mensuel(montant_abs: Decimal, nb_jours) -> Decimal:
    """Coût ramené au mois. None si la fréquence n'a pas de nb_jours."""
    if not nb_jours:
        return None
    return (montant_abs * JOURS_PAR_MOIS / Decimal(nb_jours)).quantize(CENT)


def _cout_annuel(montant_abs: Decimal, nb_jours) -> Decimal:
    """Coût ramené à l'année. None si la fréquence n'a pas de nb_jours."""
    if not nb_jours:
        return None
    return (montant_abs * JOURS_PAR_AN / Decimal(nb_jours)).quantize(CENT)


def _normaliser(abo) -> dict:
    """
    Représentation enrichie d'un abonnement de dépense : coûts normalisés
    (mensuel/annuel) + libellés lisibles. `cout_mensuel`/`cout_annuel` valent
    None si la fréquence est ponctuelle (nb_jours nul → non récurrente).
    """
    montant_abs = abs(abo.montant_attendu)
    nb_jours = abo.frequence.nb_jours
    compte = abo.compte
    return {
        "id": str(abo.id),
        "nom": abo.nom,
        "montant_attendu": abo.montant_attendu,
        "frequence_libelle": abo.frequence.libelle,
        "categorie_id": str(abo.categorie_id) if abo.categorie_id else None,
        "compte_nom": compte.nom,
        "cout_mensuel": _cout_mensuel(montant_abs, nb_jours),
        "cout_annuel": _cout_annuel(montant_abs, nb_jours),
    }


def _part(valeur: Decimal, total: Decimal) -> Decimal:
    """Part en % (1 décimale), 0 si total nul."""
    if total and total > 0:
        return (valeur / total * 100).quantize(DIX)
    return Decimal("0.0")


# --------------------------------------------------------------------------
# Bloc « synthese » (coût normalisé #1 + poids budget #4)
# --------------------------------------------------------------------------
def _moyennes_reelles(nb_mois: int, mois_fin: datetime.date) -> dict:
    """
    Dépenses et revenus réels moyens par mois sur la fenêtre glissante, pour
    situer le poids des abonnements. Transferts et ajustements exclus.
    """
    from flux.models import Flux

    premier = mois_fin - relativedelta(months=nb_mois - 1)
    labels = []
    curseur = premier
    while curseur <= mois_fin:
        labels.append(curseur)
        curseur += relativedelta(months=1)

    agg = Flux.objects.filter(
        mois__in=labels, est_transfert=False, est_ajustement=False
    ).aggregate(
        depenses=Sum("montant", filter=Q(montant__lt=0)),
        revenus=Sum("montant", filter=Q(montant__gt=0)),
    )
    depenses = -(agg["depenses"] or ZERO)
    revenus = agg["revenus"] or ZERO
    nb = len(labels)
    return {
        "depenses_mensuelles_moy": (depenses / nb).quantize(CENT),
        "revenus_mensuels_moy": (revenus / nb).quantize(CENT),
    }


def _bloc_synthese(normalises: list, nb_mois: int, mois_fin: datetime.date) -> dict:
    recurrents = [a for a in normalises if a["cout_mensuel"] is not None]
    total_mensuel = sum((a["cout_mensuel"] for a in recurrents), ZERO)
    total_annuel = sum((a["cout_annuel"] for a in recurrents), ZERO)

    moy = _moyennes_reelles(nb_mois, mois_fin)
    depenses_moy = moy["depenses_mensuelles_moy"]
    revenus_moy = moy["revenus_mensuels_moy"]

    top = sorted(recurrents, key=lambda a: a["cout_mensuel"], reverse=True)

    return {
        "definition": (
            "Coût des abonnements actifs ramené au mois et à l'année (via la "
            "fréquence). Le « poids » situe ce total récurrent face aux dépenses "
            "et revenus réels moyens des derniers mois. Base référentiel → "
            "fiabilité estimative ; les moyennes réelles sont, elles, réelles."
        ),
        "fiabilite": "estimatif",
        "nb_actifs": len(normalises),
        "nb_recurrents": len(recurrents),
        "total_mensuel": total_mensuel,
        "total_annuel": total_annuel,
        "depenses_mensuelles_moy": depenses_moy,
        "revenus_mensuels_moy": revenus_moy,
        "poids_depenses_pct": _part(total_mensuel, depenses_moy),
        "poids_revenus_pct": _part(total_mensuel, revenus_moy),
        "abonnements": top,
    }


# --------------------------------------------------------------------------
# Bloc « par_categorie » (#2)
# --------------------------------------------------------------------------
def _bloc_par_categorie(abos_actifs: list, normalises_par_id: dict) -> dict:
    """
    Coût mensuel/annuel regroupé par catégorie **majeure** (les mineures sont
    regroupées sous leur parent, comme dans l'Analyse). Les abonnements sans
    catégorie forment un bucket « Sans catégorie ».
    """
    majeures = {}
    for abo in abos_actifs:
        norm = normalises_par_id[str(abo.id)]
        if norm["cout_mensuel"] is None:
            continue

        cat = abo.categorie
        if cat is None:
            key, nom = "sans", "Sans catégorie"
        elif cat.parent_id is None:
            key, nom = str(cat.id), cat.nom
        else:
            key, nom = str(cat.parent_id), cat.parent.nom

        maj = majeures.setdefault(
            key,
            {"id": key, "nom": nom, "total_mensuel": ZERO,
             "total_annuel": ZERO, "nb": 0},
        )
        maj["total_mensuel"] += norm["cout_mensuel"]
        maj["total_annuel"] += norm["cout_annuel"]
        maj["nb"] += 1

    total_mensuel = sum((m["total_mensuel"] for m in majeures.values()), ZERO)

    par_categorie = []
    for maj in sorted(majeures.values(), key=lambda x: x["total_mensuel"], reverse=True):
        par_categorie.append({
            **maj,
            "part_pct": _part(maj["total_mensuel"], total_mensuel),
        })

    return {
        "definition": (
            "Coût mensuel et annuel des abonnements actifs regroupés par "
            "catégorie majeure (mineures agrégées sous leur parent). Répond à "
            "« combien je paye en streaming / télécoms / assurances ». "
            "Fiabilité estimative (référentiel)."
        ),
        "fiabilite": "estimatif",
        "total_mensuel": total_mensuel,
        "par_categorie": par_categorie,
    }


# --------------------------------------------------------------------------
# Bloc « par_titulaire » (#3 — qui paye quoi)
# --------------------------------------------------------------------------
def _bloc_par_titulaire(abos_actifs: list, normalises_par_id: dict) -> dict:
    """
    Coût des abonnements ventilé par personne du foyer, selon le propriétaire
    du compte prélevé (`compte.titulaire`). Les comptes communs (`est_commun`)
    forment un bucket « Commun » distinct — jamais rattaché à une personne
    (arbitrage foyer, cohérent avec l'Analyse). Fiabilité estimative.
    """
    buckets = {}
    for abo in abos_actifs:
        norm = normalises_par_id[str(abo.id)]
        if norm["cout_mensuel"] is None:
            continue

        compte = abo.compte
        if compte.est_commun:
            key, nom, est_commun = "commun", "Commun", True
        else:
            key = str(compte.titulaire_id)
            nom = compte.titulaire.libelle
            est_commun = False

        bucket = buckets.setdefault(
            key,
            {"id": key, "nom": nom, "est_commun": est_commun,
             "total_mensuel": ZERO, "total_annuel": ZERO, "nb": 0},
        )
        bucket["total_mensuel"] += norm["cout_mensuel"]
        bucket["total_annuel"] += norm["cout_annuel"]
        bucket["nb"] += 1

    total_mensuel = sum((b["total_mensuel"] for b in buckets.values()), ZERO)

    par_titulaire = []
    for bucket in sorted(buckets.values(), key=lambda x: x["total_mensuel"], reverse=True):
        par_titulaire.append({
            **bucket,
            "part_pct": _part(bucket["total_mensuel"], total_mensuel),
        })

    return {
        "definition": (
            "Coût des abonnements ventilé par personne du foyer (propriétaire "
            "du compte prélevé). Les comptes communs forment un groupe "
            "« Commun » à part. Fiabilité estimative (référentiel)."
        ),
        "fiabilite": "estimatif",
        "total_mensuel": total_mensuel,
        "par_titulaire": par_titulaire,
    }


# --------------------------------------------------------------------------
# Blocs « derive_prix » (#6) et « a_risque » (#7) — croisent le réel
# --------------------------------------------------------------------------
def _dernier_flux(abo):
    """Flux réel le plus récent rattaché à l'abonnement (None si aucun)."""
    return abo.flux.order_by("-date_flux", "-created_at").first()


def _est_en_retard(abo, aujourd_hui: datetime.date) -> bool:
    """
    Vrai si aucun flux depuis plus d'un cycle. Recalculé ici (plutôt que via
    la propriété du modèle) pour rester déterministe avec `aujourd_hui`.
    """
    if not abo.actif or not abo.derniere_occurrence:
        return False
    nb_jours = abo.frequence.nb_jours
    if not nb_jours:
        return False
    echeance = abo.derniere_occurrence + datetime.timedelta(days=nb_jours)
    return aujourd_hui > echeance


def _bloc_derive_prix(abos_actifs: list) -> dict:
    """
    Compare, pour chaque abonnement actif ayant au moins un flux réel, le
    dernier montant prélevé au montant attendu → révèle les hausses de tarif
    silencieuses. `en_divergence` si l'écart dépasse le seuil de l'abonnement.
    Fiabilité réelle (basée sur les flux générés).
    """
    par_abonnement = []
    for abo in abos_actifs:
        dernier = _dernier_flux(abo)
        if dernier is None:
            continue

        attendu = abs(abo.montant_attendu)
        reel = abs(dernier.montant)
        if attendu > 0:
            ecart_pct = ((reel - attendu) / attendu * 100).quantize(DIX)
        else:
            ecart_pct = None
        seuil = abo.seuil_divergence_pct
        en_divergence = ecart_pct is not None and abs(ecart_pct) > seuil

        par_abonnement.append({
            "id": str(abo.id),
            "nom": abo.nom,
            "montant_attendu": abo.montant_attendu,
            "dernier_montant_reel": dernier.montant,
            "dernier_date": dernier.date_flux.isoformat(),
            "ecart_pct": ecart_pct,
            "en_divergence": en_divergence,
            "seuil_pct": seuil,
        })

    par_abonnement.sort(
        key=lambda x: abs(x["ecart_pct"]) if x["ecart_pct"] is not None else Decimal("0"),
        reverse=True,
    )

    return {
        "definition": (
            "Écart entre le dernier montant réellement prélevé et le montant "
            "attendu de l'abonnement — détecte les hausses de tarif "
            "silencieuses. « En divergence » quand l'écart dépasse le seuil "
            "configuré sur l'abonnement. Fiabilité réelle (flux générés)."
        ),
        "fiabilite": "reel",
        "par_abonnement": par_abonnement,
    }


def _bloc_a_risque(abos_actifs: list, derive: dict, aujourd_hui: datetime.date) -> dict:
    """
    Abonnements méritant l'attention, avec le(s) motif(s) : en retard de
    prélèvement, montant divergent, ou jamais matérialisé en flux (dormant).
    Purement signalétique — aucune alerte n'est créée. Fiabilité réelle.
    """
    divergents = {
        d["id"]: d["ecart_pct"]
        for d in derive["par_abonnement"] if d["en_divergence"]
    }

    a_risque = []
    for abo in abos_actifs:
        aid = str(abo.id)
        raisons = []
        if _est_en_retard(abo, aujourd_hui):
            raisons.append("en_retard")
        if aid in divergents:
            raisons.append("divergence_montant")
        if abo.derniere_occurrence is None:
            raisons.append("jamais_genere")

        if not raisons:
            continue

        montant_abs = abs(abo.montant_attendu)
        a_risque.append({
            "id": aid,
            "nom": abo.nom,
            "montant_attendu": abo.montant_attendu,
            "cout_mensuel": _cout_mensuel(montant_abs, abo.frequence.nb_jours),
            "raisons": raisons,
            "ecart_pct": divergents.get(aid),
            "derniere_occurrence": (
                abo.derniere_occurrence.isoformat()
                if abo.derniere_occurrence else None
            ),
        })

    # Les plus « chers » d'abord (impact potentiel le plus fort).
    a_risque.sort(
        key=lambda x: x["cout_mensuel"] or ZERO, reverse=True
    )

    return {
        "definition": (
            "Abonnements à surveiller : en retard de prélèvement, montant "
            "divergent du référentiel, ou jamais matérialisé en flux "
            "(potentiellement dormant/oublié). Signalétique, sans alerte ni "
            "jugement. Fiabilité réelle."
        ),
        "fiabilite": "reel",
        "a_risque": a_risque,
    }


# --------------------------------------------------------------------------
# Point d'entrée
# --------------------------------------------------------------------------
def calculer_abonnements(nb_mois: int = 6, aujourd_hui: datetime.date = None) -> dict:
    """
    Agrège les blocs d'analyse des abonnements. Lecture seule.

    - synthese / par_categorie / par_titulaire : base référentiel (estimatif),
      abonnements actifs de dépense uniquement ;
    - derive_prix / a_risque : croisent les flux réels (fiabilité réelle).

    ``nb_mois`` borne la fenêtre des moyennes réelles servant au « poids ».
    ``aujourd_hui`` injectable pour des tests déterministes.
    """
    from abonnements.models import Abonnement
    from core.services.periode import mois_comptable_courant

    aujourd_hui = aujourd_hui or datetime.date.today()
    mois_fin = mois_comptable_courant(aujourd_hui)

    abos_actifs = list(
        Abonnement.objects
        .filter(actif=True, montant_attendu__lt=0)
        .select_related("categorie", "categorie__parent", "compte",
                        "compte__titulaire", "frequence")
    )

    normalises = [_normaliser(a) for a in abos_actifs]
    normalises_par_id = {n["id"]: n for n in normalises}

    derive = _bloc_derive_prix(abos_actifs)

    return {
        "date_calcul": aujourd_hui.isoformat(),
        "nb_mois": nb_mois,
        "fiabilite": "estimatif",
        "synthese": _bloc_synthese(normalises, nb_mois, mois_fin),
        "par_categorie": _bloc_par_categorie(abos_actifs, normalises_par_id),
        "par_titulaire": _bloc_par_titulaire(abos_actifs, normalises_par_id),
        "derive_prix": derive,
        "a_risque": _bloc_a_risque(abos_actifs, derive, aujourd_hui),
    }

"""
Orchestration d'un import : fichier brut → lot persisté + rapprochement.

Chaîne : décoder → parser (provider) → vérifier mono-compte → anti-doublon
(vs tout l'historique du compte) → créer le lot + les lignes → lancer le
rapprochement. Aucun flux n'est créé ni modifié (14-A).
"""
from __future__ import annotations

from collections import Counter

from django.db import transaction

from ..models import Banque, ImportBancaire, LigneBancaire
from ..parsers import decoder_fichier, parser_boursobank
from .rapprochement import executer_rapprochement, filtrer_doublons

# Un parser par banque (providers isolés — règle §3).
PARSERS = {
    Banque.BOURSOBANK: parser_boursobank,
}


class FichierMultiCompteError(Exception):
    """Le fichier mélange plusieurs comptes (un import = un seul compte)."""

    def __init__(self, comptes):
        self.comptes = sorted(comptes)
        super().__init__(
            "Le fichier contient plusieurs comptes : " + ", ".join(self.comptes)
        )


class BanqueNonSupportee(Exception):
    """Aucun parser pour la banque demandée."""


class CompteIntrouvableError(Exception):
    """Aucun compte de l'app ne porte le numéro de compte du fichier."""

    def __init__(self, compte_num):
        self.compte_num = compte_num
        super().__init__(
            f"Aucun compte ne porte le numéro « {compte_num} ». Renseignez ce "
            "numéro sur le compte concerné (champ N° Compte), ou sélectionnez-le "
            "manuellement."
        )


def creer_import(compte, banque, contenu_bytes, nom_fichier=""):
    """
    Crée un lot d'import et lance le rapprochement. Renvoie un dict de synthèse.

    `compte` peut être None : il est alors résolu automatiquement via le numéro
    de compte du fichier (`accountNum` = `Compte.code`).

    Peut lever : FormatInvalideError (parser), FichierMultiCompteError,
    BanqueNonSupportee, CompteIntrouvableError — à traduire en 400 côté vue.
    """
    from comptes.models import Compte

    parser = PARSERS.get(banque)
    if parser is None:
        raise BanqueNonSupportee(banque)

    texte = decoder_fichier(contenu_bytes)
    resultat_parsing = parser(texte)  # peut lever FormatInvalideError

    if len(resultat_parsing.comptes_rencontres) > 1:
        raise FichierMultiCompteError(resultat_parsing.comptes_rencontres)
    compte_num = next(iter(resultat_parsing.comptes_rencontres), "")

    # Résolution automatique du compte par son numéro (code) si non fourni.
    if compte is None:
        compte = Compte.objects.filter(code=compte_num).first()
        if compte is None:
            raise CompteIntrouvableError(compte_num)

    # Anti-doublon : multiset des hash déjà connus pour CE compte (tous lots).
    hashes_existants = Counter(
        LigneBancaire.objects
        .filter(import_lot__compte=compte)
        .values_list("hash_dedup", flat=True)
    )
    nouvelles, nb_doublons = filtrer_doublons(
        resultat_parsing.lignes, hashes_existants
    )

    with transaction.atomic():
        lot = ImportBancaire.objects.create(
            compte=compte,
            banque=banque,
            nom_fichier=nom_fichier or "",
            compte_num_source=compte_num,
            nb_doublons_ignores=nb_doublons,
        )
        LigneBancaire.objects.bulk_create([
            LigneBancaire(
                import_lot=lot,
                date_operation=l.date_operation,
                date_valeur=l.date_valeur,
                libelle=l.libelle,
                libelle_suggere=l.libelle_suggere,
                categorie_banque=l.categorie_banque,
                categorie_parent_banque=l.categorie_parent_banque,
                montant=l.montant,
                commentaire=l.commentaire,
                solde_apres=l.solde_apres,
                pointe_banque=l.pointe_banque,
                hash_dedup=l.hash_dedup,
            )
            for l in nouvelles
        ])

    rapport = executer_rapprochement(lot)
    lot.refresh_from_db()
    return {
        "lot": lot,
        "rapport": rapport,
        "nb_doublons": nb_doublons,
        "erreurs_parsing": resultat_parsing.erreurs,
    }

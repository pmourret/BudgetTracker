"""
Parser de l'export CSV BoursoBank (« Mouvements »).

Colonnes attendues (séparateur ';', en-tête obligatoire) :
    dateOp;dateVal;label;suggestedLabel;category;categoryParent;amount;
    comment;accountNum;accountLabel;accountbalance;mark

Pièges de format encaissés ici :
  - décimale française (virgule) : "-56,15"
  - séparateur de milliers (espaces, y compris insécables) + guillemets :
    "-2 469,63", "1 850,00"
  - dates ISO sur deux colonnes (opération / valeur)
  - encodage variable (géré en amont par decoder_fichier)
"""
from __future__ import annotations

import csv
import io
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from .base import LigneBrute, ResultatParsing

# En-têtes de référence (ordre indifférent : on lit par nom via DictReader).
COLONNES_ATTENDUES = {
    "dateOp", "dateVal", "label", "suggestedLabel", "category",
    "categoryParent", "amount", "comment", "accountNum", "accountLabel",
    "accountbalance", "mark",
}

# Sépare les milliers : toute espace (normale, insécable U+00A0, fine U+202F…).
# `\s` en mode str (Unicode) les couvre toutes d'un coup.
_ESPACES_MILLIERS = re.compile(r"\s")


class FormatInvalideError(ValueError):
    """Le fichier ne ressemble pas à un export BoursoBank exploitable."""


def _nettoyer_montant(brut: str) -> Decimal:
    """
    '"-2 469,63"' -> Decimal('-2469.63').

    Retire guillemets et espaces (milliers), convertit la virgule décimale.
    """
    txt = brut.strip().strip('"').strip()
    txt = _ESPACES_MILLIERS.sub("", txt)
    txt = txt.replace(",", ".")
    try:
        return Decimal(txt)
    except InvalidOperation as exc:
        raise ValueError(f"montant illisible : {brut!r}") from exc


def _nettoyer_solde(brut: str) -> Decimal | None:
    """Comme _nettoyer_montant mais tolère une valeur vide (-> None)."""
    if not brut or not brut.strip():
        return None
    return _nettoyer_montant(brut)


def _parser_date(brut: str) -> date:
    return date.fromisoformat(brut.strip())


def parser_boursobank(texte: str) -> ResultatParsing:
    """
    Parse le contenu texte d'un export BoursoBank en `ResultatParsing`.

    Fonction pure (aucune dépendance Django) → testable en isolation.
    Les lignes illisibles n'interrompent pas le parsing : elles sont
    collectées dans `erreurs` (rapport, pas exception).
    """
    flux = io.StringIO(texte)
    lecteur = csv.DictReader(flux, delimiter=";")

    if lecteur.fieldnames is None:
        raise FormatInvalideError("Fichier vide ou sans en-tête.")

    entetes = {h.strip() for h in lecteur.fieldnames}
    manquantes = COLONNES_ATTENDUES - entetes
    if manquantes:
        raise FormatInvalideError(
            "Colonnes manquantes : " + ", ".join(sorted(manquantes))
        )

    lignes: list[LigneBrute] = []
    erreurs: list[str] = []
    comptes: set[str] = set()

    # start=2 : ligne 1 = en-tête, on numérote comme dans un tableur.
    for numero, brut in enumerate(lecteur, start=2):
        try:
            ligne = LigneBrute(
                date_operation=_parser_date(brut["dateOp"]),
                date_valeur=_parser_date(brut["dateVal"]),
                libelle=(brut.get("label") or "").strip(),
                libelle_suggere=(brut.get("suggestedLabel") or "").strip(),
                categorie_banque=(brut.get("category") or "").strip(),
                categorie_parent_banque=(brut.get("categoryParent") or "").strip(),
                montant=_nettoyer_montant(brut["amount"]),
                commentaire=(brut.get("comment") or "").strip(),
                compte_num=(brut.get("accountNum") or "").strip(),
                compte_libelle=(brut.get("accountLabel") or "").strip(),
                solde_apres=_nettoyer_solde(brut.get("accountbalance", "")),
                pointe_banque=(brut.get("mark") or "").strip().lower() == "oui",
            )
        except (ValueError, KeyError) as exc:
            erreurs.append(f"Ligne {numero} ignorée : {exc}")
            continue

        lignes.append(ligne)
        if ligne.compte_num:
            comptes.add(ligne.compte_num)

    return ResultatParsing(lignes=lignes, erreurs=erreurs, comptes_rencontres=comptes)

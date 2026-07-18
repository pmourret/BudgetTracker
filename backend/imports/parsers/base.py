"""
Format normalisé partagé par tous les parsers bancaires.

Le moteur de rapprochement (brique ③) ne travaille QUE sur des `LigneBrute` :
c'est le contrat commun, indépendant de la banque d'origine.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class LigneBrute:
    """
    Une ligne d'un relevé bancaire, normalisée (format pivot).

    Purement représentative des données de la BANQUE : aucune notion de flux
    applicatif ici. Le montant est signé (négatif = débit, positif = crédit),
    comme les Flux de l'app (règle §4.2).
    """

    date_operation: date
    date_valeur: date
    libelle: str                 # label brut de la banque
    libelle_suggere: str         # suggestedLabel (nettoyé par la banque)
    categorie_banque: str        # category (indicatif, jamais utilisé pour matcher)
    categorie_parent_banque: str # categoryParent
    montant: Decimal             # signé
    commentaire: str
    compte_num: str              # accountNum brut de la banque
    compte_libelle: str          # accountLabel
    solde_apres: Decimal | None  # accountbalance = solde du compte après l'opération
    pointe_banque: bool          # mark == "Oui" (pointage côté banque)

    # Empreinte de dé-duplication : identifie une ligne de relevé de façon
    # stable entre deux exports qui se chevauchent (BoursoBank ne fournit
    # aucun ID de transaction). Voir hash_dedup().
    hash_dedup: str = field(default="", init=False)

    def __post_init__(self):
        self.hash_dedup = self._calculer_hash()

    def _calculer_hash(self) -> str:
        """
        Empreinte reproductible d'une ligne de relevé.

        On inclut le solde après opération : il départage deux mouvements
        identiques (même date, même montant, même libellé) survenus le même
        jour, car le solde courant diffère forcément entre les deux.
        """
        base = "|".join([
            self.compte_num,
            self.date_operation.isoformat(),
            f"{self.montant:.2f}",
            self.libelle.strip().lower(),
            "" if self.solde_apres is None else f"{self.solde_apres:.2f}",
        ])
        return hashlib.sha1(base.encode("utf-8")).hexdigest()


@dataclass
class ResultatParsing:
    """Retour d'un parser : lignes valides + anomalies non bloquantes."""

    lignes: list[LigneBrute]
    erreurs: list[str] = field(default_factory=list)
    # Numéros de compte distincts rencontrés — sert à avertir si le fichier
    # mélange plusieurs comptes (mapping manuel = un import → un compte).
    comptes_rencontres: set[str] = field(default_factory=set)


def decoder_fichier(contenu: bytes) -> str:
    """
    Décode un fichier CSV bancaire en texte.

    BoursoBank exporte tantôt en UTF-8 (parfois avec BOM), tantôt en
    Windows-1252 (héritage). On essaie dans l'ordre le plus probable ;
    cp1252 accepte tous les octets, donc c'est un filet de sécurité qui
    ne lève jamais (au pire, accents dégradés — signalé en amont).
    """
    for encodage in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return contenu.decode(encodage)
        except UnicodeDecodeError:
            continue
    # cp1252 ne devrait jamais échouer ; garde-fou explicite.
    return contenu.decode("cp1252", errors="replace")

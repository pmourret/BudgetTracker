"""
Parsers d'exports bancaires — providers isolés (règle §3).

Chaque banque a son format propre. Le moteur de rapprochement ne connaît que
le format normalisé `LigneBrute` ; ajouter une banque = ajouter un parser ici,
sans toucher au moteur.
"""
from .base import LigneBrute, ResultatParsing, decoder_fichier
from .boursobank import parser_boursobank

__all__ = [
    "LigneBrute",
    "ResultatParsing",
    "decoder_fichier",
    "parser_boursobank",
]

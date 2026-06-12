from django.core.management.base import BaseCommand
from django.db import transaction

from referentiels.models import (
    TypeCompte, TypeFlux, Titulaire, ModePaiement,
    Frequence, Etablissement, Devise, Fiscalite, StatutFlux
)


class Command(BaseCommand):
    help = (
        "Crée les référentiels structurels indispensables au fonctionnement de "
        "l'application (9 référentiels). Idempotente : relançable sans danger ni "
        "doublon. NE crée AUCUNE donnée métier (compte, catégorie, flux...). "
        "Destinée à la prod (l'appli démarre vierge de données métier mais avec "
        "ses référentiels structurels)."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Création des référentiels structurels...")

        # --- Devise (défaut) ---
        Devise.objects.get_or_create(
            code="EUR",
            defaults={"libelle": "Euro", "symbole": "€", "est_defaut": True, "ordre": 1},
        )

        # --- Types de compte ---
        TypeCompte.objects.get_or_create(
            code="COURANT", defaults={"libelle": "Compte courant", "ordre": 1}
        )
        TypeCompte.objects.get_or_create(
            code="EPARGNE", defaults={"libelle": "Compte épargne", "ordre": 2}
        )

        # --- Titulaires ---
        Titulaire.objects.get_or_create(
            code="PIERRE", defaults={"libelle": "Pierre", "ordre": 1}
        )

        # --- Établissements ---
        Etablissement.objects.get_or_create(
            code="BOURSOBANK", defaults={"libelle": "BoursoBank", "ordre": 1}
        )

        # --- Types de flux (codes DEBIT/CREDIT critiques : dérivation type_flux) ---
        TypeFlux.objects.get_or_create(
            code="DEBIT", defaults={"libelle": "Débit", "ordre": 1}
        )
        TypeFlux.objects.get_or_create(
            code="CREDIT", defaults={"libelle": "Crédit", "ordre": 2}
        )

        # --- Modes de paiement ---
        for i, (code, lib) in enumerate([
            ("CB", "Carte bancaire"),
            ("VIREMENT", "Virement"),
            ("PRELEVEMENT", "Prélèvement"),
            ("ESPECES", "Espèces"),
        ], start=1):
            ModePaiement.objects.get_or_create(
                code=code, defaults={"libelle": lib, "ordre": i}
            )

        # --- Statuts de flux (est_definitif critique : calcul des soldes réels) ---
        StatutFlux.objects.get_or_create(
            code="VALIDE",
            defaults={"libelle": "Validé", "est_definitif": True, "ordre": 1},
        )
        StatutFlux.objects.get_or_create(
            code="PREVISIONNEL",
            defaults={"libelle": "Prévisionnel", "est_definitif": False, "ordre": 2},
        )

        # --- Fréquences ---
        for i, (code, lib, jours) in enumerate([
            ("MENSUEL", "Mensuel", 30),
            ("TRIMESTRIEL", "Trimestriel", 90),
            ("ANNUEL", "Annuel", 365),
            ("HEBDOMADAIRE", "Hebdomadaire", 7),
        ], start=1):
            Frequence.objects.get_or_create(
                code=code, defaults={"libelle": lib, "nb_jours": jours, "ordre": i}
            )

        # --- Fiscalités ---
        for i, (code, lib) in enumerate([
            ("PEA", "PEA"),
            ("CTO", "Compte-titres ordinaire"),
            ("AV", "Assurance-vie"),
        ], start=1):
            Fiscalite.objects.get_or_create(
                code=code, defaults={"libelle": lib, "ordre": i}
            )

        self.stdout.write(self.style.SUCCESS("✓ Référentiels structurels en place."))

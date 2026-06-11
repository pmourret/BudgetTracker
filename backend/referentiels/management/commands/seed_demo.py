from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction

from referentiels.models import (
    TypeCompte, TypeFlux, Titulaire, ModePaiement,
    Frequence, Etablissement, Devise, Fiscalite, StatutFlux
)
from comptes.models import Compte
from categories.models import Categorie


class Command(BaseCommand):
    help = "Crée un jeu de données de démonstration (référentiels, compte, catégories)."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Création des référentiels...")

        # --- Devise (défaut) ---
        eur, _ = Devise.objects.get_or_create(
            code="EUR",
            defaults={"libelle": "Euro", "symbole": "€", "est_defaut": True, "ordre": 1},
        )

        # --- Types de compte ---
        courant, _ = TypeCompte.objects.get_or_create(
            code="COURANT", defaults={"libelle": "Compte courant", "ordre": 1}
        )
        TypeCompte.objects.get_or_create(
            code="EPARGNE", defaults={"libelle": "Compte épargne", "ordre": 2}
        )

        # --- Titulaires ---
        pierre, _ = Titulaire.objects.get_or_create(
            code="PIERRE", defaults={"libelle": "Pierre", "ordre": 1}
        )

        # --- Établissements ---
        bourso, _ = Etablissement.objects.get_or_create(
            code="BOURSOBANK", defaults={"libelle": "BoursoBank", "ordre": 1}
        )

        # --- Types de flux ---
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

        # --- Statuts de flux ---
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

        self.stdout.write("Création du compte...")

        # --- Compte principal ---
        compte, created = Compte.objects.get_or_create(
            code="CPT-0001",
            defaults={
                "nom": "Compte principal",
                "type_compte": courant,
                "titulaire": pierre,
                "etablissement": bourso,
                "devise": eur,
                "solde_initial": Decimal("4196.49"),
                "solde_reel": Decimal("4196.49"),
            },
        )

        self.stdout.write("Création des catégories...")

        # --- Catégories parentes + quelques sous-catégories ---
        categories = {
            "ALIMENTATION": ("Alimentation", ["Courses", "Restaurant"]),
            "TRANSPORT": ("Transport", ["Carburant", "Transports en commun"]),
            "LOISIRS": ("Loisirs", ["Sorties", "Sport"]),
            "ABONNEMENTS": ("Abonnements", ["Streaming", "Téléphonie"]),
            "REVENUS": ("Revenus", ["Salaire", "Autres revenus"]),
        }

        for i, (code, (nom, enfants)) in enumerate(categories.items(), start=1):
            parent, _ = Categorie.objects.get_or_create(
                code=code, defaults={"nom": nom, "ordre": i}
            )
            for j, enfant_nom in enumerate(enfants, start=1):
                enfant_code = f"{code}_{j}"
                Categorie.objects.get_or_create(
                    code=enfant_code,
                    defaults={"nom": enfant_nom, "parent": parent, "ordre": j},
                )

        self.stdout.write(self.style.SUCCESS("✓ Jeu de données de démonstration créé."))
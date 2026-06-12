from decimal import Decimal
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from referentiels.models import (
    TypeCompte, Titulaire, Etablissement, Devise
)
from comptes.models import Compte
from categories.models import Categorie


class Command(BaseCommand):
    help = (
        "Crée un jeu de données de DÉMONSTRATION (référentiels + compte + "
        "catégories). Outil de DEV uniquement — ne jamais lancer en prod. "
        "Les référentiels structurels sont délégués à `seed_referentiels` "
        "(pas de duplication)."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        # Référentiels structurels (idempotent, source unique de vérité)
        call_command("seed_referentiels")

        # Objets nécessaires à la construction des données de démo
        eur = Devise.objects.get(code="EUR")
        courant = TypeCompte.objects.get(code="COURANT")
        pierre = Titulaire.objects.get(code="PIERRE")
        bourso = Etablissement.objects.get(code="BOURSOBANK")

        self.stdout.write("Création du compte de démo...")

        # --- Compte principal ---
        Compte.objects.get_or_create(
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

        self.stdout.write("Création des catégories de démo...")

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

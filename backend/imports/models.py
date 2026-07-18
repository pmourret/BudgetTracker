from django.db import models

from core.models import BaseModel


class StatutRapprochement(models.TextChoices):
    """Statut d'une ligne de relevé après la passe de rapprochement."""

    EN_ATTENTE = "en_attente", "En attente"        # pas encore rapprochée
    RAPPROCHE = "rapproche", "Rapproché"           # un flux app correspond
    MANQUANT_APP = "manquant_app", "Manquant dans l'app"  # oubli de saisie probable
    AMBIGU = "ambigu", "Ambigu"                    # plusieurs flux candidats
    IGNORE = "ignore", "Ignoré"                    # hors périmètre (choix manuel)


class Banque(models.TextChoices):
    """Parser à appliquer. Chaque valeur = un provider isolé (imports/parsers)."""

    BOURSOBANK = "boursobank", "BoursoBank"


class ImportBancaire(BaseModel):
    """
    Un lot d'import : un fichier de relevé rattaché à UN compte de l'app.

    Le rapprochement (14-A) est en lecture seule : ce lot conserve les lignes
    brutes normalisées et le résultat du matching, mais ne crée aucun flux
    (création → 14-B). Le compte est choisi manuellement à l'upload (mapping
    manuel — voir CLAUDE.md phase 14).
    """

    compte = models.ForeignKey(
        "comptes.Compte",
        on_delete=models.PROTECT,
        related_name="imports_bancaires",
        help_text="Compte de l'app auquel ce relevé est rattaché (choix manuel).",
    )
    banque = models.CharField(
        max_length=30,
        choices=Banque.choices,
        default=Banque.BOURSOBANK,
    )
    nom_fichier = models.CharField(max_length=255, blank=True)

    # Numéro de compte lu dans le fichier — conservé pour traçabilité et pour
    # avertir si le fichier mélange plusieurs comptes (import = un seul compte).
    compte_num_source = models.CharField(max_length=50, blank=True)

    # Compteurs figés au moment du rapprochement (photo du rapport).
    nb_lignes = models.PositiveIntegerField(default=0)
    nb_rapproches = models.PositiveIntegerField(default=0)
    nb_manquants_app = models.PositiveIntegerField(default=0)
    nb_ambigus = models.PositiveIntegerField(default=0)
    nb_ignores = models.PositiveIntegerField(default=0)
    nb_doublons_ignores = models.PositiveIntegerField(
        default=0,
        help_text="Lignes déjà présentes dans un import précédent (anti-doublon).",
    )

    notes = models.TextField(blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Import bancaire"
        verbose_name_plural = "Imports bancaires"

    def __str__(self):
        return f"Import {self.banque} · {self.compte} · {self.nb_lignes} lignes"

    def delete(self, using=None, keep_parents=False):
        """
        Soft delete en cascade : `BaseModel.delete` ne cascade pas, or laisser
        les `LigneBancaire` actives fausserait l'anti-doublon (leurs hash
        resteraient comptés) et bloquerait tout ré-import du même relevé.
        Supprimer un lot doit donc libérer ses lignes.
        """
        self.lignes.all().delete()  # SoftDeleteQuerySet → is_deleted=True
        super().delete(using=using, keep_parents=keep_parents)


class LigneBancaire(BaseModel):
    """
    Une ligne de relevé bancaire normalisée (issue d'une `LigneBrute`), persistée.

    Représente la vérité BANQUE ; le lien vers l'app se fait via `flux` (nullable)
    quand le rapprochement trouve une correspondance. Montant signé comme les Flux
    (règle §4.2 : négatif = débit, positif = crédit).
    """

    import_lot = models.ForeignKey(
        ImportBancaire,
        on_delete=models.CASCADE,
        related_name="lignes",
    )

    # --- Données brutes normalisées (miroir de parsers.base.LigneBrute) -------
    date_operation = models.DateField()
    date_valeur = models.DateField()
    libelle = models.CharField(max_length=255)
    libelle_suggere = models.CharField(max_length=255, blank=True)
    categorie_banque = models.CharField(max_length=120, blank=True)
    categorie_parent_banque = models.CharField(max_length=120, blank=True)
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    commentaire = models.TextField(blank=True)
    solde_apres = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Solde du compte après l'opération (accountbalance) — "
                  "contrôle du solde_reel du jour.",
    )
    pointe_banque = models.BooleanField(
        default=False,
        help_text="Pointage côté banque (colonne mark).",
    )

    # Empreinte de dé-duplication (parsers.base.LigneBrute.hash_dedup).
    # PAS d'unicité en base : la banque peut réémettre deux opérations
    # réellement identiques le même jour (même montant/libellé, et le solde
    # est un instantané journalier, pas par opération → non discriminant).
    # L'anti-doublon entre exports se fait au niveau du moteur de
    # rapprochement, par comptage d'occurrences du hash (brique ③).
    hash_dedup = models.CharField(max_length=40, db_index=True)

    # --- Résultat du rapprochement -------------------------------------------
    statut = models.CharField(
        max_length=20,
        choices=StatutRapprochement.choices,
        default=StatutRapprochement.EN_ATTENTE,
        db_index=True,
    )
    flux = models.ForeignKey(
        "flux.Flux",
        on_delete=models.SET_NULL,
        related_name="lignes_bancaires",
        null=True,
        blank=True,
        help_text="Flux de l'app apparié par le rapprochement, si trouvé.",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Ligne bancaire"
        verbose_name_plural = "Lignes bancaires"
        ordering = ["-date_operation", "-created_at"]
        indexes = [
            models.Index(fields=["import_lot", "statut"]),
            models.Index(fields=["date_operation", "montant"]),
        ]

    def __str__(self):
        signe = "+" if self.montant >= 0 else ""
        return f"{self.date_operation} | {signe}{self.montant} € | {self.libelle}"

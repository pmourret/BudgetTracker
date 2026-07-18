from django.contrib import admin

from .models import ImportBancaire, LigneBancaire


class LigneBancaireInline(admin.TabularInline):
    model = LigneBancaire
    extra = 0
    fields = ("date_operation", "libelle", "montant", "statut", "flux")
    readonly_fields = fields
    show_change_link = True


@admin.register(ImportBancaire)
class ImportBancaireAdmin(admin.ModelAdmin):
    list_display = (
        "banque", "compte", "nb_lignes", "nb_rapproches",
        "nb_manquants_app", "nb_ambigus", "created_at",
    )
    list_filter = ("banque", "compte")
    search_fields = ("nom_fichier", "compte_num_source")
    inlines = [LigneBancaireInline]


@admin.register(LigneBancaire)
class LigneBancaireAdmin(admin.ModelAdmin):
    list_display = ("date_operation", "libelle", "montant", "statut", "import_lot")
    list_filter = ("statut", "import_lot__banque")
    search_fields = ("libelle", "libelle_suggere", "hash_dedup")
    raw_id_fields = ("import_lot", "flux")

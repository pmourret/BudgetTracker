from django.contrib import admin
from .models import Budget


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = [
        "categorie", "mois", "montant_prevu",
        "montant_consomme", "taux_consommation"
    ]
    list_filter = ["mois", "categorie"]
    search_fields = ["categorie__nom", "notes"]
    ordering = ["-mois", "categorie__nom"]
    readonly_fields = [
        "montant_consomme", "taux_consommation", "created_at", "updated_at"
    ]
    fieldsets = (
        ("Budget", {
            "fields": ("categorie", "mois", "montant_prevu", "notes")
        }),
        ("Consommation (calculé)", {
            "fields": ("montant_consomme", "taux_consommation")
        }),
        ("Audit", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
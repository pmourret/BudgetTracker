from django.contrib import admin
from .models import Compte


@admin.register(Compte)
class CompteAdmin(admin.ModelAdmin):
    list_display = [
        "code", "nom", "titulaire", "etablissement",
        "solde_initial", "solde_reel", "solde_theorique", "ecart_solde", "actif"
    ]
    list_filter = ["actif", "type_compte", "titulaire", "etablissement"]
    search_fields = ["code", "nom"]
    readonly_fields = ["solde_theorique", "ecart_solde", "created_at", "updated_at"]
    fieldsets = (
        ("Identification", {
            "fields": ("code", "nom", "type_compte", "titulaire", "etablissement", "devise")
        }),
        ("Soldes", {
            "fields": (
                "solde_initial", "solde_reel",
                "solde_theorique", "ecart_solde"
            )
        }),
        ("Metadata", {
            "fields": ("actif", "date_ouverture", "date_fermeture", "notes")
        }),
        ("Audit", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
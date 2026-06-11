from django.contrib import admin
from .models import Flux


@admin.register(Flux)
class FluxAdmin(admin.ModelAdmin):
    list_display = [
        "date_flux", "mois", "compte", "libelle",
        "montant", "categorie", "type_flux", "statut", "est_transfert"
    ]
    list_filter = [
        "est_transfert", "type_flux", "statut",
        "compte", "categorie", "mois"
    ]
    search_fields = ["libelle", "reference_externe", "notes"]
    ordering = ["-date_flux"]
    readonly_fields = ["mois", "created_at", "updated_at"]
    fieldsets = (
        ("Identification", {
            "fields": (
                "compte", "type_flux", "statut",
                "titulaire", "mode_paiement", "devise"
            )
        }),
        ("Montant & Date", {
            "fields": ("montant", "date_flux", "mois")
        }),
        ("Catégorisation", {
            "fields": ("categorie", "libelle", "reference_externe", "notes")
        }),
        ("Flags", {
            "fields": ("est_transfert",)
        }),
        ("Audit", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
from django.contrib import admin
from .models import Actif


@admin.register(Actif)
class ActifAdmin(admin.ModelAdmin):
    list_display = [
        "nom", "type_actif", "valeur_actuelle",
        "valeur_acquisition", "date_valorisation",
        "est_valorise_recemment", "actif"
    ]
    list_filter = ["type_actif", "actif", "fiscalite"]
    search_fields = ["nom", "notes"]
    ordering = ["type_actif", "nom"]
    readonly_fields = [
        "plus_value_latente", "est_valorise_recemment",
        "created_at", "updated_at"
    ]
    fieldsets = (
        ("Identification", {
            "fields": (
                "nom", "type_actif", "compte_associe",
                "fiscalite", "devise"
            )
        }),
        ("Valorisation (estimative)", {
            "fields": (
                "valeur_acquisition", "valeur_actuelle",
                "date_valorisation", "plus_value_latente",
                "est_valorise_recemment"
            )
        }),
        ("Metadata", {
            "fields": ("actif", "notes")
        }),
        ("Audit", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
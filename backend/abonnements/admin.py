from django.contrib import admin
from .models import Abonnement


@admin.register(Abonnement)
class AbonnementAdmin(admin.ModelAdmin):
    list_display = [
        "nom", "compte", "categorie", "montant_attendu",
        "frequence", "actif", "derniere_occurrence", "est_en_retard"
    ]
    list_filter = ["actif", "frequence", "compte", "categorie"]
    search_fields = ["nom", "notes"]
    ordering = ["nom"]
    readonly_fields = [
        "derniere_occurrence", "created_at", "updated_at"
    ]
    fieldsets = (
        ("Identification", {
            "fields": ("nom", "compte", "categorie", "type_flux", "mode_paiement")
        }),
        ("Récurrence", {
            "fields": (
                "frequence", "montant_attendu", "seuil_divergence_pct",
                "date_debut", "date_fin", "jour_echeance"
            )
        }),
        ("Suivi", {
            "fields": ("actif", "derniere_occurrence", "notes")
        }),
        ("Audit", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
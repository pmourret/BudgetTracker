from django.contrib import admin
from .models import Alerte


@admin.register(Alerte)
class AlerteAdmin(admin.ModelAdmin):
    list_display = [
        "type_alerte", "niveau", "acquittee",
        "compte", "budget", "abonnement", "created_at"
    ]
    list_filter = ["type_alerte", "niveau", "acquittee"]
    search_fields = ["explication"]
    ordering = ["-created_at"]
    readonly_fields = [
        "type_alerte", "niveau", "explication",
        "valeur_constatee", "valeur_seuil",
        "acquittee_le", "created_at", "updated_at"
    ]
    fieldsets = (
        ("Alerte", {
            "fields": (
                "type_alerte", "niveau", "explication",
                "valeur_constatee", "valeur_seuil"
            )
        }),
        ("Contexte", {
            "fields": ("compte", "budget", "abonnement")
        }),
        ("Suivi", {
            "fields": ("acquittee", "acquittee_le")
        }),
        ("Audit", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
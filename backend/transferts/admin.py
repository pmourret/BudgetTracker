from django.contrib import admin
from .models import Transfert


@admin.register(Transfert)
class TransfertAdmin(admin.ModelAdmin):
    list_display = [
        "flux_debit", "flux_credit", "montant", "created_at"
    ]
    readonly_fields = [
        "flux_debit", "flux_credit", "montant", "created_at", "updated_at"
    ]
    search_fields = ["notes"]
    ordering = ["-created_at"]
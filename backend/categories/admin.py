from django.contrib import admin
from .models import Categorie


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ["code", "nom", "parent", "niveau", "ordre", "actif"]
    list_editable = ["ordre", "actif"]
    list_filter = ["actif", "parent"]
    search_fields = ["code", "nom"]
    ordering = ["ordre", "nom"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Identification", {
            "fields": ("code", "nom", "parent", "description")
        }),
        ("Configuration", {
            "fields": ("ordre", "actif")
        }),
        ("Audit", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
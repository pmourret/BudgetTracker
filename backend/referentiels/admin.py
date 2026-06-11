from django.contrib import admin
from .models import (
    TypeCompte, TypeFlux, Titulaire, ModePaiement,
    Frequence, Etablissement, Devise, Fiscalite, StatutFlux,
)


class ReferentielAdmin(admin.ModelAdmin):
    list_display = ["code", "libelle", "ordre", "actif"]
    list_editable = ["ordre", "actif"]
    search_fields = ["code", "libelle"]
    ordering = ["ordre", "libelle"]


@admin.register(TypeCompte)
class TypeCompteAdmin(ReferentielAdmin):
    pass


@admin.register(TypeFlux)
class TypeFluxAdmin(ReferentielAdmin):
    pass


@admin.register(Titulaire)
class TitulaireAdmin(ReferentielAdmin):
    pass


@admin.register(ModePaiement)
class ModePaiementAdmin(ReferentielAdmin):
    pass


@admin.register(Frequence)
class FrequenceAdmin(ReferentielAdmin):
    list_display = ["code", "libelle", "nb_jours", "ordre", "actif"]


@admin.register(Etablissement)
class EtablissementAdmin(ReferentielAdmin):
    pass


@admin.register(Devise)
class DeviseAdmin(ReferentielAdmin):
    list_display = ["code", "libelle", "symbole", "est_defaut", "ordre", "actif"]


@admin.register(Fiscalite)
class FiscaliteAdmin(ReferentielAdmin):
    pass


@admin.register(StatutFlux)
class StatutFluxAdmin(ReferentielAdmin):
    list_display = ["code", "libelle", "est_definitif", "ordre", "actif"]
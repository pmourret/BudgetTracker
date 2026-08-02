"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from accounts.views import (
    ConnexionView,
    DeconnexionView,
    MoiView,
    RafraichissementView,
)

from comptes.views import CompteViewSet
from categories.views import CategorieViewSet
from flux.views import FluxViewSet
from transferts.views import TransfertViewSet
from budgets.views import BudgetViewSet, BudgetTemplateViewSet
from abonnements.views import AbonnementViewSet
from alertes.views import AlerteViewSet
from patrimoine.views import ActifViewSet
from imports.views import ImportBancaireViewSet, LigneBancaireViewSet
from referentiels.views import (
    ParametresBudgetView,
    TypeCompteViewSet, TypeFluxViewSet, TitulaireViewSet,
    ModePaiementViewSet, FrequenceViewSet, EtablissementViewSet,
    DeviseViewSet, FiscaliteViewSet, StatutFluxViewSet
)

from analytics.views import (
    DashboardView, CompteDashboardView, PrevisionnelView, AnalyseView,
    AbonnementsAnalyseView, PointsView, TransfertsAnalyseView
)

router = DefaultRouter()

# Ressources principales
router.register(r"comptes", CompteViewSet, basename="compte")
router.register(r"categories", CategorieViewSet, basename="categorie")
router.register(r"flux", FluxViewSet, basename="flux")
router.register(r"transferts", TransfertViewSet, basename="transfert")
router.register(r"budgets", BudgetViewSet, basename="budget")
router.register(r"budget-templates", BudgetTemplateViewSet, basename="budget-template")
router.register(r"abonnements", AbonnementViewSet, basename="abonnement")
router.register(r"alertes", AlerteViewSet, basename="alerte")
router.register(r"patrimoine", ActifViewSet, basename="actif")
router.register(r"imports", ImportBancaireViewSet, basename="import-bancaire")
router.register(r"imports-lignes", LigneBancaireViewSet, basename="ligne-bancaire")

# Référentiels (lecture seule)
router.register(r"referentiels/types-compte", TypeCompteViewSet, basename="type-compte")
router.register(r"referentiels/types-flux", TypeFluxViewSet, basename="type-flux")
router.register(r"referentiels/titulaires", TitulaireViewSet, basename="titulaire")
router.register(r"referentiels/modes-paiement", ModePaiementViewSet, basename="mode-paiement")
router.register(r"referentiels/frequences", FrequenceViewSet, basename="frequence")
router.register(r"referentiels/etablissements", EtablissementViewSet, basename="etablissement")
router.register(r"referentiels/devises", DeviseViewSet, basename="devise")
router.register(r"referentiels/fiscalites", FiscaliteViewSet, basename="fiscalite")
router.register(r"referentiels/statuts-flux", StatutFluxViewSet, basename="statut-flux")

urlpatterns = [
    path("admin/", admin.site.urls),
    # --- Authentification (durcissement, août 2026) ----------------------- #
    # Mêmes chemins que FoyerOS : les deux applications convergeront vers un
    # service d'identité commun, autant que le contrat soit déjà le même.
    path("api/v1/auth/token/", ConnexionView.as_view(), name="token"),
    # Ces deux vues **relaient** vers l'annuaire sous `IDENTITE_AUTORITE`,
    # sinon elles émettent localement. Le front appelle la même URL.
    path(
        "api/v1/auth/token/refresh/",
        RafraichissementView.as_view(),
        name="token-refresh",
    ),
    path(
        "api/v1/auth/deconnexion/",
        DeconnexionView.as_view(),
        name="deconnexion",
    ),
    path("api/v1/auth/me/", MoiView.as_view(), name="moi"),
    path("api/v1/analytics/dashboard/", DashboardView.as_view(), name="dashboard"),
    path("api/v1/analytics/compte/<uuid:compte_id>/", CompteDashboardView.as_view(), name="compte-dashboard"),
    path("api/v1/analytics/previsionnel/", PrevisionnelView.as_view(), name="previsionnel"),
    path("api/v1/analytics/analyse/", AnalyseView.as_view(), name="analyse"),
    path("api/v1/analytics/abonnements/", AbonnementsAnalyseView.as_view(), name="abonnements-analyse"),
    path("api/v1/analytics/transferts/", TransfertsAnalyseView.as_view(), name="transferts-analyse"),
    path("api/v1/analytics/points/", PointsView.as_view(), name="points"),
    path("api/v1/referentiels/parametres-budget/", ParametresBudgetView.as_view(), name="parametres-budget"),
    path("api/v1/", include(router.urls)),
]
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from django.core.exceptions import ValidationError as DjangoValidationError

from comptes.models import Compte
from flux.models import Flux
from referentiels.models import ParametresBudget
from .models import ImportBancaire, LigneBancaire, StatutRapprochement
from .parsers.boursobank import FormatInvalideError
from .serializers import (
    CreerFluxSerializer, FluxResumeSerializer, ImportBancaireSerializer,
    ImportUploadSerializer, LigneBancaireSerializer, ValiderLigneSerializer,
)
from .services.creation import (
    BanqueNonSupportee, CompteIntrouvableError, FichierMultiCompteError,
    creer_import,
)
from .services.rapprochement import (
    CreationFluxInvalide, ValidationInvalide, candidats_pour, controle_solde,
    creer_flux_depuis_ligne, dernier_controle_pour_compte,
    executer_rapprochement, flux_orphelins, rejeter_ligne, valider_ligne,
)


def _serialiser_controle(ctrl):
    """Montants en chaîne, comme les `DecimalField` des serializers.

    Les deux exposants du contrôle (rapport d'import et widget par compte)
    passent par ici : deux conversions parallèles finiraient par diverger d'un
    arrondi, et un centime d'écart est précisément ce que ce contrôle mesure.
    """
    if ctrl is None:
        return None
    return {
        **ctrl,
        "solde_banque": str(ctrl["solde_banque"]),
        "solde_app": str(ctrl["solde_app"]),
        "ecart": str(ctrl["ecart"]),
    }


def _rapport_detaille(import_lot):
    """
    Rapport présenté (flux hydratés) pour le front. Lu sur l'état PERSISTÉ,
    donc juste après une validation/rejet manuel.
    """
    lignes = (
        import_lot.lignes
        .select_related("flux", "flux__categorie", "flux__statut")
        .all()
    )
    lignes_out = []
    for ligne in lignes:
        entry = LigneBancaireSerializer(ligne).data
        entry["flux_detail"] = (
            FluxResumeSerializer(ligne.flux).data if ligne.flux_id else None
        )
        entry["candidats"] = (
            FluxResumeSerializer(candidats_pour(ligne), many=True).data
            if ligne.statut == StatutRapprochement.AMBIGU else []
        )
        lignes_out.append(entry)

    flux_sans_ligne = [
        {**FluxResumeSerializer(o["flux"]).data, "motif": o["motif"]}
        for o in flux_orphelins(import_lot)
    ]

    ctrl = _serialiser_controle(controle_solde(import_lot))

    return {
        "lot": ImportBancaireSerializer(import_lot).data,
        "tolerance_jours": ParametresBudget.get_solo().tolerance_jours_rapprochement,
        "controle_solde": ctrl,
        "lignes": lignes_out,
        "flux_sans_ligne": flux_sans_ligne,
    }


class ImportBancaireViewSet(viewsets.ModelViewSet):
    """
    Rapprochement bancaire (14-A, lecture seule vis-à-vis des flux).

    - POST   /imports/                (multipart) : upload d'un relevé → lot + rapprochement
    - GET    /imports/                : liste des lots
    - GET    /imports/{id}/           : synthèse d'un lot
    - GET    /imports/{id}/rapport/   : rapport détaillé (lignes + flux orphelins)
    - POST   /imports/{id}/relancer/  : recalcule le rapprochement (ex. tolérance modifiée)
    - DELETE /imports/{id}/           : soft delete du lot
    """

    serializer_class = ImportBancaireSerializer
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        return ImportBancaire.objects.select_related("compte").all()

    def create(self, request, *args, **kwargs):
        entree = ImportUploadSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        fichier = entree.validated_data["fichier"]

        try:
            synthese = creer_import(
                compte=entree.validated_data.get("compte"),
                banque=entree.validated_data["banque"],
                contenu_bytes=fichier.read(),
                nom_fichier=getattr(fichier, "name", ""),
            )
        except FichierMultiCompteError as exc:
            return Response(
                {"detail": str(exc), "comptes": exc.comptes},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except CompteIntrouvableError as exc:
            return Response(
                {"detail": str(exc), "compte_num": exc.compte_num},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except (FormatInvalideError, BanqueNonSupportee) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "lot": ImportBancaireSerializer(synthese["lot"]).data,
                "nb_doublons": synthese["nb_doublons"],
                "erreurs_parsing": synthese["erreurs_parsing"],
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="controle-compte")
    def controle_compte(self, request):
        """`GET /imports/controle-compte/?compte=<uuid>` — le contrôle hors import.

        ⚠️ **Cette route vit dans `imports`, pas dans `comptes`.** Le contrôle
        de solde est une notion du rapprochement : la porter par
        `CompteViewSet` obligerait `comptes` à importer `imports`, alors que la
        dépendance va déjà dans l'autre sens (`imports` lit comptes et flux).
        Un aller-retour entre deux apps est une boucle qu'on ne défait plus.

        `204` quand le compte n'a aucun relevé : ce n'est pas une erreur, c'est
        l'état normal d'un compte jamais rapproché — et le front doit pouvoir
        ne rien afficher sans traiter un cas d'échec.
        """
        compte_id = request.query_params.get("compte")
        if not compte_id:
            return Response(
                {"detail": "Paramètre `compte` requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            compte = Compte.objects.filter(pk=compte_id).first()
        except (DjangoValidationError, ValueError):
            # Un UUID malformé remonte de la couche base : sans ce garde, une
            # URL bricolée à la main répond 500 là où la réponse est « inconnu ».
            compte = None
        if compte is None:
            return Response(
                {"detail": "Compte introuvable."}, status=status.HTTP_404_NOT_FOUND
            )

        controle = dernier_controle_pour_compte(compte)
        if controle is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(_serialiser_controle(controle))

    @action(detail=True, methods=["get"])
    def rapport(self, request, pk=None):
        return Response(_rapport_detaille(self.get_object()))

    @action(detail=True, methods=["post"])
    def relancer(self, request, pk=None):
        lot = self.get_object()
        executer_rapprochement(lot)
        return Response(_rapport_detaille(lot))


class LigneBancaireViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Lignes de relevé. Actions de résolution des ambigus :
    - GET  /imports-lignes/{id}/candidats/ : flux candidats à valider
    - POST /imports-lignes/{id}/valider/   : body { "flux_id": ... }
    - POST /imports-lignes/{id}/rejeter/   : marque « manquant dans l'app »
    """

    serializer_class = LigneBancaireSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["import_lot", "statut"]

    def get_queryset(self):
        return LigneBancaire.objects.select_related("import_lot", "flux").all()

    @action(detail=True, methods=["get"])
    def candidats(self, request, pk=None):
        ligne = self.get_object()
        return Response(
            FluxResumeSerializer(candidats_pour(ligne), many=True).data
        )

    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
        ligne = self.get_object()
        entree = ValiderLigneSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        flux = Flux.objects.filter(id=entree.validated_data["flux_id"]).first()
        if flux is None:
            return Response(
                {"detail": "Flux introuvable."}, status=status.HTTP_404_NOT_FOUND
            )
        try:
            valider_ligne(ligne, flux)
        except ValidationInvalide as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        ligne.refresh_from_db()
        return Response(LigneBancaireSerializer(ligne).data)

    @action(detail=True, methods=["post"])
    def rejeter(self, request, pk=None):
        ligne = self.get_object()
        rejeter_ligne(ligne)
        ligne.refresh_from_db()
        return Response(LigneBancaireSerializer(ligne).data)

    @action(detail=True, methods=["post"], url_path="creer-flux")
    def creer_flux(self, request, pk=None):
        """14-B — crée le flux manquant correspondant à cette ligne et la rattache."""
        ligne = self.get_object()
        entree = CreerFluxSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        try:
            flux = creer_flux_depuis_ligne(
                ligne,
                categorie=entree.validated_data["categorie"],
                libelle=entree.validated_data.get("libelle") or None,
            )
        except CreationFluxInvalide as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        ligne.refresh_from_db()
        return Response(
            {
                "ligne": LigneBancaireSerializer(ligne).data,
                "flux": FluxResumeSerializer(flux).data,
            },
            status=status.HTTP_201_CREATED,
        )

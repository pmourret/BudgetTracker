from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

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
    creer_flux_depuis_ligne, executer_rapprochement, flux_orphelins,
    rejeter_ligne, valider_ligne,
)


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

    ctrl = controle_solde(import_lot)
    if ctrl is not None:
        # Montants en chaîne (cohérent avec les serializers DecimalField).
        ctrl = {
            "date_reference": ctrl["date_reference"],
            "solde_banque": str(ctrl["solde_banque"]),
            "solde_app": str(ctrl["solde_app"]),
            "ecart": str(ctrl["ecart"]),
            "coherent": ctrl["coherent"],
        }

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

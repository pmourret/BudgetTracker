from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .models import Categorie
from .serializers import CategorieSerializer


class CategorieViewSet(viewsets.ModelViewSet):
    """
    CRUD catégories avec protection sur la suppression.

    Actions supplémentaires :
    - GET /categories/{id}/sous-categories/ — liste les enfants d'une racine
    - POST /categories/{id}/desactiver/     — désactive sans supprimer
    """
    serializer_class = CategorieSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ["actif", "parent"]
    search_fields = ["nom", "code"]
    ordering_fields = ["ordre", "nom", "created_at"]
    ordering = ["ordre", "nom"]

    def get_queryset(self):
        return (
            Categorie.objects
            .select_related("parent")
            .prefetch_related("sous_categories")
            .all()
        )

    def destroy(self, request, *args, **kwargs):
        """
        Soft delete protégé : retourne 409 si des flux actifs sont liés.
        """
        instance = self.get_object()
        try:
            instance.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_409_CONFLICT
            )

    @action(detail=True, methods=["get"], url_path="sous-categories")
    def sous_categories(self, request, pk=None):
        """Retourne les sous-catégories d'une catégorie racine."""
        categorie = self.get_object()
        sous_cats = categorie.sous_categories.filter(is_deleted=False)
        serializer = self.get_serializer(sous_cats, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="desactiver")
    def desactiver(self, request, pk=None):
        """
        Désactive une catégorie (et ses sous-catégories) sans la supprimer.
        Utilisable même si des flux sont liés.
        """
        categorie = self.get_object()
        categorie.actif = False
        categorie.save(update_fields=["actif", "updated_at"])

        if categorie.est_racine:
            categorie.sous_categories.all().update(actif=False)

        return Response(
            {"detail": f"Catégorie '{categorie.nom}' désactivée."},
            status=status.HTTP_200_OK
        )
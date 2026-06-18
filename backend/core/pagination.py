from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Pagination par défaut du projet.

    Comportement par défaut inchangé (50 par page). Le client peut demander
    une autre taille via ``?page_size=N`` — utile pour les référentiels à
    volume borné consommés en entier par l'UI (ex. catégories). ``max_page_size``
    plafonne la demande pour éviter les abus.
    """

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 1000

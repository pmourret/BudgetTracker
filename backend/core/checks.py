"""Contrôles au démarrage — `python manage.py check`.

Ajoutés avec le durcissement (août 2026), parce que celui-ci **change la nature
de `SECRET_KEY`**. Tant que l'API était `AllowAny` et sans `SessionAuthentication`,
cette clé ne signait rien qui protégeait quoi que ce soit. Elle signe désormais
**tous les jetons d'accès** : la voler, c'est pouvoir en fabriquer.

⚠️ **Bloquant hors `DEBUG`, simple avertissement en développement** (durci en
août 2026). Le contrôle n'était qu'un *warning* partout — donc il passait
`check --deploy --fail-level ERROR`, et une clé faible partait en production
sans que rien ne l'arrête. C'était exactement le cas ici : 20 octets. En
développement, bloquer n'aurait fait qu'empêcher de travailler.

⚠️ **Volontairement dupliqué** dans les trois dépôts de la suite : la règle de
suite interdit de partager du code par copie ou symlink, et un paquet versionné
serait la bonne réponse le jour où il y aura plus que ça à mutualiser.
"""
from django.conf import settings
from django.core.checks import Error, Warning, register

# RFC 7518 §3.2 : pour HS256, une clé au moins aussi longue que la sortie du
# hachage, soit 32 octets. En dessous, PyJWT émet lui-même un avertissement —
# mais au moment de signer, c'est-à-dire noyé dans les logs d'exécution.
LONGUEUR_MINIMALE = 32


@register()
def verifier_cle_de_signature(app_configs, **kwargs):
    cle = settings.SECRET_KEY or ""
    Niveau = Warning if settings.DEBUG else Error
    suffixe = "W" if settings.DEBUG else "E"

    if cle.startswith("django-insecure"):
        return [
            Niveau(
                "SECRET_KEY est la clé de repli codée dans le dépôt.",
                hint=(
                    "Elle est publique par construction, et signe les jetons "
                    'd\'accès. Poser DJANGO_SECRET_KEY : python -c "import '
                    'secrets; print(secrets.token_urlsafe(48))"'
                ),
                id=f"core.{suffixe}001",
            )
        ]

    if len(cle.encode()) < LONGUEUR_MINIMALE:
        return [
            Niveau(
                f"SECRET_KEY fait {len(cle.encode())} octets, moins que les "
                f"{LONGUEUR_MINIMALE} recommandés pour signer en HS256.",
                hint=(
                    "Depuis l'activation de JWT, cette clé protège l'accès à "
                    "toute l'API. La renouveler déconnecte les sessions en cours."
                ),
                id=f"core.{suffixe}002",
            )
        ]

    return []

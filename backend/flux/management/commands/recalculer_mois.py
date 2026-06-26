from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Recalcule le champ `mois` (mois comptable) de tous les flux selon le "
        "paramètre `jour_debut_mois_comptable` courant. Re-sauvegarde chaque "
        "flux : les signaux recalculent ensuite soldes et consommations de "
        "budgets. À lancer après tout changement du jour de bascule. "
        "Idempotente (aucun effet si rien ne change, notamment jour = 1)."
    )

    def handle(self, *args, **options):
        from core.services.periode import jour_bascule_actif
        from flux.services.recalcul_mois import recalculer_mois_flux

        jour = jour_bascule_actif()
        res = recalculer_mois_flux()

        self.stdout.write(self.style.SUCCESS(
            f"✓ {res['total']} flux parcourus, {res['modifies']} remappés "
            f"(jour de bascule = {jour})."
        ))

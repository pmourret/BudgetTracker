from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Referme les alertes budget dont le seuil n'est plus franchi. "
        "Depuis la revue UI/UX du 2026-08-20, la détection le fait à chaque "
        "mouvement de flux ; cette commande rattrape les alertes ouvertes "
        "AVANT cette correction, qui ne se refermeraient qu'au prochain flux "
        "touchant leur budget. À blanc par défaut : --appliquer pour écrire. "
        "Idempotente."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--appliquer",
            action="store_true",
            help="Écrit réellement. Sans ce drapeau, la commande n'affiche que ce qu'elle ferait.",
        )

    def handle(self, *args, **options):
        from alertes.models import Alerte, TypeAlerte
        from alertes.services import refermer_alertes_budget_perimees
        from budgets.models import Budget

        appliquer = options["appliquer"]

        ouvertes = Alerte.objects.filter(
            acquittee=False,
            budget__isnull=False,
            type_alerte__in=(TypeAlerte.BUDGET_ALERTE, TypeAlerte.BUDGET_DEPASSE),
        )

        # ⚠️ `all_with_deleted` : une alerte peut pointer un budget **supprimé**,
        # et c'est justement le cas qu'on veut refermer. Le manager par défaut
        # ne le verrait pas, et l'alerte resterait ouverte pour toujours.
        budgets = Budget.objects.all_with_deleted().filter(
            pk__in=ouvertes.values("budget_id")
        )

        total = 0
        orphelines = 0
        for budget in budgets:
            if budget.is_deleted:
                concernees = ouvertes.filter(budget=budget)
                n = concernees.count()
                if n:
                    self.stdout.write(
                        f"  {budget.libelle} — {budget.mois:%Y-%m} : "
                        f"{n} alerte(s), budget supprimé"
                    )
                    if appliquer:
                        for alerte in concernees:
                            alerte.acquitter()
                orphelines += n
                total += n
                continue
            if appliquer:
                referme = refermer_alertes_budget_perimees(budget)
            else:
                referme = sum(
                    1
                    for a in Alerte.objects.filter(
                        budget=budget,
                        acquittee=False,
                        type_alerte__in=(TypeAlerte.BUDGET_ALERTE, TypeAlerte.BUDGET_DEPASSE),
                    )
                    if a.valeur_seuil is not None
                    and budget.taux_consommation < a.valeur_seuil
                )
            if referme:
                self.stdout.write(
                    f"  {budget.libelle} — {budget.mois:%Y-%m} : "
                    f"{referme} alerte(s), taux actuel {budget.taux_consommation} %"
                )
            total += referme

        detail = f" (dont {orphelines} sur un budget supprimé)" if orphelines else ""
        if appliquer:
            self.stdout.write(
                self.style.SUCCESS(f"✓ {total} alerte(s) refermée(s){detail}.")
            )
        else:
            self.stdout.write(self.style.WARNING(
                f"À blanc : {total} alerte(s) seraient refermées{detail}. "
                f"Relancer avec --appliquer pour écrire."
            ))

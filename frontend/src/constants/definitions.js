/**
 * Définitions pédagogiques centralisées des indicateurs affichés dans l'UI.
 *
 * Chaque entrée : { titre, texte (ce que représente le chiffre),
 * formule (comment il est calculé) }. Consommé par <Tooltip {...DEFINITIONS.xxx} />.
 *
 * Règle projet : on explique, on ne conseille jamais. Préciser la fiabilité
 * (réel / estimatif / projeté) quand c'est pertinent. Garder le wording aligné
 * sur les règles métier (CLAUDE.md §4-5).
 */
export const DEFINITIONS = {
  // ---- Soldes (Dashboard & Comptes) ----
  solde_total: {
    titre: 'Solde total',
    texte:
      "Somme des soldes théoriques de tous vos comptes : les flux prévisionnels (à venir, non confirmés) y sont inclus.",
    formule: 'Σ (solde initial + tous les flux de chaque compte).',
  },
  solde_theorique: {
    titre: 'Solde théorique',
    texte:
      "Ce que deviendra le compte si tous les mouvements saisis (y compris prévisionnels) se réalisent. Vue anticipée, pas le solde réel de la banque.",
    formule: 'Solde initial + Σ (tous les flux du compte, confirmés et prévisionnels).',
  },
  solde_reel: {
    titre: 'Solde confirmé',
    texte:
      "Le solde réellement présent sur le compte aujourd'hui : seuls les flux à statut définitif sont comptés. C'est la seule vérité comptable.",
    formule: 'Solde initial + Σ (flux dont le statut est définitif).',
  },
  ecart_solde: {
    titre: 'En attente',
    texte:
      "Montant des mouvements prévisionnels pas encore confirmés. Ce n'est pas une erreur : c'est l'écart entre ce qui est projeté et ce qui est déjà acté.",
    formule: 'Solde confirmé − solde théorique (= −Σ des flux prévisionnels).',
  },

  // ---- Dashboard : mois courant ----
  depenses_mois: {
    titre: 'Dépenses du mois',
    texte:
      'Total des sorties d’argent du mois en cours. Les transferts entre vos comptes et les ajustements en sont exclus.',
    formule: 'Σ des flux négatifs du mois (hors transferts et ajustements).',
  },
  revenus_mois: {
    titre: 'Revenus du mois',
    texte:
      'Total des entrées d’argent du mois en cours. Les transferts entre vos comptes et les ajustements en sont exclus.',
    formule: 'Σ des flux positifs du mois (hors transferts et ajustements).',
  },
  epargne_nette: {
    titre: 'Épargne nette',
    texte:
      "Ce qu'il reste une fois les dépenses retirées des revenus du mois. Positive = vous mettez de côté ; négative = vous puisez dans vos réserves.",
    formule: 'Revenus du mois − dépenses du mois.',
  },
  taux_epargne: {
    titre: "Taux d'épargne",
    texte:
      'Part de vos revenus du mois qui est épargnée plutôt que dépensée.',
    formule: '(Épargne nette ÷ revenus du mois) × 100.',
  },
  patrimoine_estime: {
    titre: 'Patrimoine estimé',
    texte:
      "Valeur estimative de vos actifs, basée sur vos valorisations manuelles. Indépendante de vos soldes bancaires : ce n'est jamais une vérité comptable.",
    formule: 'Σ des dernières valeurs estimées de vos actifs actifs.',
  },
  depenses_par_categorie: {
    titre: 'Dépenses par catégorie',
    texte:
      "Répartition de vos dépenses du mois par catégorie majeure. Les sous-catégories sont regroupées sous leur parent. Transferts et ajustements exclus.",
    formule: 'Σ des dépenses du mois, groupées par catégorie majeure.',
  },

  // ---- Dashboard par compte ----
  compte_nb_flux: {
    titre: 'Mouvements du mois',
    texte:
      'Nombre de flux saisis ce mois sur ce compte (hors transferts et ajustements).',
    formule: 'Nombre de flux du mois rattachés au compte.',
  },
  compte_top_depenses: {
    titre: 'Top dépenses du mois',
    texte:
      "Les plus grosses sorties d'argent du mois sur ce compte, de la plus élevée à la plus faible. Transferts et ajustements exclus.",
    formule: 'Les 5 flux négatifs du mois les plus élevés, par montant décroissant.',
  },

  // ---- Budgets ----
  budget_total_prevu: {
    titre: 'Total prévu',
    texte: "Somme des enveloppes que vous avez fixées pour le mois.",
    formule: 'Σ des montants prévus de tous les budgets du mois.',
  },
  budget_total_consomme: {
    titre: 'Total consommé',
    texte:
      'Dépenses déjà réalisées ce mois sur les catégories budgétées.',
    formule: 'Σ des dépenses du mois rattachées à une catégorie budgétée.',
  },
  budget_reste: {
    titre: 'Reste disponible',
    texte:
      "Ce qu'il reste à dépenser avant d'atteindre vos enveloppes. Négatif = budget global dépassé.",
    formule: 'Total prévu − total consommé.',
  },
  budget_taux: {
    titre: 'Taux de consommation',
    texte:
      "Part du budget déjà utilisée. Au-delà de 100 %, l'enveloppe est dépassée.",
    formule: '(Montant consommé ÷ montant prévu) × 100.',
  },
  budget_majeur: {
    titre: 'Budget global',
    texte:
      "Budget d'ensemble sur une catégorie majeure : il agrège automatiquement les dépenses de ses sous-catégories incluses.",
    formule: 'Σ des dépenses des sous-catégories incluses.',
  },

  // ---- Abonnements ----
  abo_total_mensuel: {
    titre: 'Total mensuel estimé',
    texte:
      "Poids mensuel estimé de vos abonnements actifs. Les fréquences non mensuelles sont ramenées à un équivalent par mois (estimatif).",
    formule: 'Σ (montant attendu × 30 ÷ nombre de jours de la fréquence).',
  },
  abo_en_retard: {
    titre: 'En retard',
    texte:
      "Abonnements actifs dont l'échéance attendue est passée sans qu'un flux correspondant ait été constaté.",
    formule: 'Nombre d’abonnements actifs dont l’échéance est dépassée.',
  },
  abo_seuil_divergence: {
    titre: 'Seuil de divergence',
    texte:
      "Écart toléré entre le montant attendu et le montant réellement prélevé. Au-delà, une divergence est signalée.",
    formule: '|montant réel − montant attendu| ÷ montant attendu, comparé au seuil.',
  },

  // ---- Patrimoine ----
  patrimoine_total: {
    titre: 'Patrimoine total estimé',
    texte:
      "Valeur estimative totale de vos actifs, d'après vos dernières valorisations manuelles. N'affecte jamais vos soldes bancaires.",
    formule: 'Σ des valeurs estimées actuelles de vos actifs.',
  },
  plus_value_latente: {
    titre: 'Plus-value latente estimée',
    texte:
      "Gain (ou perte) estimé non encore réalisé : la différence entre la valeur estimée aujourd'hui et le prix d'acquisition. « Latente » car vous ne l'encaissez qu'à la revente.",
    formule: 'Valeur estimée actuelle − valeur d’acquisition.',
  },

  // ---- Prévisionnel (briques de calcul) ----
  prev_solde_actuel: {
    titre: 'Solde actuel',
    texte:
      "Point de départ de la projection : vos soldes théoriques desquels on retire les flux datés dans le futur, pour les réintroduire ensuite brique par brique (évite de les compter deux fois).",
    formule: 'Σ soldes théoriques − Σ flux futurs déjà datés.',
  },
  prev_flux_futurs: {
    titre: 'Flux futurs datés du mois',
    texte:
      'Mouvements déjà saisis avec une date à venir dans le mois. Nature « engagé » : certitude quasi totale.',
    formule: 'Σ des flux prévisionnels datés d’ici la fin du mois.',
  },
  prev_abonnements: {
    titre: 'Abonnements à échoir (non budgétés)',
    texte:
      "Échéances d'abonnements attendues ce mois et pas encore matérialisées, hors celles déjà couvertes par un budget (pour éviter le double comptage). Nature « récurrent ».",
    formule: 'Σ des échéances d’abonnements restantes non budgétées.',
  },
  prev_reste_budgete: {
    titre: 'Reste à dépenser budgété',
    texte:
      "Estimation des dépenses encore à venir d'après vos budgets : la part non encore consommée des enveloppes. Nature « estimé » : fiabilité plus faible.",
    formule: 'Σ (montant prévu − montant consommé) des budgets du mois.',
  },
  prev_solde_projete: {
    titre: 'Solde projeté fin de mois',
    texte:
      "Estimation du solde à la fin du mois si tout se déroule comme prévu. Toujours « projeté » : le solde confirmé reste la seule vérité.",
    formule: 'Solde actuel + flux futurs + abonnements à échoir − reste à dépenser budgété.',
  },
  prev_capacite: {
    titre: 'Capacité à dépenser restante',
    texte:
      "Ce qu'il vous reste à dépenser sur vos budgets du mois, une fois retirés le déjà-consommé et les abonnements restants à couvrir.",
    formule: 'Budgets du mois − déjà consommé − abonnements restants.',
  },
}

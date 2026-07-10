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
      "Répartition de vos dépenses du mois par catégorie majeure. Les sous-catégories sont regroupées sous leur parent. Transferts et ajustements exclus. Cliquez une (sous-)catégorie pour voir le détail des flux.",
    formule: 'Σ des dépenses du mois, groupées par catégorie majeure.',
  },
  heatmap_depenses: {
    titre: 'Calendrier des dépenses',
    texte:
      "Intensité des dépenses jour par jour sur le mois en cours : plus une case est foncée, plus vous avez dépensé ce jour-là. Transferts et ajustements exclus. Fiabilité : réelle.",
    formule: 'Σ des dépenses (flux négatifs) de chaque jour du mois.',
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

  // ---- Système de points (mécanique B) ----
  valeur_point: {
    titre: 'Valeur du point',
    texte:
      "Conversion entre euros et points de discipline budgétaire. Une enveloppe « en jeu » rapporte des points si elle n'est pas dépassée, en fait perdre sinon. Paramètre du foyer, ajustable.",
    formule: '1 point = valeur_point € (défaut 10 €). Arrondi à l’entier supérieur.',
  },
  points_reserve: {
    titre: 'Réserve de points',
    texte:
      "Points accumulés (discipline budgétaire) sur les mois clôturés, reportés de mois en mois. Le mois en cours est projeté (non figé) : il n'entre dans la réserve disponible qu'à la clôture.",
    formule: 'Σ(points des mois clôturés) − Σ(points distribués). Peut être négatif.',
  },
  points_enveloppe: {
    titre: 'Points de l’enveloppe',
    texte:
      "Points générés par cette enveloppe. Positif si elle n'est pas dépassée, négatif si elle l'est. Réel à la clôture du mois, projeté tant que le mois est en cours.",
    formule: 'signe(prévu − consommé) × ⌈ |prévu − consommé| ÷ valeur_point ⌉.',
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

  // ---- Analyse des abonnements ----
  abo_total_annuel: {
    titre: 'Coût annuel estimé',
    texte:
      "Ce que vos abonnements actifs représentent sur une année entière — souvent plus parlant que le mensuel (un « petit » 12 €/mois = 144 €/an). Estimatif (référentiel).",
    formule: 'Σ (montant attendu × 365,25 ÷ nombre de jours de la fréquence).',
  },
  abo_poids_depenses: {
    titre: 'Poids sur les dépenses',
    texte:
      "Part de vos dépenses réelles moyennes que représentent les abonnements. Croise le total mensuel estimé (référentiel) avec vos dépenses réelles des derniers mois.",
    formule: 'total mensuel des abonnements ÷ dépenses réelles moyennes par mois × 100.',
  },
  abo_poids_revenus: {
    titre: 'Poids sur les revenus',
    texte:
      "Part de vos revenus réels moyens absorbée par les abonnements. Repère quand le récurrent devient lourd face à ce qui rentre.",
    formule: 'total mensuel des abonnements ÷ revenus réels moyens par mois × 100.',
  },
  abo_par_categorie: {
    titre: 'Abonnements par catégorie',
    texte:
      "Coût mensuel et annuel de vos abonnements regroupés par catégorie majeure (les sous-catégories sont regroupées sous leur parent). Estimatif.",
    formule: 'Σ des coûts mensuels normalisés, par catégorie.',
  },
  abo_par_titulaire: {
    titre: 'Qui paye quoi',
    texte:
      "Répartition du coût des abonnements par personne du foyer, selon le propriétaire du compte prélevé. Les comptes communs forment un groupe « Commun » à part. Cliquez sur une personne pour voir le détail et basculer un abonnement en commun. Estimatif.",
    formule: 'Σ des coûts mensuels des abonnements prélevés sur les comptes de chaque personne.',
  },
  abo_derive_prix: {
    titre: 'Dérive de prix',
    texte:
      "Écart entre le dernier montant réellement prélevé et le montant attendu — détecte les hausses de tarif silencieuses. Fiabilité réelle (flux générés).",
    formule: '(dernier montant réel − montant attendu) ÷ montant attendu × 100.',
  },
  abo_a_risque: {
    titre: 'Abonnements à surveiller',
    texte:
      "Abonnements méritant l'attention : en retard de prélèvement, montant divergent, ou jamais matérialisé en flux (potentiellement oublié). Signalétique, sans jugement.",
    formule: 'Signalement selon retard / divergence / absence de flux.',
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
    formule: 'Solde actuel + flux futurs datés − reste à dépenser budgété.',
  },
  prev_capacite: {
    titre: 'Capacité à dépenser restante',
    texte:
      "Ce qu'il vous reste à dépenser sur vos budgets du mois, une fois retiré le déjà-consommé.",
    formule: 'Budgets du mois − déjà consommé.',
  },

  // ---- Analyse rétrospective (Phase 13) ----
  analyse_tendances: {
    titre: 'Tendances',
    texte:
      "Évolution de vos dépenses, revenus et épargne mois par mois sur la période. Fiabilité réelle (basé sur les flux saisis) ; transferts et ajustements exclus.",
    formule:
      'Par mois comptable : dépenses = Σ montants négatifs, revenus = Σ montants positifs, épargne = revenus − dépenses.',
  },
  analyse_comparaison: {
    titre: 'Comparaison à la période précédente',
    texte:
      "Écart entre la période affichée et la période équivalente qui la précède immédiatement. Purement descriptif, sans jugement.",
    formule:
      '(total période actuelle − total période précédente) / |période précédente| × 100. Vide si la période précédente est nulle.',
  },
  analyse_epargne_encours: {
    titre: 'Encours d\'épargne',
    texte:
      "Somme actuelle des soldes de vos comptes marqués « épargne » (livrets, PEL, PEA…). Le stock accumulé. Fiabilité réelle.",
    formule: 'Σ solde des comptes est_epargne.',
  },
  analyse_epargne_versements: {
    titre: 'Épargne mise de côté',
    texte:
      "L'argent réellement transféré vers vos comptes d'épargne chaque mois (versements − retraits). À distinguer de l'épargne budgétaire (revenus − dépenses) : ici c'est ce qui finit vraiment sur un livret. Fiabilité réelle.",
    formule: 'Par mois : Σ montant des transferts sur les comptes d\'épargne (entrées +, sorties −), puis cumul.',
  },
  analyse_epargne_ecart: {
    titre: 'Écart budgétaire vs réel',
    texte:
      "Compare ce qui restait après dépenses (épargne budgétaire = revenus − dépenses) à ce qui a été réellement transféré sur un livret. Un écart positif signale du « reste » non encore épargné.",
    formule: 'Épargne budgétaire (revenus − dépenses) vs versement réel (transferts vers l\'épargne), mois par mois.',
  },
  taux_annuel: {
    titre: 'Taux annuel',
    texte:
      "Taux d'intérêt annuel du compte d'épargne (ex. 3 % pour un Livret A). Informatif pour l'instant ; il servira à projeter les intérêts dans le prévisionnel (à venir). N'entre pas dans les mesures d'épargne actuelles.",
    formule: 'Saisi par compte. La projection des intérêts composés viendra dans un incrément ultérieur.',
  },
  analyse_titulaires: {
    titre: 'Répartition par titulaire',
    texte:
      "Qui du foyer dépense, gagne et épargne, selon le propriétaire du compte. Les comptes communs forment un groupe « Commun » à part, jamais rattaché à une seule personne. Fiabilité réelle.",
    formule:
      'Flux regroupés par propriétaire du compte (comptes communs = bucket « Commun ») : dépenses, revenus, épargne = revenus − dépenses, part = dépenses / dépenses totales × 100.',
  },
  analyse_commun_perso: {
    titre: 'Commun vs perso',
    texte:
      "Comparaison entre les comptes communs du foyer et l'ensemble des comptes personnels. Aide à voir la part mutualisée. Descriptif, fiabilité réelle.",
    formule: 'Somme des dépenses/revenus des comptes est_commun d\'un côté, des comptes personnels de l\'autre.',
  },
  analyse_categories: {
    titre: 'Dépenses par catégorie dans le temps',
    texte:
      "Répartition des dépenses par catégorie majeure (les sous-catégories sont regroupées sous leur parent) et leur évolution sur la période. Fiabilité réelle.",
    formule:
      "Par catégorie : total sur la période, part = total / dépenses totales × 100, moyenne = total / nombre de mois.",
  },
  analyse_saisonnalite: {
    titre: 'Comparaison à l\'année précédente',
    texte:
      "Dépenses de chaque mois comptable clôturé face au même mois un an plus tôt, sur tout l'historique. Le mois en cours (partiel) est exclu. Descriptif, sans jugement ; fiabilité réelle.",
    formule:
      'Pour un mois : dépenses du mois vs dépenses du même mois l\'année précédente. Δ = (mois − année-1) / année-1 × 100 (vide si l\'année précédente est nulle).',
  },
  analyse_rythme_jour: {
    titre: 'Dépenses par jour de semaine',
    texte:
      "Sur quels jours de la semaine se concentrent vos dépenses, cumulées sur toute la période. Descriptif — aucun jugement.",
    formule: 'Σ des dépenses de la période regroupées selon le jour de la semaine de leur date.',
  },
  analyse_recurrents: {
    titre: 'Postes récurrents',
    texte:
      "Libellés de dépense qui reviennent au moins deux fois sur la période, pour repérer vos habitudes. Descriptif, sans jugement ni seuil.",
    formule:
      'Dépenses regroupées par libellé (casse et espaces normalisés), gardées si ≥ 2 occurrences, triées par montant cumulé.',
  },

  // ---- Paramètres du foyer ----
  mois_comptable: {
    titre: 'Mois comptable',
    texte:
      "Jour où débute votre mois budgétaire. Réglé sur 1, c'est le mois calendaire. Réglé par exemple sur 25 (jour de votre salaire), une période va du 25 au 24 du mois suivant et compte comme ce mois suivant : votre salaire et les dépenses qu'il finance restent regroupés.",
    formule:
      "Un mouvement daté au jour ≥ jour de bascule est rattaché au mois suivant ; sinon au mois courant. Borné à 28 (valide tous les mois).",
  },
}

import { useState } from 'react'
import { ChevronRight, ChevronDown, Receipt } from 'lucide-react'
import { formatEuro } from '../../utils/format'
import FluxCategorieModal from '../flux/FluxCategorieModal'

/**
 * Ventilation des dépenses par catégorie majeure : **liste de barres**
 * dépliable (majeures → mineures). `data` = liste renvoyée par l'API
 * (`depenses_par_categorie`), chaque entrée = { id, nom, total, sous_categories }.
 *
 * Drill-down : un clic sur une catégorie-feuille (sous-catégorie, ou majeure
 * sans sous-catégorie) ouvre le détail des flux du mois (`FluxCategorieModal`).
 * `mois` (1er du mois) est requis pour le drill-down ; `compteId` optionnel
 * scope le détail à un compte (dashboard par compte).
 *
 * ⚠️ **Pas d'anneau ici, et ce n'est pas un goût.** Le travail de cette donnée
 * est de **comparer des magnitudes** entre catégories ; un anneau ne permet pas
 * de départager deux parts voisines à l'œil, là où deux barres alignées sur la
 * même origine le font sans effort. *Analyse* rendait déjà la même information
 * en barres : c'est le Tableau de bord qui s'aligne, pas l'inverse.
 * (D21 de la revue UI/UX du 2026-08-20.)
 *
 * ⚠️ **Une seule teinte, pas douze.** Ici les catégories sont l'**axe**, pas des
 * séries : on lit une seule mesure — ce qui a été dépensé. Douze couleurs
 * n'existaient que pour distinguer les parts de l'anneau, et elles entraient en
 * collision avec la sémantique monétaire de l'application (turquoise = entrant,
 * rouge = sortant). La longueur porte la grandeur ; le montant et le
 * pourcentage sont écrits à côté, donc rien ne repose sur la couleur seule.
 */
export default function DepensesCategories({
  data,
  mois,
  compteId,
  emptyMessage = 'Aucune dépense catégorisée ce mois.',
}) {
  const [expandedId, setExpandedId] = useState(null)
  const [selectedCat, setSelectedCat] = useState(null) // { id, nom } | null

  if (!data || data.length === 0) {
    return (
      <p className="text-sm text-content-3 py-4 text-center">
        {emptyMessage}
      </p>
    )
  }

  const total = data.reduce((s, c) => s + Number(c.total), 0)
  // La barre se mesure contre la **plus grosse catégorie**, pas contre le total :
  // sur une répartition plate, des barres toutes à 8 % ne comparent rien.
  const maxi = data.reduce((m, c) => Math.max(m, Number(c.total)), 0)

  // Le drill-down n'est proposé que si on connaît le mois ciblé.
  const drillEnabled = !!mois
  const openFlux = (cat) =>
    drillEnabled && setSelectedCat({ id: cat.id, nom: cat.nom })

  return (
    <div className="flex flex-col gap-2 min-w-0">
      <p className="text-xs text-content-2">
        Total <span className="tabular-nums font-medium">{formatEuro(total)}</span>
      </p>

      {/* Liste de barres — voir l'en-tête du fichier pour le pourquoi. */}
      <div className="flex flex-col gap-0.5 min-w-0">
        {data.map((cat) => {
          const pct = total > 0 ? (Number(cat.total) / total) * 100 : 0
          const part = maxi > 0 ? (Number(cat.total) / maxi) * 100 : 0
          const isExpanded = expandedId === cat.id
          const hasSub = cat.sous_categories && cat.sous_categories.length > 0
          // Majeure sans mineure = feuille → cliquable pour le détail des flux.
          const isLeaf = !hasSub && drillEnabled

          return (
            <div key={cat.id}>
              <button
                onClick={() =>
                  hasSub ? setExpandedId(isExpanded ? null : cat.id) : openFlux(cat)
                }
                className={[
                  'group w-full flex items-center gap-2 py-1.5 px-2 -mx-2 rounded-md transition-colors',
                  hasSub || isLeaf ? 'hover:bg-surface-3 cursor-pointer' : 'cursor-default',
                ].join(' ')}
              >
                <span className="text-sm text-content flex-1 text-left truncate">{cat.nom}</span>
                <span className="text-xs text-content-2 w-20 text-right shrink-0 tabular-nums">
                  {formatEuro(cat.total)}
                </span>
                <span className="text-xs text-content-3 w-9 text-right shrink-0 tabular-nums">
                  {pct.toFixed(0)} %
                </span>
                <span className="w-3.5 shrink-0 flex justify-center">
                  {hasSub ? (
                    isExpanded
                      ? <ChevronDown size={12} className="text-content-3" />
                      : <ChevronRight size={12} className="text-content-3" />
                  ) : isLeaf ? (
                    <Receipt
                      size={12}
                      className="text-content-3 actions-ligne"
                    />
                  ) : null}
                </span>
              </button>

              {/* La barre : 4 px, ancrée à gauche comme toutes les autres, sur
                  un rail discret qui donne l'échelle sans la surcharger. */}
              <div className="h-1 rounded-full bg-surface-3 overflow-hidden -mt-0.5 mb-1">
                <div
                  className="h-full rounded-full bg-purple-600"
                  style={{ width: `${part}%` }}
                />
              </div>

              {isExpanded && hasSub && (
                <div className="ml-4 flex flex-col gap-0.5 mb-1">
                  {cat.sous_categories.map((m) => {
                    const mPct = total > 0 ? (Number(m.total) / total) * 100 : 0
                    const mPart = maxi > 0 ? (Number(m.total) / maxi) * 100 : 0
                    return (
                      <div key={m.id}>
                      <button
                        onClick={() => openFlux(m)}
                        className={[
                          'group w-full flex items-center gap-2 py-1 px-2 -mx-2 rounded-md transition-colors',
                          drillEnabled ? 'hover:bg-surface-3 cursor-pointer' : 'cursor-default',
                        ].join(' ')}
                      >
                        <span className="text-xs text-content-2 flex-1 text-left truncate">{m.nom}</span>
                        <span className="text-xs text-content-3 w-20 text-right shrink-0 tabular-nums">
                          {formatEuro(m.total)}
                        </span>
                        <span className="text-xs text-content-3 w-9 text-right shrink-0 tabular-nums">
                          {mPct.toFixed(0)} %
                        </span>
                        <span className="w-3.5 shrink-0 flex justify-center">
                          {drillEnabled && (
                            <Receipt
                              size={11}
                              className="text-content-3 actions-ligne"
                            />
                          )}
                        </span>
                      </button>
                      {/* Même échelle que les majeures — sinon deux barres de
                          même longueur ne diraient pas la même chose selon leur
                          niveau. Teinte plus claire : c'est un détail de la
                          ligne au-dessus, pas une grandeur concurrente. */}
                      <div className="h-1 rounded-full bg-surface-3 overflow-hidden -mt-0.5 mb-1">
                        <div
                          className="h-full rounded-full bg-purple-400"
                          style={{ width: `${mPart}%` }}
                        />
                      </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {drillEnabled && (
        <FluxCategorieModal
          categorie={selectedCat}
          mois={mois}
          compteId={compteId}
          onClose={() => setSelectedCat(null)}
        />
      )}
    </div>
  )
}

import { useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { formatEuro } from '../../utils/format'
import DoughnutChart from './DoughnutChart'
import { chartColors } from './chartSetup'

// Palette des catégories (donut + pastilles de légende), partagée par le
// dashboard global et le dashboard par compte.
export const CAT_PALETTE = [
  chartColors.purple,
  chartColors.teal,
  chartColors.amber,
  chartColors.red,
  chartColors.blue,
  '#8B5CF6',
  '#EC4899',
  '#14B8A6',
  '#F97316',
  '#84CC16',
  '#6366F1',
  chartColors.gray,
]

/**
 * Ventilation des dépenses par catégorie majeure : donut + légende dépliable
 * (majeures → mineures). `data` = liste renvoyée par l'API
 * (`depenses_par_categorie`), chaque entrée = { id, nom, total, sous_categories }.
 */
export default function DepensesCategories({ data, emptyMessage = 'Aucune dépense catégorisée ce mois.' }) {
  const [expandedId, setExpandedId] = useState(null)

  if (!data || data.length === 0) {
    return (
      <p className="text-sm text-content-3 py-4 text-center">
        {emptyMessage}
      </p>
    )
  }

  const total = data.reduce((s, c) => s + Number(c.total), 0)
  const labels = data.map((c) => c.nom)
  const values = data.map((c) => Number(c.total))
  const colors = data.map((_, i) => CAT_PALETTE[i % CAT_PALETTE.length])

  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:gap-6">
      {/* Donut */}
      <div className="w-full lg:w-44 shrink-0">
        <DoughnutChart labels={labels} values={values} colors={colors} height={176} />
        <p className="text-center text-xs text-content-3 mt-2">
          Total {formatEuro(total)}
        </p>
      </div>

      {/* Légende expandable */}
      <div className="flex-1 flex flex-col gap-0.5 min-w-0">
        {data.map((cat, i) => {
          const pct = total > 0 ? (Number(cat.total) / total) * 100 : 0
          const isExpanded = expandedId === cat.id
          const color = colors[i]
          const hasSub = cat.sous_categories && cat.sous_categories.length > 0

          return (
            <div key={cat.id}>
              <button
                onClick={() => hasSub && setExpandedId(isExpanded ? null : cat.id)}
                className={[
                  'w-full flex items-center gap-2 py-1.5 px-2 -mx-2 rounded-md transition-colors',
                  hasSub ? 'hover:bg-surface-3 cursor-pointer' : 'cursor-default',
                ].join(' ')}
              >
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: color }}
                />
                <span className="text-sm text-content flex-1 text-left truncate">{cat.nom}</span>
                <span className="text-xs text-content-2 w-20 text-right shrink-0 tabular-nums">
                  {formatEuro(cat.total)}
                </span>
                <span className="text-xs text-content-3 w-9 text-right shrink-0 tabular-nums">
                  {pct.toFixed(0)} %
                </span>
                <span className="w-3.5 shrink-0 flex justify-center">
                  {hasSub && (
                    isExpanded
                      ? <ChevronDown size={12} className="text-content-3" />
                      : <ChevronRight size={12} className="text-content-3" />
                  )}
                </span>
              </button>

              {isExpanded && hasSub && (
                <div className="ml-4 flex flex-col gap-0.5 mb-1">
                  {cat.sous_categories.map((m) => {
                    const mPct = total > 0 ? (Number(m.total) / total) * 100 : 0
                    return (
                      <div
                        key={m.id}
                        className="flex items-center gap-2 py-1 px-2 -mx-2"
                      >
                        <span className="w-2.5 shrink-0" />
                        <span className="w-1.5 h-1.5 rounded-full bg-content-3 shrink-0" />
                        <span className="text-xs text-content-2 flex-1 truncate">{m.nom}</span>
                        <span className="text-xs text-content-3 w-20 text-right shrink-0 tabular-nums">
                          {formatEuro(m.total)}
                        </span>
                        <span className="text-xs text-content-3 w-9 text-right shrink-0 tabular-nums">
                          {mPct.toFixed(0)} %
                        </span>
                        <span className="w-3.5 shrink-0" />
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

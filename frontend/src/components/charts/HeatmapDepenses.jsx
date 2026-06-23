import { useState } from 'react'
import { formatEuro } from '../../utils/format'
import FluxJourModal from '../flux/FluxJourModal'

const JOURS = ['L', 'M', 'M', 'J', 'V', 'S', 'D']

// 4 niveaux d'intensité (opacité du rouge « dépense »), alignés sur la légende.
// Plancher relevé à 0.4 pour rester lisible même sur le niveau le plus faible
// (un rouge trop transparent passait sous le texte en thème clair).
const NIVEAUX = [0.4, 0.6, 0.8, 1]

/**
 * Plafond de l'échelle de couleur : 90e centile des jours dépensés, et non le
 * max brut. Une dépense exceptionnelle (loyer, gros achat) n'écrase plus toute
 * l'échelle — sinon tous les autres jours retombaient au niveau le plus faible
 * et la heatmap devenait quasi monochrome. Les jours au-delà du plafond
 * saturent simplement au niveau maximal.
 */
function calculerPlafond(valeurs) {
  const nz = valeurs.filter((v) => v > 0).sort((a, b) => a - b)
  if (nz.length === 0) return 0
  const idx = Math.min(nz.length - 1, Math.floor(nz.length * 0.9))
  return nz[idx]
}

function niveauDe(total, plafond) {
  if (!total || plafond <= 0) return -1 // pas de dépense
  const ratio = Math.min(1, total / plafond)
  if (ratio <= 0.25) return 0
  if (ratio <= 0.5) return 1
  if (ratio <= 0.75) return 2
  return 3
}

/**
 * Heatmap calendaire des dépenses du mois courant : une cellule par jour,
 * colorée selon le montant dépensé ce jour-là (rouge = dépense). Fiabilité
 * réelle. `data` = liste `[{ date, total }]` (`depenses_par_jour` de l'API),
 * `mois` = "YYYY-MM-DD" (1er du mois). `compteId` optionnel scope le drill-down
 * à un compte. Cliquer un jour dépensé ouvre le détail des flux.
 */
export default function HeatmapDepenses({ data, mois, compteId }) {
  const [jourSelectionne, setJourSelectionne] = useState(null)

  if (!mois) return null

  const [year, moNum] = mois.split('-').map(Number)
  const monthIdx = moNum - 1
  const daysInMonth = new Date(year, monthIdx + 1, 0).getDate()
  // getDay() : 0=dim … 6=sam → on cale sur lundi=0.
  const firstWeekday = (new Date(year, monthIdx, 1).getDay() + 6) % 7

  const totalParJour = {}
  for (const j of data || []) {
    totalParJour[j.date] = Number(j.total)
  }
  const plafond = calculerPlafond(Object.values(totalParJour))

  const aujourdhui = new Date()
  const todayKey = `${aujourdhui.getFullYear()}-${String(aujourdhui.getMonth() + 1).padStart(2, '0')}-${String(aujourdhui.getDate()).padStart(2, '0')}`

  const cells = []
  for (let i = 0; i < firstWeekday; i++) cells.push(null)
  for (let day = 1; day <= daysInMonth; day++) {
    const key = `${year}-${String(moNum).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    const total = totalParJour[key] || 0
    cells.push({
      day,
      key,
      total,
      niveau: niveauDe(total, plafond),
      futur: key > todayKey, // jour à venir : donnée non encore connue
    })
  }

  if (plafond <= 0) {
    return (
      <p className="text-sm text-content-3 py-4 text-center">
        Aucune dépense ce mois.
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="grid grid-cols-7 gap-1">
        {JOURS.map((j, i) => (
          <div key={i} className="text-center text-[11px] text-content-3">
            {j}
          </div>
        ))}

        {cells.map((c, i) => {
          if (c === null) return <div key={`b-${i}`} />

          const cliquable = c.total > 0
          // Texte sombre/clair adaptatif (text-content) sur les niveaux faibles
          // — lisible dans les deux thèmes ; blanc sur les niveaux soutenus.
          const couleurTexte =
            c.niveau < 0 || c.niveau <= 1 ? 'text-content-3' : 'text-white'

          return (
            <div
              key={c.key}
              role={cliquable ? 'button' : undefined}
              tabIndex={cliquable ? 0 : undefined}
              onClick={cliquable ? () => setJourSelectionne(c.key) : undefined}
              onKeyDown={
                cliquable
                  ? (e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        setJourSelectionne(c.key)
                      }
                    }
                  : undefined
              }
              title={
                c.futur
                  ? `${c.day} : à venir`
                  : c.total > 0
                    ? `${c.day} : −${formatEuro(c.total)}`
                    : `${c.day} : aucune dépense`
              }
              aria-label={
                c.total > 0
                  ? `${c.day} : ${formatEuro(c.total)} de dépenses`
                  : undefined
              }
              className={[
                'h-12 sm:h-14 rounded-md flex items-start justify-end p-1 text-[10px] tabular-nums select-none',
                c.niveau < 0 ? 'bg-surface-3' : '',
                couleurTexte,
                c.futur ? 'opacity-40' : '',
                cliquable
                  ? 'cursor-pointer transition hover:ring-2 hover:ring-white/50 focus:outline-none focus:ring-2 focus:ring-white/60'
                  : '',
                c.key === todayKey ? 'ring-2 ring-purple-400' : '',
              ].join(' ')}
              style={
                c.niveau >= 0
                  ? { backgroundColor: `rgba(220, 38, 38, ${NIVEAUX[c.niveau]})` }
                  : undefined
              }
            >
              {c.day}
            </div>
          )
        })}
      </div>

      {/* Légende */}
      <div className="flex items-center justify-end gap-1.5 text-[11px] text-content-3">
        <span>Moins</span>
        <span className="w-3 h-3 rounded bg-surface-3" />
        {NIVEAUX.map((a) => (
          <span
            key={a}
            className="w-3 h-3 rounded"
            style={{ backgroundColor: `rgba(220, 38, 38, ${a})` }}
          />
        ))}
        <span>Plus</span>
      </div>

      <FluxJourModal
        date={jourSelectionne}
        compteId={compteId}
        onClose={() => setJourSelectionne(null)}
      />
    </div>
  )
}

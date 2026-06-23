import { formatEuro } from '../../utils/format'

const JOURS = ['L', 'M', 'M', 'J', 'V', 'S', 'D']

// 4 niveaux d'intensité (opacité du rouge « dépense »), alignés sur la légende.
const NIVEAUX = [0.25, 0.5, 0.75, 1]

function niveauDe(total, max) {
  if (!total || max <= 0) return -1 // pas de dépense
  const ratio = total / max
  if (ratio <= 0.25) return 0
  if (ratio <= 0.5) return 1
  if (ratio <= 0.75) return 2
  return 3
}

/**
 * Heatmap calendaire des dépenses du mois courant : une cellule par jour,
 * colorée selon le montant dépensé ce jour-là (rouge = dépense). Fiabilité
 * réelle. `data` = liste `[{ date, total }]` (`depenses_par_jour` de l'API),
 * `mois` = "YYYY-MM-DD" (1er du mois).
 */
export default function HeatmapDepenses({ data, mois }) {
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
  const max = Math.max(0, ...Object.values(totalParJour))

  const aujourdhui = new Date()
  const todayKey = `${aujourdhui.getFullYear()}-${String(aujourdhui.getMonth() + 1).padStart(2, '0')}-${String(aujourdhui.getDate()).padStart(2, '0')}`

  const cells = []
  for (let i = 0; i < firstWeekday; i++) cells.push(null)
  for (let day = 1; day <= daysInMonth; day++) {
    const key = `${year}-${String(moNum).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    const total = totalParJour[key] || 0
    cells.push({ day, key, total, niveau: niveauDe(total, max) })
  }

  if (max <= 0) {
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

        {cells.map((c, i) =>
          c === null ? (
            <div key={`b-${i}`} />
          ) : (
            <div
              key={c.key}
              title={
                c.total > 0
                  ? `${c.day} : −${formatEuro(c.total)}`
                  : `${c.day} : aucune dépense`
              }
              className={[
                'aspect-square rounded-md flex items-start justify-end p-1 text-[10px] tabular-nums select-none',
                c.niveau < 0 ? 'bg-surface-3 text-content-3' : 'text-white',
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
        )}
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
    </div>
  )
}

import { useMemo, useState } from 'react'
import { formatEuro } from '../../utils/format'

/**
 * Graphe nœud-lien fléché des transferts entre comptes.
 *
 * - Chaque compte = un nœud disposé en cercle.
 * - Chaque paire (source → destination) = une flèche courbe, épaisseur ∝ montant
 *   cumulé sur la période. La courbure sépare les allers-retours (A→B ≠ B→A).
 * - Survoler un nœud met en avant ses flèches ; survoler une flèche l'isole.
 *
 * 100 % SVG (aucune dépendance) ; responsive via viewBox. Fiabilité RÉELLE.
 */
const W = 680
const H = 460
const CX = W / 2
const CY = H / 2
const R = 158 // rayon du cercle des nœuds
const NODE_RX = 74
const NODE_RY = 26

export default function FluxGraph({ noeuds = [], liens = [] }) {
  const [actif, setActif] = useState(null) // id de nœud survolé
  const [lienActif, setLienActif] = useState(null) // index de lien survolé

  const positions = useMemo(() => {
    const map = {}
    const n = noeuds.length
    noeuds.forEach((nd, i) => {
      // Un seul nœud → centre ; sinon réparti sur le cercle, départ en haut.
      if (n === 1) {
        map[nd.id] = { x: CX, y: CY }
        return
      }
      const angle = -Math.PI / 2 + (i * 2 * Math.PI) / n
      map[nd.id] = { x: CX + R * Math.cos(angle), y: CY + R * Math.sin(angle) }
    })
    return map
  }, [noeuds])

  const maxTotal = useMemo(
    () => Math.max(1, ...liens.map((l) => Number(l.total))),
    [liens]
  )

  if (!noeuds.length) return null

  const epaisseur = (total) => 2 + (Number(total) / maxTotal) * 12

  const edges = liens.map((l, i) => {
    const a = positions[l.source]
    const b = positions[l.destination]
    if (!a || !b) return null

    // Boucle sur soi-même (rare) : petite boucle au-dessus du nœud.
    if (l.source === l.destination) {
      const path = `M ${a.x - 14} ${a.y - NODE_RY} C ${a.x - 40} ${a.y - 80}, ${a.x + 40} ${a.y - 80}, ${a.x + 14} ${a.y - NODE_RY}`
      return { i, l, path, mid: { x: a.x, y: a.y - 70 } }
    }

    // Point de contrôle décalé perpendiculairement (handedness constante →
    // A→B et B→A ne se superposent pas).
    const mx = (a.x + b.x) / 2
    const my = (a.y + b.y) / 2
    const dx = b.x - a.x
    const dy = b.y - a.y
    const len = Math.hypot(dx, dy) || 1
    const off = Math.min(60, len * 0.22)
    const cx = mx + (-dy / len) * off
    const cy = my + (dx / len) * off
    const path = `M ${a.x} ${a.y} Q ${cx} ${cy} ${b.x} ${b.y}`
    // Point à t=0.5 sur la quadratique (pour l'étiquette).
    const mid = {
      x: 0.25 * a.x + 0.5 * cx + 0.25 * b.x,
      y: 0.25 * a.y + 0.5 * cy + 0.25 * b.y,
    }
    return { i, l, path, mid }
  }).filter(Boolean)

  const estMisEnAvant = (edge) => {
    if (lienActif !== null) return edge.i === lienActif
    if (actif) return edge.l.source === actif || edge.l.destination === actif
    return true
  }
  const rien = lienActif !== null || actif !== null

  return (
    <div className="w-full overflow-x-auto">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full text-content"
        style={{ maxHeight: 480 }}
        role="img"
        aria-label="Graphe des transferts entre comptes"
      >
        <defs>
          <marker
            id="fg-arrow" markerWidth="9" markerHeight="9" refX="7" refY="3"
            orient="auto" markerUnits="userSpaceOnUse"
          >
            <path d="M0,0 L7,3 L0,6 Z" fill="#8b5cf6" />
          </marker>
          <marker
            id="fg-arrow-on" markerWidth="11" markerHeight="11" refX="7" refY="3.5"
            orient="auto" markerUnits="userSpaceOnUse"
          >
            <path d="M0,0 L8,3.5 L0,7 Z" fill="#6d28d9" />
          </marker>
        </defs>

        {/* Flèches */}
        {edges.map((edge) => {
          const on = estMisEnAvant(edge)
          return (
            <g
              key={edge.i}
              onMouseEnter={() => setLienActif(edge.i)}
              onMouseLeave={() => setLienActif(null)}
              style={{ cursor: 'pointer' }}
            >
              {/* Trait invisible large pour faciliter le survol */}
              <path d={edge.path} fill="none" stroke="transparent" strokeWidth="16" />
              <path
                d={edge.path}
                fill="none"
                stroke={on ? '#6d28d9' : '#8b5cf6'}
                strokeWidth={epaisseur(edge.l.total)}
                strokeLinecap="round"
                opacity={rien && !on ? 0.12 : on ? 0.95 : 0.55}
                markerEnd={on ? 'url(#fg-arrow-on)' : 'url(#fg-arrow)'}
              />
              {on && (
                <g>
                  <rect
                    x={edge.mid.x - 34} y={edge.mid.y - 11} width="68" height="18" rx="4"
                    fill="#6d28d9"
                  />
                  <text
                    x={edge.mid.x} y={edge.mid.y + 2} textAnchor="middle"
                    fontSize="11" fontWeight="600" fill="#ffffff"
                  >
                    {formatEuro(edge.l.total)}
                  </text>
                </g>
              )}
            </g>
          )
        })}

        {/* Nœuds */}
        {noeuds.map((nd) => {
          const p = positions[nd.id]
          if (!p) return null
          const on = actif === nd.id
          const dim = rien && !on &&
            !(lienActif !== null && edges[lienActif] &&
              (edges[lienActif].l.source === nd.id || edges[lienActif].l.destination === nd.id))
          return (
            <g
              key={nd.id}
              onMouseEnter={() => setActif(nd.id)}
              onMouseLeave={() => setActif(null)}
              style={{ cursor: 'pointer' }}
              opacity={dim ? 0.35 : 1}
            >
              <rect
                x={p.x - NODE_RX} y={p.y - NODE_RY}
                width={NODE_RX * 2} height={NODE_RY * 2} rx="10"
                className="fill-surface-3"
                stroke={nd.est_epargne ? '#0d9488' : '#8b5cf6'}
                strokeWidth={on ? 2.5 : 1.5}
              />
              <text
                x={p.x} y={p.y - 3} textAnchor="middle"
                fontSize="12" fontWeight="600" fill="currentColor"
              >
                {tronquer(nd.nom, 14)}
              </text>
              <text
                x={p.x} y={p.y + 13} textAnchor="middle"
                fontSize="10.5"
                fill={Number(nd.solde_net) >= 0 ? '#0d9488' : '#dc2626'}
              >
                {Number(nd.solde_net) >= 0 ? '+' : ''}{formatEuro(nd.solde_net)}
              </text>
            </g>
          )
        })}
      </svg>

      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-content-2 mt-1 px-1">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-3 h-0.5 rounded" style={{ background: '#8b5cf6' }} />
          Épaisseur ∝ montant transféré
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded border-2" style={{ borderColor: '#0d9488' }} />
          Compte d'épargne
        </span>
        <span className="text-content-3">Solde net = reçu − envoyé sur la période</span>
      </div>
    </div>
  )
}

function tronquer(s, n) {
  if (!s) return ''
  return s.length > n ? s.slice(0, n - 1) + '…' : s
}

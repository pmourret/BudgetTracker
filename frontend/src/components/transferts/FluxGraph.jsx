import { useEffect, useMemo, useState } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  MarkerType,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { PiggyBank, Maximize2, X } from 'lucide-react'
import { useThemeStore } from '../../stores/themeStore'
import { formatEuro } from '../../utils/format'

/**
 * Graphe nœud-lien fléché des transferts entre comptes (React Flow).
 *
 * Layout en couches selon le rôle du compte sur la période :
 *   émetteurs purs (gauche) → comptes mixtes (centre) → récepteurs purs (droite).
 * Chaque flèche va de la source vers la destination, son épaisseur est
 * proportionnelle au montant cumulé ; les flux vers un compte d'épargne sont
 * colorés en teal. Nœuds déplaçables, zoom/pan. Fiabilité RÉELLE.
 *
 * Props : noeuds [{id, nom, solde_net, est_epargne, est_commun, ...}],
 *         liens  [{source, destination, source_nom, destination_nom, total, nb}].
 */
const PURPLE = '#8b5cf6'
const TEAL = '#0d9488'

const COL_X = [40, 340, 640]
const ROW_H = 104
const NODE_H = 64

function CompteNode({ data }) {
  const net = Number(data.solde_net)
  const positif = net >= 0
  return (
    <div
      className="rounded-xl border bg-surface-3 px-3 py-2 shadow-sm w-[180px]"
      style={{ borderColor: data.est_epargne ? TEAL : 'var(--color-border-app)', borderWidth: data.est_epargne ? 2 : 1 }}
    >
      <Handle type="target" position={Position.Left} style={{ background: '#94a3b8', width: 7, height: 7 }} />
      <div className="flex items-center gap-1.5 min-w-0">
        {data.est_epargne && <PiggyBank size={13} className="text-teal-texte dark:text-teal-400 shrink-0" />}
        <span className="text-[13px] font-medium text-content truncate">{data.nom}</span>
      </div>
      <div className="flex items-center justify-between mt-0.5">
        <span className="text-[10px] uppercase tracking-wide text-content-3">solde net</span>
        <span className={`text-[12px] font-semibold tabular-nums ${positif ? 'text-teal-texte dark:text-teal-400' : 'text-red-texte dark:text-red-400'}`}>
          {positif ? '+' : ''}{formatEuro(net)}
        </span>
      </div>
      <Handle type="source" position={Position.Right} style={{ background: '#94a3b8', width: 7, height: 7 }} />
    </div>
  )
}

const nodeTypes = { compte: CompteNode }

export default function FluxGraph({ noeuds = [], liens = [] }) {
  const isDark = useThemeStore((s) => s.isDark)
  const [expanded, setExpanded] = useState(false)

  // Overlay plein écran : Échap pour fermer + verrou du scroll de la page.
  useEffect(() => {
    if (!expanded) return
    const onEsc = (e) => { if (e.key === 'Escape') setExpanded(false) }
    document.addEventListener('keydown', onEsc)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onEsc)
      document.body.style.overflow = ''
    }
  }, [expanded])

  const { nodes, edges } = useMemo(() => {
    if (!noeuds.length) return { nodes: [], edges: [] }

    const outSet = new Set(liens.map((l) => l.source))
    const inSet = new Set(liens.map((l) => l.destination))

    // Rôle → colonne : émetteur pur (0), mixte (1), récepteur pur (2).
    const colonneDe = (id) => {
      const emet = outSet.has(id)
      const recoit = inSet.has(id)
      if (emet && !recoit) return 0
      if (recoit && !emet) return 2
      return 1
    }

    const parColonne = [[], [], []]
    noeuds.forEach((n) => parColonne[colonneDe(n.id)].push(n))

    const hauteurMax = Math.max(...parColonne.map((c) => c.length), 1)
    const pos = {}
    parColonne.forEach((col, ci) => {
      const offset = ((hauteurMax - col.length) * ROW_H) / 2
      col.forEach((n, ri) => {
        pos[n.id] = { x: COL_X[ci], y: offset + ri * ROW_H }
      })
    })

    const nodes = noeuds.map((n) => ({
      id: n.id,
      type: 'compte',
      position: pos[n.id] ?? { x: 0, y: 0 },
      data: n,
      draggable: true,
    }))

    const maxTotal = Math.max(1, ...liens.map((l) => Number(l.total)))
    const epargneIds = new Set(noeuds.filter((n) => n.est_epargne).map((n) => n.id))

    const edges = liens.map((l, i) => {
      const versEpargne = epargneIds.has(l.destination)
      const couleur = versEpargne ? TEAL : PURPLE
      const w = 1.5 + (Number(l.total) / maxTotal) * 6
      return {
        id: `e${i}`,
        source: l.source,
        target: l.destination,
        type: 'default',
        animated: true,
        label: `${formatEuro(l.total)}${l.nb > 1 ? `  ·  ${l.nb}×` : ''}`,
        labelStyle: { fill: '#ffffff', fontWeight: 600, fontSize: 11 },
        labelBgStyle: { fill: couleur },
        labelBgPadding: [6, 3],
        labelBgBorderRadius: 4,
        style: { stroke: couleur, strokeWidth: w },
        markerEnd: { type: MarkerType.ArrowClosed, color: couleur, width: 16, height: 16 },
      }
    })

    return { nodes, edges }
  }, [noeuds, liens])

  if (!noeuds.length) return null

  const canvas = (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      colorMode={isDark ? 'dark' : 'light'}
      fitView
      fitViewOptions={{ padding: 0.18 }}
      minZoom={0.3}
      maxZoom={2}
      nodesConnectable={false}
      nodesDraggable
      elementsSelectable={false}
      proOptions={{ hideAttribution: false }}
    >
      <Background gap={18} size={1} />
      <Controls showInteractive={false} />
    </ReactFlow>
  )

  const legende = (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-content-2 mt-2 px-1">
      <span className="inline-flex items-center gap-1.5">
        <span className="inline-block w-4 h-0.5 rounded" style={{ background: PURPLE }} /> Virement
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="inline-block w-4 h-0.5 rounded" style={{ background: TEAL }} /> Vers l'épargne
      </span>
      <span className="text-content-3">Épaisseur ∝ montant · gauche = émet, droite = reçoit · glissez les nœuds</span>
    </div>
  )

  return (
    <div>
      <div style={{ height: 460 }} className="relative rounded-lg border border-border-app overflow-hidden">
        {!expanded && canvas}
        <button
          onClick={() => setExpanded(true)}
          title="Agrandir le graphe"
          aria-label="Agrandir le graphe"
          className="absolute top-2 right-2 z-10 inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md bg-surface/90 border border-border-app text-xs text-content-2 hover:text-content cursor-pointer backdrop-blur-sm"
        >
          <Maximize2 size={14} /> Agrandir
        </button>
      </div>

      {legende}

      {expanded && (
        <div
          onClick={() => setExpanded(false)}
          className="fixed inset-0 z-[70] bg-slate-900/60 flex items-stretch lg:items-center justify-center p-0 lg:p-4"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-surface flex flex-col overflow-hidden w-full h-dvh rounded-none lg:w-[95vw] lg:h-[92dvh] lg:rounded-xl"
          >
            <div className="flex justify-between items-center px-5 py-3 border-b border-border-app shrink-0">
              <span className="text-base font-medium text-content">Graphe des virements</span>
              <button
                onClick={() => setExpanded(false)}
                aria-label="Fermer"
                className="text-content-2 p-1 cursor-pointer hover:text-content"
              >
                <X size={20} />
              </button>
            </div>
            <div className="relative flex-1 min-h-0">{canvas}</div>
            <div className="px-5 py-2.5 border-t border-border-app shrink-0">{legende}</div>
          </div>
        </div>
      )}
    </div>
  )
}

import { useState, lazy, Suspense } from 'react'
import useTransfertsAnalyse from '../../hooks/useTransfertsAnalyse'
import { formatEuro } from '../../utils/format'
import { DEFINITIONS } from '../../constants/definitions'
import { ArrowRight, Repeat } from 'lucide-react'
import Card from '../ui/Card'
import Tooltip from '../ui/Tooltip'
import PeriodSelector from '../ui/PeriodSelector'
import { Loading, ErrorState, EmptyState } from '../ui/States'
import BarChart from '../charts/BarChart'
import Metric, { MetricRow } from '../ui/Metric'

// React Flow est lourd (~180 kB) : chargé à la demande, uniquement quand
// l'onglet Analyse est ouvert (il n'est pas l'onglet par défaut).
const FluxGraph = lazy(() => import('./FluxGraph'))

function moisCourt(iso) {
  return new Date(iso).toLocaleDateString('fr-FR', { month: 'short', year: '2-digit' })
}

export default function TransfertsAnalyse() {
  const [nbMois, setNbMois] = useState(6)
  const { data, isLoading, isError, refetch } = useTransfertsAnalyse(nbMois)

  const synthese = data?.synthese ?? {}
  const liens = data?.liens ?? []
  const noeuds = data?.noeuds ?? []
  const parMois = data?.par_mois ?? []
  const aucun = !isLoading && !isError && liens.length === 0

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <span className="text-sm font-medium text-content">Circulation entre comptes</span>
          <span className="text-[11px] uppercase tracking-wide text-teal-texte dark:text-teal-400">réel</span>
        </div>
        <PeriodSelector value={nbMois} onChange={setNbMois} options={[3, 6, 12]} />
      </div>

      {isLoading && <Loading message="Chargement de l'analyse..." />}
      {isError && <ErrorState message="Impossible de charger l'analyse des transferts." onRetry={refetch} />}

      {!isLoading && !isError && (
        <>
          {/* Synthèse */}
          <MetricRow colonnes={4}>
            <Metric
              label="Volume transféré" value={formatEuro(synthese.total)}
              def={DEFINITIONS.transferts_volume}
            />
            <Metric label="Virements" value={String(synthese.nb ?? 0)} />
            <Metric label="Comptes concernés" value={String(synthese.nb_comptes ?? 0)} />
            <Metric
              label="Moyenne / mois" value={formatEuro(synthese.moyenne_mensuelle)}
              def={DEFINITIONS.transferts_moyenne} defAlign="right"
            />
          </MetricRow>

          {aucun ? (
            <EmptyState
              Icon={Repeat}
              message="Aucun transfert sur cette période. Élargissez la fenêtre ou créez un transfert."
            />
          ) : (
            <>
              {/* Graphe fléché */}
              <Card>
                <div className="flex items-center gap-2 mb-2">
                  <h3 className="text-sm font-medium text-content flex items-center gap-1">
                    Graphe des virements
                    <Tooltip {...DEFINITIONS.transferts_graphe} />
                  </h3>
                </div>
                <Suspense fallback={<Loading message="Chargement du graphe..." />}>
                  <FluxGraph noeuds={noeuds} liens={liens} />
                </Suspense>
              </Card>

              {/* Volume par mois */}
              <Card>
                <h3 className="text-sm font-medium text-content mb-3">Volume par mois</h3>
                <BarChart
                  labels={parMois.map((m) => moisCourt(m.mois))}
                  datasets={[{
                    label: 'Transféré',
                    data: parMois.map((m) => Number(m.total)),
                    color: '#8b5cf6',
                  }]}
                  height={200}
                />
              </Card>

              {/* Détail des liens */}
              <Card>
                <h3 className="text-sm font-medium text-content mb-3">
                  Détail des flux ({liens.length})
                </h3>
                <div className="flex flex-col divide-y divide-border-app">
                  {liens.map((l, i) => (
                    <div key={i} className="flex items-center gap-2 py-2.5 text-sm">
                      <Repeat size={14} className="text-content-3 shrink-0" />
                      <div className="flex items-center gap-1.5 min-w-0 flex-1">
                        <span className="text-content truncate">{l.source_nom}</span>
                        <ArrowRight size={13} className="text-content-3 shrink-0" />
                        <span className="text-content truncate">{l.destination_nom}</span>
                      </div>
                      <span className="text-xs text-content-2 shrink-0">
                        {l.nb} virement{l.nb > 1 ? 's' : ''}
                      </span>
                      <span className="text-content font-medium tabular-nums shrink-0 w-24 text-right">
                        {formatEuro(l.total)}
                      </span>
                    </div>
                  ))}
                </div>
              </Card>
            </>
          )}
        </>
      )}
    </div>
  )
}


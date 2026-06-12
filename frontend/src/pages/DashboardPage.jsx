import { useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import apiClient from '../api/client'
import { formatEuro, formatDate, formatMonth, formatPercent } from '../utils/format'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Tooltip from '../components/ui/Tooltip'
import { DEFINITIONS } from '../constants/definitions'
import PeriodSelector from '../components/ui/PeriodSelector'
import { Loading, ErrorState } from '../components/ui/States'
import LineChart from '../components/charts/LineChart'
import DoughnutChart from '../components/charts/DoughnutChart'
import { chartColors } from '../components/charts/chartSetup'

const CAT_PALETTE = [
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

function useDashboard(nbMois) {
  return useQuery({
    queryKey: ['analytics', 'dashboard', nbMois],
    queryFn: async () => {
      const { data } = await apiClient.get('/analytics/dashboard/', {
        params: { nb_mois: nbMois },
      })
      return data
    },
  })
}

const NIVEAU_VARIANT = {
  CRITIQUE: 'critique',
  AVERTISSEMENT: 'avertissement',
  INFO: 'info',
}

export default function DashboardPage() {
  const [nbMois, setNbMois] = useState(6)
  const { data, isLoading, isError, refetch } = useDashboard(nbMois)

  if (isLoading) return <Loading message="Chargement du tableau de bord..." />
  if (isError) {
    return <ErrorState message="Impossible de charger le tableau de bord." onRetry={refetch} />
  }

  const m = data.metriques
  const evolutionLabels = data.evolution_solde.map((p) => {
    const d = new Date(p.mois)
    return d.toLocaleDateString('fr-FR', { month: 'short', year: '2-digit' })
  })
  const evolutionValues = data.evolution_solde.map((p) => Number(p.solde))

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-lg font-medium text-content">Tableau de bord</h1>
        <p className="text-sm text-content-2 mt-0.5 capitalize">
          {formatMonth(data.mois_courant)}
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5">
        <MetricCard label="Solde total" value={formatEuro(m.solde_total)} def={DEFINITIONS.solde_total} />
        <MetricCard
          label="Dépenses du mois"
          value={`−${formatEuro(m.depenses_mois)}`}
          valueClass="text-red-600"
          def={DEFINITIONS.depenses_mois}
        />
        <MetricCard
          label="Revenus du mois"
          value={`+${formatEuro(m.revenus_mois)}`}
          valueClass="text-teal-600"
          def={DEFINITIONS.revenus_mois}
        />
        <MetricCard
          label="Épargne nette"
          value={formatEuro(m.epargne_nette)}
          valueClass={Number(m.epargne_nette) >= 0 ? 'text-purple-400' : 'text-red-600'}
          sub={`${formatPercent(m.taux_epargne)} du revenu`}
          def={DEFINITIONS.epargne_nette}
          defAlign="right"
        />
      </div>

      <Card
        title="Évolution du solde"
        action={<PeriodSelector value={nbMois} onChange={setNbMois} />}
      >
        <LineChart
          labels={evolutionLabels}
          datasets={[
            { label: 'Solde', data: evolutionValues, color: chartColors.purple, fill: true },
          ]}
          height={220}
        />
      </Card>

      <Card
        title={
          <span className="inline-flex items-center gap-1">
            Dépenses par catégorie
            <Tooltip {...DEFINITIONS.depenses_par_categorie} align="left" />
          </span>
        }
      >
        <DepensesCategories data={data.depenses_par_categorie} />
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <Card title="Budgets du mois">
          {data.budgets.length === 0 ? (
            <p className="text-sm text-content-3 py-4 text-center">Aucun budget ce mois.</p>
          ) : (
            <div className="flex flex-col gap-3">
              {data.budgets.slice(0, 5).map((b) => (
                <BudgetLine key={b.id} budget={b} />
              ))}
            </div>
          )}
        </Card>

        <Card title="Derniers flux">
          {data.derniers_flux.length === 0 ? (
            <p className="text-sm text-content-3 py-4 text-center">Aucun flux récent.</p>
          ) : (
            <div className="flex flex-col">
              {data.derniers_flux.map((f) => (
                <FluxLine key={f.id} flux={f} />
              ))}
            </div>
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <Card title="Alertes récentes">
          {data.alertes.length === 0 ? (
            <p className="text-sm text-content-3 py-4 text-center">
              Aucune alerte en attente.
            </p>
          ) : (
            <div className="flex flex-col gap-2.5">
              {data.alertes.map((a) => (
                <div key={a.id} className="flex items-start gap-2.5">
                  <Badge variant={NIVEAU_VARIANT[a.niveau] || 'info'}>
                    {a.type_alerte_display}
                  </Badge>
                  <span className="text-xs text-content-2 leading-relaxed flex-1">
                    {a.explication}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card
          title={
            <span className="inline-flex items-center gap-1">
              Patrimoine estimé
              <Tooltip {...DEFINITIONS.patrimoine_estime} align="right" />
            </span>
          }
        >
          <div className="flex flex-col items-center justify-center py-3">
            <div className="text-3xl font-medium text-content">
              {formatEuro(data.patrimoine.total_estime)}
            </div>
            <span className="mt-2 text-[11px] text-amber-800 bg-amber-50 rounded-full px-2.5 py-0.5">
              Valeur estimative
            </span>
            <p className="text-[11px] text-content-3 mt-2 text-center leading-relaxed">
              Estimation indépendante du solde bancaire,
              <br />basée sur vos valorisations manuelles.
            </p>
          </div>
        </Card>
      </div>
    </div>
  )
}

function MetricCard({ label, value, valueClass = 'text-content', sub, def, defAlign = 'left' }) {
  return (
    <div className="bg-surface border border-border-app rounded-xl px-4 py-3.5">
      <div className="text-xs text-content-2 mb-1 flex items-center gap-1">
        {label}
        {def && <Tooltip {...def} align={defAlign} />}
      </div>
      <div className={`text-xl font-medium ${valueClass}`}>{value}</div>
      {sub && <div className="text-[11px] text-teal-600 mt-0.5">{sub}</div>}
    </div>
  )
}

function BudgetLine({ budget }) {
  const taux = Number(budget.taux_consommation)
  const largeur = Math.min(taux, 100)
  const barColor = taux >= 100 ? 'bg-red-600' : taux >= 80 ? 'bg-amber-600' : 'bg-teal-600'
  const pctColor = taux >= 100 ? 'text-red-600' : taux >= 80 ? 'text-amber-600' : 'text-content-2'

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-content w-28 shrink-0 truncate">
        {budget.categorie_nom}
      </span>
      <div className="flex-1 h-1.5 bg-surface-3 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${barColor}`} style={{ width: `${largeur}%` }} />
      </div>
      <span className={`text-xs w-10 text-right shrink-0 ${pctColor}`}>
        {taux.toFixed(0)} %
      </span>
    </div>
  )
}

function FluxLine({ flux }) {
  const value = Number(flux.montant)
  const isDepense = value < 0
  return (
    <div className="flex justify-between items-center py-2 border-b border-border-app last:border-b-0">
      <div>
        <div className="text-sm text-content">{flux.libelle}</div>
        <div className="text-xs text-content-3">
          {flux.categorie_nom || '—'} · {formatDate(flux.date_flux)}
        </div>
      </div>
      <span className={`text-sm font-medium ${isDepense ? 'text-red-600' : 'text-teal-600'}`}>
        {formatEuro(value)}
      </span>
    </div>
  )
}

function DepensesCategories({ data }) {
  const [expandedId, setExpandedId] = useState(null)

  if (!data || data.length === 0) {
    return (
      <p className="text-sm text-content-3 py-4 text-center">
        Aucune dépense catégorisée ce mois.
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
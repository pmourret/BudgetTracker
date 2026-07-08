import { useState } from 'react'
import { ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react'
import useAnalyse from '../hooks/useAnalyse'
import { formatEuro, formatPercent } from '../utils/format'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Tooltip from '../components/ui/Tooltip'
import { DEFINITIONS } from '../constants/definitions'
import PeriodSelector from '../components/ui/PeriodSelector'
import { ErrorState, EmptyState } from '../components/ui/States'
import BarChart from '../components/charts/BarChart'
import { chartColors } from '../components/charts/chartSetup'
import { CAT_PALETTE } from '../components/charts/DepensesCategories'

const JOURS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
const TOP_CATEGORIES = 7 // au-delà : regroupées sous « Autres »

function moisLabel(iso) {
  return new Date(iso).toLocaleDateString('fr-FR', { month: 'short', year: '2-digit' })
}

export default function AnalysePage() {
  const [nbMois, setNbMois] = useState(6)
  const { data, isLoading, isError, refetch } = useAnalyse(nbMois)

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-medium text-content">Analyse</h1>
          <p className="text-sm text-content-2 mt-0.5">
            Où part l'argent, quand et comment — rétrospective réelle sur la période.
          </p>
        </div>
        <PeriodSelector value={nbMois} onChange={setNbMois} options={[3, 6, 12, 24]} />
      </div>

      {isLoading && <AnalyseSkeleton />}

      {isError && (
        <ErrorState message="Impossible de charger l'analyse." onRetry={refetch} />
      )}

      {!isLoading && !isError && data && (
        estVide(data) ? (
          <EmptyState
            icon="📊"
            message="Pas encore de dépenses sur la période. Ajoutez des flux pour alimenter l'analyse."
          />
        ) : (
          <>
            <TendancesCard bloc={data.tendances} />
            <TitulairesCard bloc={data.titulaires} />
            <CategoriesCard bloc={data.categories} series={data.tendances.series} />
            <RythmeCard bloc={data.rythme} />
          </>
        )
      )}
    </div>
  )
}

function estVide(data) {
  const t = data.tendances.totaux_periode
  return (
    Number(t.depenses) === 0 &&
    Number(t.revenus) === 0 &&
    data.categories.par_categorie.length === 0
  )
}

/* -------------------------------------------------------------------------- */
/* Tendances                                                                  */
/* -------------------------------------------------------------------------- */
function TendancesCard({ bloc }) {
  const labels = bloc.series.map((p) => moisLabel(p.mois))
  const datasets = [
    { label: 'Dépenses', data: bloc.series.map((p) => Number(p.depenses)), color: chartColors.red },
    { label: 'Revenus', data: bloc.series.map((p) => Number(p.revenus)), color: chartColors.teal },
  ]
  const cmp = bloc.comparaison_periode_precedente

  return (
    <Card
      title={
        <span className="inline-flex items-center gap-1">
          Tendances
          <Tooltip {...DEFINITIONS.analyse_tendances} align="left" />
        </span>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
          <RecapTile
            label="Revenus"
            total={bloc.totaux_periode.revenus}
            moyenne={bloc.moyennes_mensuelles.revenus}
            variation={cmp.revenus.variation_pct}
          />
          <RecapTile
            label="Dépenses"
            total={bloc.totaux_periode.depenses}
            moyenne={bloc.moyennes_mensuelles.depenses}
            variation={cmp.depenses.variation_pct}
          />
          <RecapTile
            label="Épargne nette"
            total={bloc.totaux_periode.epargne_nette}
            moyenne={bloc.moyennes_mensuelles.epargne_nette}
            variation={cmp.epargne_nette.variation_pct}
            suffixe={`taux ${formatPercent(bloc.totaux_periode.taux_epargne)}`}
          />
        </div>

        <BarChart labels={labels} datasets={datasets} height={240} />

        <p className="text-[11px] text-content-3 leading-relaxed inline-flex items-center gap-1">
          Comparaison à la période précédente
          <Tooltip {...DEFINITIONS.analyse_comparaison} align="left" size={12} />
        </p>
      </div>
    </Card>
  )
}

function RecapTile({ label, total, moyenne, variation, suffixe }) {
  return (
    <div className="bg-surface-2 rounded-lg p-3 flex flex-col gap-1">
      <span className="text-xs text-content-2">{label}</span>
      <span className="text-xl font-medium text-content tabular-nums">
        {formatEuro(total)}
      </span>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[11px] text-content-3">
          {formatEuro(moyenne)}/mois
        </span>
        <VariationChip variation={variation} />
      </div>
      {suffixe && <span className="text-[11px] text-content-3">{suffixe}</span>}
    </div>
  )
}

// Δ descriptif, volontairement neutre (gris, pas de rouge/vert) : aucun
// jugement sur les variations (arbitrage foyer « pas de mise en avant »).
function VariationChip({ variation }) {
  if (variation === null || variation === undefined) {
    return <span className="text-[11px] text-content-3">— nouveau</span>
  }
  const n = Number(variation)
  const Icon = n > 0 ? ArrowUpRight : n < 0 ? ArrowDownRight : Minus
  return (
    <span className="inline-flex items-center gap-0.5 text-[11px] text-content-3 tabular-nums">
      <Icon size={12} />
      {Math.abs(n).toFixed(1).replace('.', ',')} %
    </span>
  )
}

/* -------------------------------------------------------------------------- */
/* Ventilation par titulaire                                                  */
/* -------------------------------------------------------------------------- */
function TitulairesCard({ bloc }) {
  const buckets = bloc.par_titulaire
  const total = Number(bloc.total_depenses) || 0
  const cvp = bloc.commun_vs_perso
  const communDep = Number(cvp.commun.depenses)
  const persoDep = Number(cvp.perso.depenses)
  const totalCvp = communDep + persoDep

  return (
    <Card
      title={
        <span className="inline-flex items-center gap-1">
          Répartition par titulaire
          <Tooltip {...DEFINITIONS.analyse_titulaires} align="left" />
        </span>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-col divide-y divide-border-app">
          {buckets.map((b, i) => (
            <div key={b.id} className="flex items-center gap-3 py-2">
              <span
                className="w-2.5 h-2.5 rounded-full shrink-0"
                style={{ background: CAT_PALETTE[i % CAT_PALETTE.length] }}
              />
              <div className="flex-1 min-w-0">
                <div className="text-sm text-content truncate flex items-center gap-1.5">
                  {b.nom}
                  {b.est_commun && <Badge variant="purple">Commun</Badge>}
                </div>
                <div className="h-1 mt-1 bg-surface-3 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${total > 0 ? (Number(b.depenses) / total) * 100 : 0}%`,
                      background: CAT_PALETTE[i % CAT_PALETTE.length],
                    }}
                  />
                </div>
              </div>
              <div className="text-right shrink-0">
                <div className="text-sm text-content tabular-nums">
                  {formatEuro(b.depenses)}
                </div>
                <div className="text-[11px] text-content-3 tabular-nums">
                  {formatPercent(b.part_depenses_pct)} · épargne {formatEuro(b.epargne_nette)}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Commun vs perso : barre unique + tooltip */}
        <div className="flex flex-col gap-1.5 border-t border-border-app pt-3">
          <span className="text-[11px] text-content-3 inline-flex items-center gap-1">
            Dépenses communes vs personnelles
            <Tooltip {...DEFINITIONS.analyse_commun_perso} align="left" size={12} />
          </span>
          <div className="h-2 flex rounded-full overflow-hidden bg-surface-3">
            <div
              className="h-full"
              style={{
                width: `${totalCvp > 0 ? (communDep / totalCvp) * 100 : 0}%`,
                background: chartColors.purple,
              }}
            />
            <div
              className="h-full"
              style={{
                width: `${totalCvp > 0 ? (persoDep / totalCvp) * 100 : 0}%`,
                background: chartColors.teal,
              }}
            />
          </div>
          <div className="flex justify-between text-[11px] text-content-3 tabular-nums">
            <span>
              <span className="inline-block w-2 h-2 rounded-full mr-1 align-middle" style={{ background: chartColors.purple }} />
              Commun {formatEuro(communDep)}
            </span>
            <span>
              Perso {formatEuro(persoDep)}
              <span className="inline-block w-2 h-2 rounded-full ml-1 align-middle" style={{ background: chartColors.teal }} />
            </span>
          </div>
        </div>
      </div>
    </Card>
  )
}

/* -------------------------------------------------------------------------- */
/* Catégories dans le temps                                                   */
/* -------------------------------------------------------------------------- */
function CategoriesCard({ bloc, series }) {
  const labels = series.map((p) => moisLabel(p.mois))
  const cats = bloc.par_categorie
  const total = Number(bloc.total_periode) || 0

  // Barres empilées : top N catégories + « Autres » agrégées.
  const principales = cats.slice(0, TOP_CATEGORIES)
  const reste = cats.slice(TOP_CATEGORIES)
  const datasets = principales.map((cat, i) => ({
    label: cat.nom,
    data: cat.serie.map((s) => Number(s.total)),
    color: CAT_PALETTE[i % CAT_PALETTE.length],
  }))
  if (reste.length > 0) {
    datasets.push({
      label: 'Autres',
      data: labels.map((_, idx) =>
        reste.reduce((sum, cat) => sum + Number(cat.serie[idx].total), 0)
      ),
      color: chartColors.gray,
    })
  }

  return (
    <Card
      title={
        <span className="inline-flex items-center gap-1">
          Dépenses par catégorie dans le temps
          <Tooltip {...DEFINITIONS.analyse_categories} align="left" />
        </span>
      }
    >
      <div className="flex flex-col gap-4">
        <BarChart labels={labels} datasets={datasets} height={260} stacked />

        <div className="flex flex-col divide-y divide-border-app">
          {cats.map((cat, i) => (
            <div key={cat.id} className="flex items-center gap-3 py-2">
              <span
                className="w-2.5 h-2.5 rounded-full shrink-0"
                style={{ background: CAT_PALETTE[i % CAT_PALETTE.length] }}
              />
              <div className="flex-1 min-w-0">
                <div className="text-sm text-content truncate">{cat.nom}</div>
                <div className="h-1 mt-1 bg-surface-3 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${total > 0 ? (Number(cat.total_periode) / total) * 100 : 0}%`,
                      background: CAT_PALETTE[i % CAT_PALETTE.length],
                    }}
                  />
                </div>
              </div>
              <div className="text-right shrink-0">
                <div className="text-sm text-content tabular-nums">
                  {formatEuro(cat.total_periode)}
                </div>
                <div className="text-[11px] text-content-3 tabular-nums">
                  {formatPercent(cat.part_pct)} · {formatEuro(cat.moyenne_mensuelle)}/mois
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}

/* -------------------------------------------------------------------------- */
/* Rythme                                                                      */
/* -------------------------------------------------------------------------- */
function RythmeCard({ bloc }) {
  const labels = bloc.par_jour_semaine.map((j) => JOURS[j.jour - 1])
  const datasets = [
    {
      label: 'Dépenses',
      data: bloc.par_jour_semaine.map((j) => Number(j.total)),
      color: chartColors.purple,
    },
  ]
  const recurrents = bloc.libelles_recurrents

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
      <Card
        title={
          <span className="inline-flex items-center gap-1">
            Par jour de semaine
            <Tooltip {...DEFINITIONS.analyse_rythme_jour} align="left" />
          </span>
        }
      >
        <BarChart labels={labels} datasets={datasets} height={220} />
      </Card>

      <Card
        title={
          <span className="inline-flex items-center gap-1">
            Postes récurrents
            <Tooltip {...DEFINITIONS.analyse_recurrents} align="left" />
          </span>
        }
      >
        {recurrents.length === 0 ? (
          <p className="text-sm text-content-3 py-4 text-center">
            Aucun poste répété sur la période.
          </p>
        ) : (
          <div className="flex flex-col divide-y divide-border-app">
            {recurrents.map((r) => (
              <div key={r.libelle} className="flex items-center gap-3 py-2">
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-content truncate">{r.libelle}</div>
                  <div className="text-[11px] text-content-3">
                    {r.occurrences} fois · {formatEuro(r.moyenne)} en moyenne
                  </div>
                </div>
                <div className="text-sm text-content tabular-nums shrink-0">
                  {formatEuro(r.total)}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

/* -------------------------------------------------------------------------- */
function AnalyseSkeleton() {
  return (
    <div className="flex flex-col gap-4 animate-pulse" aria-hidden="true">
      {[0, 1].map((i) => (
        <div key={i} className="bg-surface border border-border-app rounded-xl p-5 flex flex-col gap-3">
          <div className="h-4 w-40 bg-surface-3 rounded" />
          <div className="grid grid-cols-3 gap-2.5">
            <div className="h-16 bg-surface-3 rounded" />
            <div className="h-16 bg-surface-3 rounded" />
            <div className="h-16 bg-surface-3 rounded" />
          </div>
          <div className="h-56 bg-surface-3 rounded" />
        </div>
      ))}
    </div>
  )
}

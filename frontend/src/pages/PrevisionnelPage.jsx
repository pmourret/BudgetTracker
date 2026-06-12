import { useState } from 'react'
import usePrevisionnel from '../hooks/usePrevisionnel'
import { formatEuro, formatMonth } from '../utils/format'
import Card from '../components/ui/Card'
import PeriodSelector from '../components/ui/PeriodSelector'
import FiabiliteBadge from '../components/previsionnel/FiabiliteBadge'
import { ErrorState, EmptyState } from '../components/ui/States'
import LineChart from '../components/charts/LineChart'
import { chartColors } from '../components/charts/chartSetup'

export default function PrevisionnelPage() {
  const [nbMois, setNbMois] = useState(6)
  const { data, isLoading, isError, refetch } = usePrevisionnel(nbMois)

  // Pas d'early return : le header reste visible quel que soit l'état
  // (cf. piège ComptesPage).
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-lg font-medium text-content">Prévisionnel</h1>
        <p className="text-sm text-content-2 mt-0.5">
          Projection consultative — le solde réel reste la seule référence.
        </p>
      </div>

      {isLoading && <PrevisionnelSkeleton />}

      {isError && (
        <ErrorState
          message="Impossible de charger le prévisionnel."
          onRetry={refetch}
        />
      )}

      {!isLoading && !isError && data && (
        estVide(data) ? (
          <EmptyState
            icon="🔮"
            message="Pas encore assez de données pour projeter. Ajoutez des comptes, des flux, des budgets ou des abonnements pour alimenter le prévisionnel."
          />
        ) : (
          <PrevisionnelContenu data={data} nbMois={nbMois} onNbMoisChange={setNbMois} />
        )
      )}
    </div>
  )
}

function estVide(data) {
  const s = data.solde_projete
  const c = data.capacite_restante
  return (
    Number(s.composantes.solde_actuel) === 0 &&
    Number(s.solde_projete) === 0 &&
    Number(c.composantes.total_budgets) === 0 &&
    data.trajectoire.points.every(
      (p) => Number(p.revenus_attendus) === 0 && Number(p.depenses_attendues) === 0
    )
  )
}

function PrevisionnelContenu({ data, nbMois, onNbMoisChange }) {
  return (
    <>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <SoldeProjeteCard bloc={data.solde_projete} moisCourant={data.mois_courant} />
        <CapaciteCard bloc={data.capacite_restante} />
      </div>
      <TrajectoireCard
        bloc={data.trajectoire}
        nbMois={nbMois}
        onNbMoisChange={onNbMoisChange}
      />
    </>
  )
}

function SoldeProjeteCard({ bloc, moisCourant }) {
  const c = bloc.composantes
  const briques = [
    { label: 'Solde actuel', value: Number(c.solde_actuel) },
    { label: 'Flux futurs datés du mois', value: Number(c.flux_futurs_mois) },
    { label: 'Abonnements à échoir (non budgétés)', value: Number(c.abonnements_a_echoir_non_budgetes) },
    { label: 'Reste à dépenser budgété', value: -Number(c.reste_a_depenser_budgete) || 0 },
  ]

  return (
    <Card
      title="Solde projeté fin de mois"
      action={<FiabiliteBadge fiabilite={bloc.fiabilite} />}
    >
      <div className="flex flex-col gap-3">
        <div>
          <div className="text-3xl font-medium text-content">
            {formatEuro(bloc.solde_projete)}
          </div>
          <div className="text-xs text-content-3 mt-0.5 capitalize">
            {formatMonth(moisCourant)}
          </div>
        </div>

        <div className="flex flex-col gap-1.5 border-t border-border-app pt-3">
          {briques.map(({ label, value }) => (
            <div key={label} className="flex justify-between items-baseline gap-2">
              <span className="text-xs text-content-2">{label}</span>
              <span
                className={[
                  'text-xs tabular-nums',
                  value < 0 ? 'text-red-600' : value > 0 ? 'text-teal-600' : 'text-content-3',
                ].join(' ')}
              >
                {value > 0 ? '+' : ''}{formatEuro(value)}
              </span>
            </div>
          ))}
        </div>

        <p className="text-[11px] text-content-3 leading-relaxed">{bloc.definition}</p>
      </div>
    </Card>
  )
}

function CapaciteCard({ bloc }) {
  const c = bloc.composantes
  const totalBudgets = Number(c.total_budgets)
  const engage = Number(c.total_consomme) + Number(c.abonnements_restants)
  const pctEngage = totalBudgets > 0 ? Math.min((engage / totalBudgets) * 100, 100) : 0
  const capacite = Number(bloc.capacite)

  return (
    <Card
      title="Capacité à dépenser restante"
      action={<FiabiliteBadge fiabilite={bloc.fiabilite} />}
    >
      <div className="flex flex-col gap-3">
        <div className={`text-3xl font-medium ${capacite < 0 ? 'text-red-600' : 'text-content'}`}>
          {formatEuro(capacite)}
        </div>

        {totalBudgets > 0 && (
          <div className="flex flex-col gap-1">
            <div className="h-1.5 bg-surface-3 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full bg-purple-600"
                style={{ width: `${pctEngage}%` }}
              />
            </div>
            <div className="text-[11px] text-content-3">
              {formatEuro(engage)} engagés sur {formatEuro(totalBudgets)} budgétés
            </div>
          </div>
        )}

        <div className="flex flex-col gap-1.5 border-t border-border-app pt-3">
          <DetailLigne label="Budgets du mois" value={formatEuro(c.total_budgets)} />
          <DetailLigne label="Déjà consommé" value={formatEuro(-Number(c.total_consomme) || 0)} />
          <DetailLigne
            label="Abonnements restants (hors budgets)"
            value={formatEuro(-Number(c.abonnements_restants) || 0)}
          />
        </div>

        <p className="text-[11px] text-content-3 leading-relaxed">{bloc.definition}</p>
      </div>
    </Card>
  )
}

function DetailLigne({ label, value }) {
  return (
    <div className="flex justify-between items-baseline gap-2">
      <span className="text-xs text-content-2">{label}</span>
      <span className="text-xs text-content tabular-nums">{value}</span>
    </div>
  )
}

function TrajectoireCard({ bloc, nbMois, onNbMoisChange }) {
  const points = bloc.points
  const labels = points.map((p) =>
    new Date(p.mois).toLocaleDateString('fr-FR', { month: 'short', year: '2-digit' })
  )
  const cumul = points.map((p) => Number(p.cumul))

  // Coupe le tracé là où l'API dégrade la fiabilité à 'faible' :
  // trait plein avant, pointillés gris au-delà (aucun seuil côté front).
  const premierFaible = points.findIndex((p) => p.fiabilite === 'faible')
  const datasets =
    premierFaible === -1
      ? [{ label: 'Épargne cumulée', data: cumul, color: chartColors.purple, fill: true }]
      : [
          {
            label: 'Épargne cumulée',
            data: cumul.map((v, i) => (i < premierFaible ? v : null)),
            color: chartColors.purple,
            fill: true,
          },
          {
            label: 'Indicatif (fiabilité faible)',
            data: cumul.map((v, i) => (i >= premierFaible - 1 ? v : null)),
            color: chartColors.gray,
            dashed: true,
          },
        ]

  return (
    <Card
      title="Trajectoire d'épargne projetée"
      action={
        <div className="flex items-center gap-2">
          <FiabiliteBadge fiabilite={bloc.fiabilite} />
          <PeriodSelector value={nbMois} onChange={onNbMoisChange} />
        </div>
      }
    >
      <div className="flex flex-col gap-3">
        <LineChart labels={labels} datasets={datasets} height={220} />
        {premierFaible !== -1 && (
          <p className="text-[11px] text-content-3">
            Les mois en pointillés sont indicatifs (fiabilité faible renvoyée par l'API).
          </p>
        )}
        <p className="text-[11px] text-content-3 leading-relaxed">{bloc.definition}</p>
      </div>
    </Card>
  )
}

function PrevisionnelSkeleton() {
  return (
    <div className="flex flex-col gap-4 animate-pulse" aria-hidden="true">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <SkeletonCard />
        <SkeletonCard />
      </div>
      <div className="bg-surface border border-border-app rounded-xl p-5 flex flex-col gap-3">
        <div className="h-4 w-48 bg-surface-3 rounded" />
        <div className="h-52 bg-surface-3 rounded" />
      </div>
    </div>
  )
}

function SkeletonCard() {
  return (
    <div className="bg-surface border border-border-app rounded-xl p-5 flex flex-col gap-3">
      <div className="h-4 w-40 bg-surface-3 rounded" />
      <div className="h-8 w-32 bg-surface-3 rounded" />
      <div className="h-3 w-full bg-surface-3 rounded" />
      <div className="h-3 w-2/3 bg-surface-3 rounded" />
    </div>
  )
}

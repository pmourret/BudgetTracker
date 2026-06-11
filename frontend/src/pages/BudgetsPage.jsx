import { useState } from 'react'
import { useResourceList, useDeleteResource } from '../hooks/useResource'
import { formatEuro, formatMonth } from '../utils/format'
import { Pencil, Trash2 } from 'lucide-react'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import { Loading, ErrorState, EmptyState } from '../components/ui/States'
import BudgetFormModal from '../components/budgets/BudgetFormModal'

function moisActuelDate() {
  const d = new Date()
  return new Date(d.getFullYear(), d.getMonth(), 1)
}

function toISO(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-01`
}

function statutFromTaux(taux) {
  const t = Number(taux)
  if (t >= 100) return { label: 'Dépassé', variant: 'critique', bar: 'bg-red-600', pct: 'text-red-600' }
  if (t >= 80)  return { label: 'Alerte',  variant: 'avertissement', bar: 'bg-amber-600', pct: 'text-amber-600' }
  if (t >= 50)  return { label: 'En cours', variant: 'purple', bar: 'bg-purple-600', pct: 'text-purple-400' }
  return { label: 'OK', variant: 'success', bar: 'bg-teal-600', pct: 'text-teal-600' }
}

export default function BudgetsPage() {
  const [moisCourant, setMoisCourant] = useState(moisActuelDate())
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedBudget, setSelectedBudget] = useState(null)

  const moisISO = toISO(moisCourant)
  const { data, isLoading, isError, refetch } = useResourceList('budgets', { mois: moisISO })

  const budgets = data?.results ?? []
  const totalPrevu = budgets.reduce((s, b) => s + Number(b.montant_prevu || 0), 0)
  const totalConsomme = budgets.reduce((s, b) => s + Number(b.montant_consomme || 0), 0)
  const reste = totalPrevu - totalConsomme

  const changeMois = (delta) => {
    setMoisCourant((prev) => new Date(prev.getFullYear(), prev.getMonth() + delta, 1))
  }

  const openCreate = () => { setSelectedBudget(null); setModalOpen(true) }
  const openEdit = (budget) => { setSelectedBudget(budget); setModalOpen(true) }
  const closeModal = () => { setModalOpen(false); setSelectedBudget(null) }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-lg font-medium text-content">Budgets</h1>
          <p className="text-sm text-content-2 mt-0.5">
            {budgets.length} budget{budgets.length > 1 ? 's' : ''} défini{budgets.length > 1 ? 's' : ''}
          </p>
        </div>
        <Button variant="primary" onClick={openCreate}>
          + Nouveau budget
        </Button>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={() => changeMois(-1)}
          className="w-8 h-8 rounded-lg border border-border-app bg-surface text-content-2 cursor-pointer hover:bg-surface-3 flex items-center justify-center"
          aria-label="Mois précédent"
        >
          ‹
        </button>
        <span className="text-sm font-medium text-content min-w-[130px] text-center capitalize">
          {formatMonth(moisISO)}
        </span>
        <button
          onClick={() => changeMois(1)}
          className="w-8 h-8 rounded-lg border border-border-app bg-surface text-content-2 cursor-pointer hover:bg-surface-3 flex items-center justify-center"
          aria-label="Mois suivant"
        >
          ›
        </button>
      </div>

      {isLoading && <Loading message="Chargement des budgets..." />}
      {isError && <ErrorState message="Impossible de charger les budgets." onRetry={refetch} />}

      {!isLoading && !isError && (
        <>
          {budgets.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              <MetricCard label="Total prévu" value={formatEuro(totalPrevu)} />
              <MetricCard
                label="Total consommé"
                value={formatEuro(totalConsomme)}
                valueClass={totalConsomme > totalPrevu ? 'text-red-600' : 'text-content'}
              />
              <MetricCard
                label="Reste disponible"
                value={formatEuro(reste)}
                valueClass={reste < 0 ? 'text-red-600' : 'text-teal-600'}
              />
            </div>
          )}

          {budgets.length === 0 ? (
            <EmptyState
              icon="🎯"
              message={`Aucun budget défini pour ${formatMonth(moisISO)}.`}
              action={
                <Button variant="primary" onClick={openCreate}>
                  Définir un budget
                </Button>
              }
            />
          ) : (
            <div className="flex flex-col gap-3">
              {budgets.map((budget) => (
                <BudgetCard
                  key={budget.id}
                  budget={budget}
                  onEdit={() => openEdit(budget)}
                />
              ))}
            </div>
          )}
        </>
      )}

      <BudgetFormModal
        isOpen={modalOpen}
        onClose={closeModal}
        moisDefaut={moisISO}
        budget={selectedBudget}
      />
    </div>
  )
}

function MetricCard({ label, value, valueClass = 'text-content' }) {
  return (
    <div className="bg-surface-3 rounded-lg px-4 py-3.5">
      <div className="text-xs text-content-2 mb-1">{label}</div>
      <div className={`text-xl font-medium ${valueClass}`}>{value}</div>
    </div>
  )
}

function BudgetCard({ budget, onEdit }) {
  const statut = statutFromTaux(budget.taux_consommation)
  const largeur = Math.min(Number(budget.taux_consommation), 100)
  const deleteBudget = useDeleteResource('budgets')

  const handleDelete = () => {
    if (!window.confirm(`Supprimer le budget « ${budget.categorie_nom} » pour ${formatMonth(budget.mois)} ?`)) return
    deleteBudget.mutate(budget.id)
  }

  return (
    <Card>
      <div className="flex justify-between items-center mb-2.5">
        <span className="text-sm font-medium text-content">{budget.categorie_nom}</span>
        <div className="flex items-center gap-2">
          <Badge variant={statut.variant}>{statut.label}</Badge>
          <button
            onClick={onEdit}
            title="Modifier"
            className="p-1.5 rounded-md text-content-2 hover:text-content hover:bg-surface-3 cursor-pointer"
          >
            <Pencil size={13} />
          </button>
          <button
            onClick={handleDelete}
            title="Supprimer"
            disabled={deleteBudget.isPending}
            className="p-1.5 rounded-md text-content-2 hover:text-red-600 hover:bg-red-50 cursor-pointer disabled:opacity-50"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>

      <div className="h-2 bg-surface-3 rounded-full overflow-hidden mb-2">
        <div className={`h-full rounded-full ${statut.bar}`} style={{ width: `${largeur}%` }} />
      </div>

      <div className="flex justify-between items-center text-xs text-content-2">
        <span>
          Consommé : <strong className="text-content font-medium">{formatEuro(budget.montant_consomme)}</strong>
        </span>
        <span>
          Prévu : <strong className="text-content font-medium">{formatEuro(budget.montant_prevu)}</strong>
        </span>
        <span className={`font-medium ${statut.pct}`}>
          {Number(budget.taux_consommation).toFixed(0)} %
        </span>
      </div>
    </Card>
  )
}

import { useState } from 'react'
import { useResourceList, useDeleteResource, useResourceAction } from '../hooks/useResource'
import { formatEuro, formatMonth } from '../utils/format'
import { Pencil, Trash2, RefreshCw } from 'lucide-react'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Tooltip from '../components/ui/Tooltip'
import { DEFINITIONS } from '../constants/definitions'
import { Loading, ErrorState, EmptyState } from '../components/ui/States'
import BudgetFormModal from '../components/budgets/BudgetFormModal'
import BudgetTemplateFormModal from '../components/budgets/BudgetTemplateFormModal'

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
  const [tab, setTab] = useState('mois')
  const [moisCourant, setMoisCourant] = useState(moisActuelDate())
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedBudget, setSelectedBudget] = useState(null)
  const [templateModalOpen, setTemplateModalOpen] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState(null)
  const [reconduireMsg, setReconduireMsg] = useState(null)

  const moisISO = toISO(moisCourant)
  const { data, isLoading, isError, refetch } = useResourceList('budgets', { mois: moisISO })
  const budgets = data?.results ?? []
  const totalPrevu = budgets.reduce((s, b) => s + Number(b.montant_prevu || 0), 0)
  const totalConsomme = budgets.reduce((s, b) => s + Number(b.montant_consomme || 0), 0)
  const reste = totalPrevu - totalConsomme

  const {
    data: templatesData,
    isLoading: templatesLoading,
    isError: templatesError,
    refetch: refetchTemplates,
  } = useResourceList('budget-templates')
  const templates = templatesData?.results ?? []

  const reconduireAction = useResourceAction('budget-templates')

  const changeMois = (delta) => {
    setMoisCourant((prev) => new Date(prev.getFullYear(), prev.getMonth() + delta, 1))
  }

  const openCreate = () => { setSelectedBudget(null); setModalOpen(true) }
  const openEdit = (budget) => { setSelectedBudget(budget); setModalOpen(true) }
  const closeModal = () => { setModalOpen(false); setSelectedBudget(null) }

  const openTemplateCreate = () => { setSelectedTemplate(null); setTemplateModalOpen(true) }
  const openTemplateEdit = (tmpl) => { setSelectedTemplate(tmpl); setTemplateModalOpen(true) }
  const closeTemplateModal = () => { setTemplateModalOpen(false); setSelectedTemplate(null) }

  const handleReconduire = () => {
    setReconduireMsg(null)
    reconduireAction.mutate(
      { id: null, action: 'reconduire', payload: { mois: moisISO } },
      {
        onSuccess: (data) => {
          setReconduireMsg(
            data.crees > 0
              ? `${data.crees} budget${data.crees > 1 ? 's' : ''} créé${data.crees > 1 ? 's' : ''} pour ${formatMonth(moisISO)}.`
              : `Tous les modèles sont déjà couverts pour ${formatMonth(moisISO)}.`
          )
          if (tab !== 'mois') setTab('mois')
        },
        onError: () => {
          setReconduireMsg('Erreur lors de la reconduction.')
        },
      }
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-lg font-medium text-content">Budgets</h1>
          <p className="text-sm text-content-2 mt-0.5">
            {tab === 'mois'
              ? `${budgets.length} budget${budgets.length > 1 ? 's' : ''} défini${budgets.length > 1 ? 's' : ''}`
              : `${templates.length} modèle${templates.length > 1 ? 's' : ''} récurrent${templates.length > 1 ? 's' : ''}`}
          </p>
        </div>
        {tab === 'mois' ? (
          <Button variant="primary" onClick={openCreate}>+ Nouveau budget</Button>
        ) : (
          <Button variant="primary" onClick={openTemplateCreate}>+ Nouveau modèle</Button>
        )}
      </div>

      {/* Onglets */}
      <div className="flex gap-1 rounded-lg border border-border-app bg-surface-2 p-1 w-fit">
        <TabBtn active={tab === 'mois'} onClick={() => setTab('mois')}>Ce mois</TabBtn>
        <TabBtn active={tab === 'modeles'} onClick={() => setTab('modeles')}>Modèles</TabBtn>
      </div>

      {/* ---- Onglet Ce mois ---- */}
      {tab === 'mois' && (
        <>
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
                  <MetricCard label="Total prévu" value={formatEuro(totalPrevu)} def={DEFINITIONS.budget_total_prevu} />
                  <MetricCard
                    label="Total consommé"
                    value={formatEuro(totalConsomme)}
                    valueClass={totalConsomme > totalPrevu ? 'text-red-600' : 'text-content'}
                    def={DEFINITIONS.budget_total_consomme}
                  />
                  <MetricCard
                    label="Reste disponible"
                    value={formatEuro(reste)}
                    valueClass={reste < 0 ? 'text-red-600' : 'text-teal-600'}
                    def={DEFINITIONS.budget_reste}
                    defAlign="right"
                  />
                </div>
              )}

              {budgets.length === 0 ? (
                <EmptyState
                  icon="🎯"
                  message={`Aucun budget défini pour ${formatMonth(moisISO)}.`}
                  action={
                    <div className="flex flex-col items-center gap-2">
                      <Button variant="primary" onClick={openCreate}>Définir un budget</Button>
                      {templates.length > 0 && (
                        <Button
                          variant="secondary"
                          onClick={handleReconduire}
                          disabled={reconduireAction.isPending}
                        >
                          <RefreshCw size={14} className="mr-1.5" />
                          {reconduireAction.isPending ? 'Reconduction...' : 'Reconduire les modèles'}
                        </Button>
                      )}
                    </div>
                  }
                />
              ) : (
                <div className="flex flex-col gap-3">
                  {budgets.map((budget) => (
                    <BudgetCard key={budget.id} budget={budget} onEdit={() => openEdit(budget)} />
                  ))}
                </div>
              )}
            </>
          )}
        </>
      )}

      {/* ---- Onglet Modèles ---- */}
      {tab === 'modeles' && (
        <>
          <div className="flex items-center justify-between">
            <p className="text-sm text-content-2">
              Les modèles actifs sont reconduits chaque mois en un clic.
            </p>
            <Button
              variant="secondary"
              onClick={handleReconduire}
              disabled={reconduireAction.isPending}
            >
              <RefreshCw size={14} className="mr-1.5" />
              {reconduireAction.isPending ? 'Reconduction...' : `Reconduire sur ${formatMonth(moisISO)}`}
            </Button>
          </div>

          {reconduireMsg && (
            <div className="px-4 py-2.5 rounded-lg bg-teal-50 dark:bg-teal-950 border border-teal-200 dark:border-teal-800 text-sm text-teal-800 dark:text-teal-200">
              {reconduireMsg}
            </div>
          )}

          {templatesLoading && <Loading message="Chargement des modèles..." />}
          {templatesError && <ErrorState message="Impossible de charger les modèles." onRetry={refetchTemplates} />}

          {!templatesLoading && !templatesError && (
            templates.length === 0 ? (
              <EmptyState
                icon="📋"
                message="Aucun modèle défini."
                action={
                  <Button variant="primary" onClick={openTemplateCreate}>
                    Créer un modèle
                  </Button>
                }
              />
            ) : (
              <div className="flex flex-col gap-3">
                {templates.map((tmpl) => (
                  <TemplateCard
                    key={tmpl.id}
                    template={tmpl}
                    onEdit={() => openTemplateEdit(tmpl)}
                  />
                ))}
              </div>
            )
          )}
        </>
      )}

      <BudgetFormModal
        isOpen={modalOpen}
        onClose={closeModal}
        moisDefaut={moisISO}
        budget={selectedBudget}
      />
      <BudgetTemplateFormModal
        isOpen={templateModalOpen}
        onClose={closeTemplateModal}
        template={selectedTemplate}
      />
    </div>
  )
}

function TabBtn({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors cursor-pointer ${
        active
          ? 'bg-surface text-content shadow-sm'
          : 'text-content-2 hover:text-content'
      }`}
    >
      {children}
    </button>
  )
}

function MetricCard({ label, value, valueClass = 'text-content', def, defAlign = 'left' }) {
  return (
    <div className="bg-surface-3 rounded-lg px-4 py-3.5">
      <div className="text-xs text-content-2 mb-1 flex items-center gap-1">
        {label}
        {def && <Tooltip {...def} align={defAlign} />}
      </div>
      <div className={`text-xl font-medium ${valueClass}`}>{value}</div>
    </div>
  )
}

function MineuresIncluses({ detail }) {
  const MAX = 3
  const visible = detail.slice(0, MAX)
  const reste = detail.length - MAX
  return (
    <p className="text-xs text-content-3 mb-2">
      Inclut&nbsp;:{' '}
      {visible.map((c) => c.nom).join(', ')}
      {reste > 0 && ` +${reste}`}
    </p>
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
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-content">{budget.categorie_nom}</span>
          {budget.template_id && (
            <span title="Créé depuis un modèle" className="text-content-3">
              <RefreshCw size={11} />
            </span>
          )}
        </div>
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

      {budget.est_budget_majeur && budget.categories_incluses_detail?.length > 0 && (
        <MineuresIncluses detail={budget.categories_incluses_detail} />
      )}

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
        <span className={`font-medium flex items-center gap-1 ${statut.pct}`}>
          {Number(budget.taux_consommation).toFixed(0)} %
          <Tooltip {...DEFINITIONS.budget_taux} align="right" size={12} />
        </span>
      </div>
    </Card>
  )
}

function TemplateCard({ template, onEdit }) {
  const deleteTemplate = useDeleteResource('budget-templates')

  const handleDelete = () => {
    if (!window.confirm(`Supprimer le modèle « ${template.categorie_nom} » ?`)) return
    deleteTemplate.mutate(template.id)
  }

  return (
    <Card>
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-2.5 flex-1 min-w-0">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-content truncate">
                {template.categorie_nom}
              </span>
              {!template.actif && (
                <Badge variant="neutre">Inactif</Badge>
              )}
              {template.est_budget_majeur && (
                <span className="inline-flex items-center gap-1">
                  <Badge variant="purple">Global</Badge>
                  <Tooltip {...DEFINITIONS.budget_majeur} align="left" size={12} />
                </span>
              )}
            </div>
            {template.est_budget_majeur && template.categories_incluses_detail?.length > 0 && (
              <MineuresIncluses detail={template.categories_incluses_detail} />
            )}
            {template.nb_budgets_mensuels > 0 && (
              <p className="text-xs text-content-3 mt-0.5">
                {template.nb_budgets_mensuels} budget{template.nb_budgets_mensuels > 1 ? 's' : ''} généré{template.nb_budgets_mensuels > 1 ? 's' : ''}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <span className="text-sm font-medium text-content">
            {formatEuro(template.montant_defaut)}
          </span>
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
            disabled={deleteTemplate.isPending}
            className="p-1.5 rounded-md text-content-2 hover:text-red-600 hover:bg-red-50 cursor-pointer disabled:opacity-50"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>
    </Card>
  )
}

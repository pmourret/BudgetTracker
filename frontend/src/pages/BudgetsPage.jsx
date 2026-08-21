import { useState } from 'react'
import { useResourceList, useDeleteResource, useResourceAction } from '../hooks/useResource'
import { useParametres } from '../hooks/useParametres'
import usePoints from '../hooks/usePoints'
import { formatEuro, formatMonth } from '../utils/format'
import { Pencil, Trash2, RefreshCw, Coins, Target, ClipboardList } from 'lucide-react'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Tooltip from '../components/ui/Tooltip'
import { DEFINITIONS } from '../constants/definitions'
import { Loading, ErrorState, EmptyState } from '../components/ui/States'
import MonthNav from '../components/ui/MonthNav'
import BudgetFormModal from '../components/budgets/BudgetFormModal'
import BudgetTemplateFormModal from '../components/budgets/BudgetTemplateFormModal'
import AllocationModal from '../components/budgets/AllocationModal'
import Metric, { MetricRow } from '../components/ui/Metric'

// Points d'une enveloppe (miroir client de budgets/services/points.py) :
// signe(prévu_effectif − consommé) × ⌈ |écart| / valeur_point ⌉.
function computePoints(budget, vp) {
  const prevuEff = Number(budget.montant_prevu) + Number(budget.points_alloues || 0) * vp
  const ecart = prevuEff - Number(budget.montant_consomme)
  if (ecart === 0 || !vp) return 0
  const mag = Math.ceil(Math.abs(ecart) / vp)
  return ecart > 0 ? mag : -mag
}

function PointsChip({ points }) {
  if (points === 0) {
    return <Badge variant="neutre">0 pt</Badge>
  }
  const positif = points > 0
  return (
    <span
      className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${
        positif ? 'bg-teal-50 text-teal-700' : 'bg-red-50 text-red-700'
      }`}
    >
      {positif ? '+' : ''}{points} pt{Math.abs(points) > 1 ? 's' : ''}
    </span>
  )
}

function PointsReservePanel({ nbMois = 6 }) {
  const { data } = usePoints(nbMois)
  if (!data) return null
  const actif =
    (data.enveloppes_courantes?.length ?? 0) > 0 ||
    data.solde_disponible !== 0 ||
    data.delta_courant_provisoire !== 0
  if (!actif) return null

  const solde = data.solde_disponible
  const soldePositif = solde >= 0
  const delta = data.delta_courant_provisoire

  return (
    <Card
      title={
        <span className="inline-flex items-center gap-1.5">
          <Coins size={16} className="text-content-2" />
          Réserve de points
          <Tooltip {...DEFINITIONS.points_reserve} align="left" />
        </span>
      }
    >
      <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
        <div>
          <div className="text-xs text-content-3 mb-0.5">Disponible (mois clôturés)</div>
          <div className={`text-2xl font-semibold ${soldePositif ? 'text-teal-texte' : 'text-red-texte'}`}>
            {soldePositif ? '+' : ''}{solde} pt{Math.abs(solde) > 1 ? 's' : ''}
          </div>
          <div className="text-xs text-content-3 mt-0.5">
            ≈ {formatEuro(data.solde_disponible_euros)}
          </div>
        </div>
        <div>
          <div className="text-xs text-content-3 mb-0.5 inline-flex items-center gap-1">
            Mois en cours <Badge variant="info">projeté</Badge>
          </div>
          <div className={`text-2xl font-semibold ${delta >= 0 ? 'text-teal-texte' : 'text-red-texte'}`}>
            {delta >= 0 ? '+' : ''}{delta} pt{Math.abs(delta) > 1 ? 's' : ''}
          </div>
          <div className="text-xs text-content-3 mt-0.5">non figé avant la clôture</div>
        </div>
      </div>

      {data.enveloppes_courantes?.length > 0 && (
        <div className="mt-3 flex flex-col gap-1.5 border-t border-border-app pt-3">
          {data.enveloppes_courantes.map((e) => (
            <div key={e.id} className="flex items-center justify-between text-sm">
              <span className="text-content-2 truncate">{e.libelle}</span>
              <PointsChip points={e.points} />
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

function moisActuelDate() {
  const d = new Date()
  return new Date(d.getFullYear(), d.getMonth(), 1)
}

function toISO(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-01`
}

function statutFromTaux(taux) {
  const t = Number(taux)
  if (t >= 100) return { label: 'Dépassé', variant: 'critique', bar: 'bg-red-600', pct: 'text-red-texte' }
  if (t >= 80)  return { label: 'Alerte',  variant: 'avertissement', bar: 'bg-amber-600', pct: 'text-amber-texte' }
  if (t >= 50)  return { label: 'En cours', variant: 'purple', bar: 'bg-purple-600', pct: 'text-purple-texte' }
  return { label: 'OK', variant: 'success', bar: 'bg-teal-600', pct: 'text-teal-texte' }
}

export default function BudgetsPage() {
  const [tab, setTab] = useState('mois')
  const [moisCourant, setMoisCourant] = useState(moisActuelDate())
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedBudget, setSelectedBudget] = useState(null)
  const [templateModalOpen, setTemplateModalOpen] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState(null)
  const [reconduireMsg, setReconduireMsg] = useState(null)
  const [allocOpen, setAllocOpen] = useState(false)
  const [allocBudget, setAllocBudget] = useState(null)

  const moisISO = toISO(moisCourant)
  const { data, isLoading, isError, refetch } = useResourceList('budgets', { mois: moisISO })
  const { data: paramsData } = useParametres()
  const { data: pointsData } = usePoints()
  const valeurPoint = Number(paramsData?.valeur_point ?? 10)
  const soldeDisponible = Number(pointsData?.solde_disponible ?? 0)
  const moisCourantPoints = pointsData?.mois_courant // libellé du mois comptable courant
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

  const openAllocate = (budget) => { setAllocBudget(budget); setAllocOpen(true) }
  const closeAllocate = () => { setAllocOpen(false); setAllocBudget(null) }

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
          <MonthNav mois={moisISO} onChange={changeMois} />

          <PointsReservePanel />

          {isLoading && <Loading message="Chargement des budgets..." />}
          {isError && <ErrorState message="Impossible de charger les budgets." onRetry={refetch} />}

          {!isLoading && !isError && (
            <>
              {budgets.length > 0 && (
                <MetricRow colonnes={3}>
                  <Metric label="Total prévu" value={formatEuro(totalPrevu)} def={DEFINITIONS.budget_total_prevu} />
                  <Metric
                    label="Total consommé"
                    value={formatEuro(totalConsomme)}
                    valueClass={totalConsomme > totalPrevu ? 'text-red-texte' : 'text-content'}
                    def={DEFINITIONS.budget_total_consomme}
                  />
                  <Metric
                    label="Reste disponible"
                    value={formatEuro(reste)}
                    valueClass={reste < 0 ? 'text-red-texte' : 'text-teal-texte'}
                    def={DEFINITIONS.budget_reste}
                    defAlign="right"
                  />
                </MetricRow>
              )}

              {budgets.length === 0 ? (
                <EmptyState
                  Icon={Target}
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
                    <BudgetCard
                      key={budget.id}
                      budget={budget}
                      valeurPoint={valeurPoint}
                      onEdit={() => openEdit(budget)}
                      onAllocate={
                        budget.en_jeu && budget.mois === moisCourantPoints
                          ? () => openAllocate(budget)
                          : null
                      }
                    />
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
                Icon={ClipboardList}
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
      <AllocationModal
        isOpen={allocOpen}
        onClose={closeAllocate}
        budget={allocBudget}
        soldeDisponible={soldeDisponible}
        valeurPoint={valeurPoint}
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

function BudgetCard({ budget, onEdit, onAllocate = null, valeurPoint = 10 }) {
  const statut = statutFromTaux(budget.taux_consommation)
  const largeur = Math.min(Number(budget.taux_consommation), 100)
  const deleteBudget = useDeleteResource('budgets')

  const libelle = budget.libelle ?? budget.categorie_nom
  const estThematique = !budget.categorie
  const points = budget.en_jeu ? computePoints(budget, valeurPoint) : null
  const pointsAlloues = Number(budget.points_alloues ?? 0)
  const prevuEffectif = Number(
    budget.montant_prevu_effectif ?? budget.montant_prevu
  )

  const handleDelete = () => {
    if (!window.confirm(`Supprimer le budget « ${libelle} » pour ${formatMonth(budget.mois)} ?`)) return
    deleteBudget.mutate(budget.id)
  }

  return (
    <Card>
      <div className="flex justify-between items-center mb-2.5">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-content">{libelle}</span>
          {estThematique && <Badge variant="info">Thématique</Badge>}
          {budget.en_jeu && (
            <span className="inline-flex items-center gap-1">
              <PointsChip points={points} />
              <Tooltip {...DEFINITIONS.points_enveloppe} align="left" size={12} />
            </span>
          )}
          {budget.template_id && (
            <span title="Créé depuis un modèle" className="text-content-3">
              <RefreshCw size={11} />
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={statut.variant}>{statut.label}</Badge>
          {onAllocate && (
            <button
              onClick={onAllocate}
              title="Distribuer des points"
              className="p-1.5 rounded-md text-content-2 hover:text-teal-texte hover:bg-teal-50 cursor-pointer"
            >
              <Coins size={13} />
            </button>
          )}
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
            className="p-1.5 rounded-md text-content-2 hover:text-red-texte hover:bg-red-50 cursor-pointer disabled:opacity-50"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>

      {budget.categories_incluses_detail?.length > 0 && (
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
          Prévu : <strong className="text-content font-medium">{formatEuro(prevuEffectif)}</strong>
          {pointsAlloues > 0 && (
            <span className="text-teal-texte"> (dont +{pointsAlloues} pt{pointsAlloues > 1 ? 's' : ''})</span>
          )}
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

  const libelle = template.libelle ?? template.categorie_nom
  const estThematique = !template.categorie

  const handleDelete = () => {
    if (!window.confirm(`Supprimer le modèle « ${libelle} » ?`)) return
    deleteTemplate.mutate(template.id)
  }

  return (
    <Card>
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-2.5 flex-1 min-w-0">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-content truncate">
                {libelle}
              </span>
              {!template.actif && (
                <Badge variant="neutre">Inactif</Badge>
              )}
              {estThematique && <Badge variant="info">Thématique</Badge>}
              {template.en_jeu && (
                <span className="inline-flex items-center gap-1 text-teal-700">
                  <Coins size={13} />
                </span>
              )}
              {template.est_budget_majeur && (
                <span className="inline-flex items-center gap-1">
                  <Badge variant="purple">Global</Badge>
                  <Tooltip {...DEFINITIONS.budget_majeur} align="left" size={12} />
                </span>
              )}
            </div>
            {template.categories_incluses_detail?.length > 0 && (
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
            className="p-1.5 rounded-md text-content-2 hover:text-red-texte hover:bg-red-50 cursor-pointer disabled:opacity-50"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>
    </Card>
  )
}

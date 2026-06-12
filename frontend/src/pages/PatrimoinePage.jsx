import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import apiClient from '../api/client'
import { useResourceList, useResourceAction, useDeleteResource } from '../hooks/useResource'
import { formatEuro, formatDate } from '../utils/format'
import { Landmark, Pencil, Trash2 } from 'lucide-react'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Tooltip from '../components/ui/Tooltip'
import { DEFINITIONS } from '../constants/definitions'
import Modal from '../components/ui/Modal'
import Input from '../components/ui/Input'
import { Loading, ErrorState, EmptyState } from '../components/ui/States'
import LineChart from '../components/charts/LineChart'
import DoughnutChart from '../components/charts/DoughnutChart'
import { chartColors } from '../components/charts/chartSetup'
import ActifFormModal from '../components/patrimoine/ActifFormModal'
import IconBadge from '../components/ui/IconBadge'

function usePatrimoineTotal() {
  return useQuery({
    queryKey: ['patrimoine', 'total'],
    queryFn: async () => {
      const { data } = await apiClient.get('/patrimoine/total/')
      return data
    },
  })
}

function usePatrimoineHistorique() {
  return useQuery({
    queryKey: ['patrimoine', 'historique'],
    queryFn: async () => {
      const { data } = await apiClient.get('/patrimoine/historique/', {
        params: { nb_mois: 12 },
      })
      return data
    },
  })
}

export default function PatrimoinePage() {
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedActif, setSelectedActif] = useState(null)
  const [valoriserFor, setValoriserFor] = useState(null)

  const { data: actifsData, isLoading, isError, refetch } = useResourceList('patrimoine')
  const { data: total } = usePatrimoineTotal()
  const { data: historique } = usePatrimoineHistorique()
  const verifierRappels = useResourceAction('patrimoine')

  const actifs = actifsData?.results ?? []

  useEffect(() => {
    verifierRappels.mutate({ action: 'verifier-rappels' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const openCreate = () => { setSelectedActif(null); setModalOpen(true) }
  const openEdit = (actif) => { setSelectedActif(actif); setModalOpen(true) }
  const closeModal = () => { setModalOpen(false); setSelectedActif(null) }

  const parType = total?.par_type ?? {}
  const donutEntries = Object.values(parType).filter((t) => Number(t.total_estime) > 0)
  const donutLabels = donutEntries.map((t) => t.libelle)
  const donutValues = donutEntries.map((t) => Number(t.total_estime))

  const histoSerie = historique?.serie ?? []
  const courbeLabels = histoSerie.map((p) => {
    const d = new Date(p.mois)
    return d.toLocaleDateString('fr-FR', { month: 'short', year: '2-digit' })
  })
  const courbeValues = histoSerie.map((p) => Number(p.valeur_estimee))

  if (isLoading) return <Loading message="Chargement du patrimoine..." />
  if (isError) {
    return <ErrorState message="Impossible de charger le patrimoine." onRetry={refetch} />
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-lg font-medium text-content">Patrimoine</h1>
          <p className="text-sm text-content-2 mt-0.5">
            {actifs.length} actif{actifs.length > 1 ? 's' : ''}
          </p>
        </div>
        <Button variant="primary" onClick={openCreate}>
          + Nouvel actif
        </Button>
      </div>

      <div className="rounded-lg bg-amber-50 text-amber-800 text-xs px-4 py-2.5 leading-relaxed">
        ⚠ Toutes les valeurs affichées ici sont <strong>estimatives</strong> et basées sur
        vos saisies manuelles. Elles ne constituent pas une vérité comptable et n'affectent
        jamais vos soldes bancaires réels.
      </div>

      {actifs.length === 0 ? (
        <EmptyState
          icon="🏦"
          message="Aucun actif patrimonial enregistré."
          action={
            <Button variant="primary" onClick={openCreate}>
              Ajouter un actif
            </Button>
          }
        />
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
            <MetricCard
              label="Patrimoine total estimé"
              value={formatEuro(total?.total_estime ?? 0)}
              def={DEFINITIONS.patrimoine_total}
            />
            <MetricCard
              label="Plus-value latente estimée"
              value={
                total?.plus_value_latente_globale_estimee != null
                  ? formatEuro(total.plus_value_latente_globale_estimee)
                  : '—'
              }
              valueClass={
                Number(total?.plus_value_latente_globale_estimee) >= 0
                  ? 'text-teal-600'
                  : 'text-red-600'
              }
              def={DEFINITIONS.plus_value_latente}
            />
            <MetricCard label="Nombre d'actifs" value={String(actifs.length)} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {donutValues.length > 0 && (
              <Card title="Répartition par type">
                <DoughnutChart labels={donutLabels} values={donutValues} />
              </Card>
            )}
            {courbeValues.some((v) => v > 0) && (
              <Card title="Évolution estimée (12 mois)">
                <LineChart
                  labels={courbeLabels}
                  datasets={[
                    { label: 'Valeur estimée', data: courbeValues, color: chartColors.purple, fill: true },
                  ]}
                  height={220}
                />
              </Card>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {actifs.map((actif) => (
              <ActifCard
                key={actif.id}
                actif={actif}
                onEdit={() => openEdit(actif)}
                onValoriser={() => setValoriserFor(actif)}
              />
            ))}
          </div>
        </>
      )}

      <ActifFormModal isOpen={modalOpen} onClose={closeModal} actif={selectedActif} />
      <ValoriserModal actif={valoriserFor} onClose={() => setValoriserFor(null)} />
    </div>
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

function ActifCard({ actif, onEdit, onValoriser }) {
  const pv = actif.plus_value_latente
  const enMoinsValue = pv != null && Number(pv) < 0
  const tauxPv =
    pv != null && Number(actif.valeur_acquisition) > 0
      ? (Number(pv) / Number(actif.valeur_acquisition)) * 100
      : null

  const deleteActif = useDeleteResource('patrimoine')

  const handleDelete = () => {
    if (!window.confirm(`Supprimer l'actif « ${actif.nom} » ? Cette action est irréversible.`)) return
    deleteActif.mutate(actif.id)
  }

  return (
    <Card className={
      actif.valorisation_a_faire
        ? 'border-amber-600'
        : enMoinsValue
        ? 'border-red-600/40'
        : ''
    }>
      <div className="flex items-start gap-2.5 mb-3">
        <IconBadge Icon={Landmark} size={16} className="w-9 h-9 shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-content truncate">{actif.nom}</div>
          <div className="text-xs text-content-2">{actif.type_actif_display}</div>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          {actif.valorisation_a_faire && <Badge variant="avertissement">À valoriser</Badge>}
          {enMoinsValue && <Badge variant="critique">Moins-value</Badge>}
        </div>
      </div>

      <div className="text-xl font-medium text-content">
        {formatEuro(actif.valeur_actuelle)}
      </div>
      <div className="text-xs text-content-2">
        Valeur estimée
        {actif.date_valorisation && ` · au ${formatDate(actif.date_valorisation)}`}
      </div>

      {pv != null && (
        <div className={`text-xs mt-1 flex items-center gap-1 ${Number(pv) >= 0 ? 'text-teal-600' : 'text-red-600'}`}>
          <span>
            Plus-value latente : {formatEuro(pv)}
            {tauxPv != null && ` (${tauxPv.toFixed(1).replace('.', ',')} %)`}
          </span>
          <Tooltip {...DEFINITIONS.plus_value_latente} align="left" size={12} />
        </div>
      )}

      {enMoinsValue && (
        <div className="mt-2 rounded-md bg-red-50 text-red-800 text-[11px] px-2.5 py-1.5 leading-relaxed">
          La valeur estimée actuelle est inférieure à la valeur d'acquisition.
          Vérifiez votre saisie, ou s'il s'agit d'une dépréciation réelle de l'actif.
        </div>
      )}

      <div className="flex justify-between items-center mt-3 pt-3 border-t border-border-app">
        <span className="text-xs text-content-2">
          {actif.frequence_valorisation_libelle
            ? `Rappel : ${actif.frequence_valorisation_libelle}`
            : 'Pas de rappel'}
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={onValoriser}
            className="text-xs text-purple-600 dark:text-purple-400 font-medium cursor-pointer bg-transparent border-none hover:underline"
          >
            Valoriser
          </button>
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
            disabled={deleteActif.isPending}
            className="p-1.5 rounded-md text-content-2 hover:text-red-600 hover:bg-red-50 cursor-pointer disabled:opacity-50"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>
    </Card>
  )
}

function ValoriserModal({ actif, onClose }) {
  const [valeur, setValeur] = useState('')
  const [error, setError] = useState('')
  const valoriserAction = useResourceAction('patrimoine')

  const handleValoriser = () => {
    const v = parseFloat(valeur.replace(',', '.'))
    if (Number.isNaN(v) || v < 0) {
      setError('Valeur invalide.')
      return
    }
    valoriserAction.mutate(
      {
        id: actif.id,
        action: 'valoriser',
        payload: { valeur: v.toFixed(2) },
      },
      {
        onSuccess: () => {
          setValeur('')
          setError('')
          onClose()
        },
        onError: (err) => {
          setError(err.response?.data?.detail || 'Erreur lors de la valorisation.')
        },
      }
    )
  }

  if (!actif) return null

  return (
    <Modal
      isOpen={!!actif}
      onClose={onClose}
      title={`Valoriser — ${actif.nom}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Annuler</Button>
          <Button variant="primary" onClick={handleValoriser} disabled={valoriserAction.isPending}>
            {valoriserAction.isPending ? 'Enregistrement...' : 'Valoriser'}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="text-sm text-content-2">
          Valeur actuelle : <strong className="text-content">{formatEuro(actif.valeur_actuelle)}</strong>
        </div>
        <Input
          label="Nouvelle valeur estimée (€)" type="text" inputMode="decimal"
          value={valeur} onChange={setValeur} placeholder="0,00" error={error}
        />
        <div className="text-xs text-content-2">
          Cette valeur sera enregistrée dans l'historique avec la date du jour.
        </div>
      </div>
    </Modal>
  )
}

import { useState } from 'react'
import { useResourceList, useResourceAction, useDeleteResource } from '../hooks/useResource'
import { formatEuro } from '../utils/format'
import { RefreshCw, Pencil, Trash2 } from 'lucide-react'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Tooltip from '../components/ui/Tooltip'
import { DEFINITIONS } from '../constants/definitions'
import Modal from '../components/ui/Modal'
import Input from '../components/ui/Input'
import { Loading, ErrorState, EmptyState } from '../components/ui/States'
import AbonnementFormModal from '../components/abonnements/AbonnementFormModal'
import IconBadge from '../components/ui/IconBadge'


export default function AbonnementsPage() {
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedAbonnement, setSelectedAbonnement] = useState(null)
  const [divergenceFor, setDivergenceFor] = useState(null)

  const { data, isLoading, isError, refetch } = useResourceList('abonnements')
  const abonnements = data?.results ?? []

  const actifs = abonnements.filter((a) => a.actif)
  const enRetard = abonnements.filter((a) => a.est_en_retard).length
  const totalMensuel = actifs.reduce((s, a) => {
    const jours = a.frequence_nb_jours || 30
    return s + (Math.abs(Number(a.montant_attendu)) * 30) / jours
  }, 0)

  const openCreate = () => { setSelectedAbonnement(null); setModalOpen(true) }
  const openEdit = (ab) => { setSelectedAbonnement(ab); setModalOpen(true) }
  const closeModal = () => { setModalOpen(false); setSelectedAbonnement(null) }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-lg font-medium text-content">Abonnements</h1>
          <p className="text-sm text-content-2 mt-0.5">
            {actifs.length} actif{actifs.length > 1 ? 's' : ''}
            {enRetard > 0 && ` · ${enRetard} en retard`}
          </p>
        </div>
        <Button variant="primary" onClick={openCreate}>
          + Nouvel abonnement
        </Button>
      </div>

      {isLoading && <Loading message="Chargement des abonnements..." />}
      {isError && <ErrorState message="Impossible de charger les abonnements." onRetry={refetch} />}

      {!isLoading && !isError && (
        <>
          {abonnements.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              <MetricCard label="Total mensuel estimé" value={formatEuro(-totalMensuel)} def={DEFINITIONS.abo_total_mensuel} />
              <MetricCard label="Abonnements actifs" value={String(actifs.length)} />
              <MetricCard
                label="En retard"
                value={String(enRetard)}
                valueClass={enRetard > 0 ? 'text-amber-600' : 'text-content'}
                def={DEFINITIONS.abo_en_retard}
                defAlign="right"
              />
            </div>
          )}

          {abonnements.length === 0 ? (
            <EmptyState
              icon="🔄"
              message="Aucun abonnement enregistré."
              action={
                <Button variant="primary" onClick={openCreate}>
                  Ajouter un abonnement
                </Button>
              }
            />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {abonnements.map((ab) => (
                <AbonnementCard
                  key={ab.id}
                  abonnement={ab}
                  onEdit={() => openEdit(ab)}
                  onVerifier={() => setDivergenceFor(ab)}
                />
              ))}
            </div>
          )}
        </>
      )}

      <AbonnementFormModal isOpen={modalOpen} onClose={closeModal} abonnement={selectedAbonnement} />
      <DivergenceModal abonnement={divergenceFor} onClose={() => setDivergenceFor(null)} />
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

function AbonnementCard({ abonnement, onEdit, onVerifier }) {
  const enRetard = abonnement.est_en_retard
  const inactif = !abonnement.actif
  const deleteAbonnement = useDeleteResource('abonnements')

  const handleDelete = () => {
    if (!window.confirm(`Supprimer l'abonnement « ${abonnement.nom} » ?`)) return
    deleteAbonnement.mutate(abonnement.id)
  }

  return (
    <Card className={enRetard ? 'border-amber-600' : ''}>
      <div className="flex items-start gap-2.5 mb-3">
        <IconBadge Icon={RefreshCw} size={16} className="w-9 h-9 shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-content truncate">{abonnement.nom}</div>
          <div className="text-xs text-content-2">{abonnement.categorie_nom || '—'}</div>
        </div>
        <div className="flex gap-1 shrink-0">
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
            disabled={deleteAbonnement.isPending}
            className="p-1.5 rounded-md text-content-2 hover:text-red-600 hover:bg-red-50 cursor-pointer disabled:opacity-50"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>

      <div className="text-xl font-medium text-content">
        {formatEuro(abonnement.montant_attendu)}
      </div>
      <div className="text-xs text-content-2">
        {abonnement.frequence_libelle}
        {abonnement.jour_echeance && ` · échéance le ${abonnement.jour_echeance}`}
      </div>

      <div className="flex justify-between items-center mt-3 pt-3 border-t border-border-app">
        {inactif ? (
          <Badge variant="neutre">Inactif</Badge>
        ) : enRetard ? (
          <Badge variant="avertissement">⚠ En retard</Badge>
        ) : (
          <Badge variant="success">✓ À jour</Badge>
        )}
        <button
          onClick={onVerifier}
          className="text-xs text-purple-600 dark:text-purple-400 font-medium cursor-pointer bg-transparent border-none hover:underline"
        >
          Vérifier
        </button>
      </div>
    </Card>
  )
}

function DivergenceModal({ abonnement, onClose }) {
  const [montantReel, setMontantReel] = useState('')
  const [resultat, setResultat] = useState(null)
  const verifierAction = useResourceAction('abonnements')

  const handleVerifier = () => {
    const montant = parseFloat(montantReel.replace(',', '.')) || 0
    verifierAction.mutate(
      {
        id: abonnement.id,
        action: 'verifier-divergence',
        payload: { montant_reel: (-Math.abs(montant)).toFixed(2) },
      },
      { onSuccess: (data) => setResultat(data) }
    )
  }

  const handleClose = () => {
    setMontantReel('')
    setResultat(null)
    onClose()
  }

  if (!abonnement) return null

  return (
    <Modal
      isOpen={!!abonnement}
      onClose={handleClose}
      title={`Vérifier — ${abonnement.nom}`}
      footer={
        <>
          <Button variant="secondary" onClick={handleClose}>Fermer</Button>
          <Button variant="primary" onClick={handleVerifier} disabled={verifierAction.isPending}>
            Vérifier
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="text-sm text-content-2">
          Montant attendu : <strong className="text-content">{formatEuro(abonnement.montant_attendu)}</strong>
          <br />
          <span className="inline-flex items-center gap-1">
            Seuil de divergence : <strong className="text-content">{abonnement.seuil_divergence_pct} %</strong>
            <Tooltip {...DEFINITIONS.abo_seuil_divergence} align="left" size={12} />
          </span>
        </div>

        <Input
          label="Montant réel constaté (€)" type="text" inputMode="decimal"
          value={montantReel} onChange={setMontantReel} placeholder="0,00"
        />

        {resultat && (
          <div
            className={[
              'rounded-lg p-4 text-sm',
              resultat.en_divergence
                ? 'bg-amber-50 text-amber-800'
                : 'bg-teal-50 text-teal-800',
            ].join(' ')}
          >
            {resultat.en_divergence ? (
              <>⚠ Divergence détectée : <strong>{resultat.divergence_pct} %</strong> d'écart (seuil : {resultat.seuil_pct} %).</>
            ) : (
              <>✓ Pas de divergence significative : {resultat.divergence_pct} % d'écart (sous le seuil de {resultat.seuil_pct} %).</>
            )}
          </div>
        )}
      </div>
    </Modal>
  )
}

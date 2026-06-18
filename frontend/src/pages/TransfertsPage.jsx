import { useState } from 'react'
import { useResourceList, useDeleteResource } from '../hooks/useResource'
import { formatEuro, formatDate } from '../utils/format'
import { ArrowRight, Repeat, Trash2 } from 'lucide-react'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import IconBadge from '../components/ui/IconBadge'
import { Loading, ErrorState, EmptyState } from '../components/ui/States'
import TransfertFormModal from '../components/transferts/TransfertFormModal'

export default function TransfertsPage() {
  const [modalOpen, setModalOpen] = useState(false)

  const { data, isLoading, isError, refetch } = useResourceList('transferts')
  const transferts = data?.results ?? []

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-lg font-medium text-content">Transferts</h1>
          <p className="text-sm text-content-2 mt-0.5">
            Mouvements internes entre vos comptes
            {transferts.length > 0 && ` · ${transferts.length}`}
          </p>
        </div>
        <Button variant="primary" onClick={() => setModalOpen(true)}>
          + Nouveau transfert
        </Button>
      </div>

      {isLoading && <Loading message="Chargement des transferts..." />}
      {isError && <ErrorState message="Impossible de charger les transferts." onRetry={refetch} />}

      {!isLoading && !isError && (
        transferts.length === 0 ? (
          <EmptyState
            icon="🔁"
            message="Aucun transfert enregistré."
            action={
              <Button variant="primary" onClick={() => setModalOpen(true)}>
                Créer un transfert
              </Button>
            }
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {transferts.map((t) => (
              <TransfertCard key={t.id} transfert={t} />
            ))}
          </div>
        )
      )}

      <TransfertFormModal isOpen={modalOpen} onClose={() => setModalOpen(false)} />
    </div>
  )
}

function TransfertCard({ transfert }) {
  const deleteTransfert = useDeleteResource('transferts')

  const handleDelete = () => {
    if (!window.confirm('Annuler ce transfert ? Les deux flux liés seront supprimés.')) return
    deleteTransfert.mutate(transfert.id)
  }

  return (
    <Card>
      <div className="flex items-start gap-2.5 mb-3">
        <IconBadge Icon={Repeat} size={16} className="w-9 h-9 shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 text-sm font-medium text-content">
            <span className="truncate">{transfert.compte_source_nom}</span>
            <ArrowRight size={13} className="text-content-3 shrink-0" />
            <span className="truncate">{transfert.compte_destination_nom}</span>
          </div>
          <div className="text-xs text-content-2">{formatDate(transfert.date_flux)}</div>
        </div>
        <button
          onClick={handleDelete}
          title="Annuler le transfert"
          disabled={deleteTransfert.isPending}
          className="p-1.5 rounded-md text-content-2 hover:text-red-600 hover:bg-red-50 cursor-pointer disabled:opacity-50 shrink-0"
        >
          <Trash2 size={13} />
        </button>
      </div>

      <div className="text-xl font-medium text-content">{formatEuro(transfert.montant)}</div>
      {transfert.notes && (
        <div className="text-xs text-content-2 mt-1 truncate">{transfert.notes}</div>
      )}
    </Card>
  )
}

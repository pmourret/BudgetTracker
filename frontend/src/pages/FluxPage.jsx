import { useState } from 'react'
import { useResourceList, useDeleteResource } from '../hooks/useResource'
import { useIsMobile } from '../hooks/useMediaQuery'
import { formatEuro, formatDate } from '../utils/format'
import { Pencil, Trash2 } from 'lucide-react'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import { Loading, ErrorState, EmptyState } from '../components/ui/States'
import FluxFormModal from '../components/flux/FluxFormModal'

export default function FluxPage() {
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedFlux, setSelectedFlux] = useState(null)
  const isMobile = useIsMobile()
  const { data, isLoading, isError, refetch } = useResourceList('flux')

  const flux = data?.results ?? []

  const openCreate = () => { setSelectedFlux(null); setModalOpen(true) }
  const openEdit = (f) => { setSelectedFlux(f); setModalOpen(true) }
  const closeModal = () => { setModalOpen(false); setSelectedFlux(null) }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-lg font-medium text-content">Flux</h1>
          <p className="text-sm text-content-2 mt-0.5">
            {data?.count ?? 0} mouvement{(data?.count ?? 0) > 1 ? 's' : ''}
          </p>
        </div>
        <Button variant="primary" onClick={openCreate}>
          + Nouveau flux
        </Button>
      </div>

      {isLoading && <Loading message="Chargement des flux..." />}
      {isError && <ErrorState message="Impossible de charger les flux." onRetry={refetch} />}

      {!isLoading && !isError && flux.length === 0 && (
        <EmptyState
          icon="💸"
          message="Aucun flux enregistré."
          action={
            <Button variant="primary" onClick={openCreate}>
              Saisir mon premier flux
            </Button>
          }
        />
      )}

      {!isLoading && !isError && flux.length > 0 && (
        isMobile
          ? <FluxCards flux={flux} onEdit={openEdit} />
          : <FluxTable flux={flux} onEdit={openEdit} />
      )}

      <FluxFormModal isOpen={modalOpen} onClose={closeModal} flux={selectedFlux} />
    </div>
  )
}

function MontantBadge({ montant }) {
  const value = Number(montant)
  const isDepense = value < 0
  return (
    <span className={`text-sm font-medium ${isDepense ? 'text-red-600' : 'text-teal-600'}`}>
      {formatEuro(value)}
    </span>
  )
}

function AjustementBadge() {
  return (
    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 border border-amber-200">
      Ajustement
    </span>
  )
}

function FluxRowActions({ flux, onEdit }) {
  const deleteFlux = useDeleteResource('flux')

  const handleDelete = () => {
    if (!window.confirm(`Supprimer « ${flux.libelle} » ? Le solde du compte sera recalculé.`)) return
    deleteFlux.mutate(flux.id)
  }

  // Un flux de transfert ne se supprime jamais seul (paire débit/crédit) :
  // le modal d'édition redirige vers la page Transferts.
  if (flux.est_ajustement || flux.est_transfert) {
    return (
      <button
        onClick={() => onEdit(flux)}
        title="Voir le détail"
        className="p-1.5 rounded-md text-content-2 hover:text-content hover:bg-surface-3 cursor-pointer"
      >
        <Pencil size={13} />
      </button>
    )
  }

  return (
    <>
      <button
        onClick={() => onEdit(flux)}
        title="Modifier"
        className="p-1.5 rounded-md text-content-2 hover:text-content hover:bg-surface-3 cursor-pointer"
      >
        <Pencil size={13} />
      </button>
      <button
        onClick={handleDelete}
        title="Supprimer"
        disabled={deleteFlux.isPending}
        className="p-1.5 rounded-md text-content-2 hover:text-red-600 hover:bg-red-50 cursor-pointer disabled:opacity-50"
      >
        <Trash2 size={13} />
      </button>
    </>
  )
}

function FluxTable({ flux, onEdit }) {
  return (
    <Card bodyClassName="p-0">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-border-app">
            <th className="text-left px-4 py-3 text-xs font-medium text-content-2">Date</th>
            <th className="text-left px-4 py-3 text-xs font-medium text-content-2">Libellé</th>
            <th className="text-left px-4 py-3 text-xs font-medium text-content-2">Catégorie</th>
            <th className="text-left px-4 py-3 text-xs font-medium text-content-2">Compte</th>
            <th className="text-right px-4 py-3 text-xs font-medium text-content-2">Montant</th>
            <th className="px-4 py-3 w-16"></th>
          </tr>
        </thead>
        <tbody>
          {flux.map((f) => (
            <tr key={f.id} className="border-b border-border-app last:border-b-0 group">
              <td className="px-4 py-3 text-content">{formatDate(f.date_flux)}</td>
              <td className="px-4 py-3 text-content">
                <div className="flex items-center gap-2">
                  {f.libelle}
                  {f.est_ajustement && <AjustementBadge />}
                </div>
              </td>
              <td className="px-4 py-3 text-content">{f.categorie_nom || '—'}</td>
              <td className="px-4 py-3 text-content">{f.compte_nom || '—'}</td>
              <td className="px-4 py-3 text-right"><MontantBadge montant={f.montant} /></td>
              <td className="px-4 py-3">
                <div className="flex gap-0.5 justify-end opacity-0 group-hover:opacity-100 transition-opacity">
                  <FluxRowActions flux={f} onEdit={onEdit} />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}

function FluxCardActions({ flux, onEdit }) {
  const deleteFlux = useDeleteResource('flux')

  const handleDelete = () => {
    if (!window.confirm(`Supprimer « ${flux.libelle} » ? Le solde du compte sera recalculé.`)) return
    deleteFlux.mutate(flux.id)
  }

  // Un flux de transfert ne se supprime jamais seul (paire débit/crédit) :
  // le modal d'édition redirige vers la page Transferts.
  if (flux.est_ajustement || flux.est_transfert) {
    return (
      <div className="flex gap-1 shrink-0">
        <button
          onClick={() => onEdit(flux)}
          title="Voir le détail"
          className="p-1.5 rounded-md text-content-2 hover:text-content hover:bg-surface-3 cursor-pointer"
        >
          <Pencil size={13} />
        </button>
      </div>
    )
  }

  return (
    <div className="flex gap-1 shrink-0">
      <button
        onClick={() => onEdit(flux)}
        title="Modifier"
        className="p-1.5 rounded-md text-content-2 hover:text-content hover:bg-surface-3 cursor-pointer"
      >
        <Pencil size={13} />
      </button>
      <button
        onClick={handleDelete}
        title="Supprimer"
        disabled={deleteFlux.isPending}
        className="p-1.5 rounded-md text-content-2 hover:text-red-600 hover:bg-red-50 cursor-pointer disabled:opacity-50"
      >
        <Trash2 size={13} />
      </button>
    </div>
  )
}

function FluxCards({ flux, onEdit }) {
  return (
    <div className="flex flex-col gap-2">
      {flux.map((f) => (
        <Card key={f.id} bodyClassName="px-4 py-3.5">
          <div className="flex justify-between items-start gap-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <div className="text-sm font-medium text-content truncate">{f.libelle}</div>
                {f.est_ajustement && <AjustementBadge />}
              </div>
              <div className="text-xs text-content-2 mt-0.5">
                {f.categorie_nom || '—'} · {formatDate(f.date_flux)}
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <MontantBadge montant={f.montant} />
              <FluxCardActions flux={f} onEdit={onEdit} />
            </div>
          </div>
        </Card>
      ))}
    </div>
  )
}

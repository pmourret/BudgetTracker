import { useState } from 'react'
import { useResourceList, useDeleteResource, useUpdateResource } from '../hooks/useResource'
import { formatEuro } from '../utils/format'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import { Loading, ErrorState, EmptyState } from '../components/ui/States'
import IconBadge from '../components/ui/IconBadge'
import { Landmark, Pencil, Trash2 } from 'lucide-react'
import CompteFormModal from '../components/comptes/CompteFormModal'

export default function ComptesPage() {
  const { data, isLoading, isError, refetch } = useResourceList('comptes')
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedCompte, setSelectedCompte] = useState(null)

  const comptes = data?.results ?? []
  const totalTheorique = comptes.reduce((sum, c) => sum + Number(c.solde_theorique || 0), 0)
  const totalReel = comptes.reduce((sum, c) => sum + Number(c.solde_reel || 0), 0)
  const ecartTotal = totalReel - totalTheorique

  const openCreate = () => { setSelectedCompte(null); setModalOpen(true) }
  const openEdit = (compte) => { setSelectedCompte(compte); setModalOpen(true) }
  const closeModal = () => { setModalOpen(false); setSelectedCompte(null) }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-lg font-medium text-content">Comptes</h1>
          <p className="text-sm text-content-2 mt-0.5">
            {comptes.length} compte{comptes.length > 1 ? 's' : ''} actif{comptes.length > 1 ? 's' : ''}
          </p>
        </div>
        <Button variant="primary" onClick={openCreate}>+ Nouveau compte</Button>
      </div>

      {isLoading && <Loading message="Chargement des comptes..." />}
      {isError && <ErrorState message="Impossible de charger les comptes." onRetry={refetch} />}

      {!isLoading && !isError && (comptes.length === 0 ? (
        <EmptyState
          icon="💳"
          message="Aucun compte pour le moment."
          action={<Button variant="primary" onClick={openCreate}>Créer mon premier compte</Button>}
        />
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
            <MetricCard label="Solde théorique" value={formatEuro(totalTheorique)} />
            <MetricCard label="Solde confirmé" value={formatEuro(totalReel)} />
            <MetricCard
              label="En attente"
              value={formatEuro(ecartTotal)}
              valueClass={ecartTotal === 0 ? 'text-teal-600' : ecartTotal > 0 ? 'text-amber-600' : 'text-teal-600'}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {comptes.map((compte) => (
              <CompteCard
                key={compte.id}
                compte={compte}
                onEdit={() => openEdit(compte)}
              />
            ))}
          </div>
        </>
      ))}

      <CompteFormModal
        isOpen={modalOpen}
        onClose={closeModal}
        compte={selectedCompte}
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

function CompteCard({ compte, onEdit }) {
  const ecart = Number(compte.ecart_solde || 0)
  const deleteCompte = useDeleteResource('comptes')
  const updateCompte = useUpdateResource('comptes')
  const [deleteError, setDeleteError] = useState(null)

  const handleDelete = () => {
    setDeleteError(null)
    if (!window.confirm(`Supprimer le compte « ${compte.nom} » ?`)) return
    deleteCompte.mutate(compte.id, {
      onError: (err) => {
        const msg = err.response?.data?.detail || 'Erreur lors de la suppression.'
        setDeleteError(msg)
      },
    })
  }

  const handleToggleActif = () => {
    const action = compte.actif ? 'désactiver' : 'réactiver'
    if (!window.confirm(`${action.charAt(0).toUpperCase() + action.slice(1)} le compte « ${compte.nom} » ?`)) return
    updateCompte.mutate({ id: compte.id, payload: { actif: !compte.actif } })
  }

  return (
    <Card>
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <IconBadge Icon={Landmark} size={18} className="w-10 h-10" />
          <div>
            <div className="text-sm font-medium text-content">
              {compte.etablissement_libelle || compte.nom}
            </div>
            <div className="text-xs text-content-2">
              {compte.titulaire_libelle} · {compte.type_compte_libelle}
            </div>
          </div>
        </div>
        <div className="flex gap-1 shrink-0">
          <button
            onClick={onEdit}
            title="Modifier"
            className="p-1.5 rounded-md text-content-2 hover:text-content hover:bg-surface-3 cursor-pointer"
          >
            <Pencil size={14} />
          </button>
          <button
            onClick={handleDelete}
            title="Supprimer"
            disabled={deleteCompte.isPending}
            className="p-1.5 rounded-md text-content-2 hover:text-red-600 hover:bg-red-50 cursor-pointer disabled:opacity-50"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      {deleteError && (
        <div className="mb-3 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          {deleteError}
          <button
            onClick={handleToggleActif}
            className="ml-2 underline font-medium cursor-pointer"
          >
            Désactiver à la place
          </button>
        </div>
      )}

      <div className="text-2xl font-medium text-content">
        {formatEuro(compte.solde_theorique)}
      </div>
      <div className="text-[11px] text-content-2">Solde théorique (avec prévisionnels)</div>

      <div className="flex justify-between mt-4 pt-3.5 border-t border-border-app">
        <div>
          <div className="text-[11px] text-content-2">Solde confirmé</div>
          <div className="text-sm font-medium text-content">{formatEuro(compte.solde_reel)}</div>
        </div>
        <div className="text-right">
          <div className="text-[11px] text-content-2">En attente</div>
          <div className={`text-sm font-medium ${
            ecart === 0 ? 'text-teal-600' : ecart > 0 ? 'text-amber-600' : 'text-teal-600'
          }`}>
            {ecart !== 0 ? (ecart > 0 ? `−${formatEuro(Math.abs(ecart))}` : `+${formatEuro(Math.abs(ecart))}`) : formatEuro(0)}
          </div>
        </div>
      </div>

      {!compte.actif && (
        <div className="mt-3 text-[11px] text-content-3 bg-surface-3 rounded px-2 py-1">
          Compte désactivé
        </div>
      )}
    </Card>
  )
}

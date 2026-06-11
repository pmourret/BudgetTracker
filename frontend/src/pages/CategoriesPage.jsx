import { useState } from 'react'
import { ChevronRight, ChevronDown, Pencil, Trash2, Plus, Tag } from 'lucide-react'
import { useResourceList, useDeleteResource, useResourceAction } from '../hooks/useResource'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import IconBadge from '../components/ui/IconBadge'
import { Loading, ErrorState, EmptyState } from '../components/ui/States'
import CategorieFormModal from '../components/categories/CategorieFormModal'

export default function CategoriesPage() {
  const [expanded, setExpanded] = useState(new Set())
  const [modal, setModal] = useState({ open: false, categorie: null, parentId: null, parentNom: null })

  const { data, isLoading, isError, refetch } = useResourceList('categories')
  const categories = data?.results ?? []

  const majeures = categories.filter((c) => c.est_racine)
  const mineures = categories.filter((c) => !c.est_racine)

  const toggle = (id) =>
    setExpanded((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  const openCreateMajeure = () =>
    setModal({ open: true, categorie: null, parentId: null, parentNom: null })
  const openEdit = (cat) =>
    setModal({ open: true, categorie: cat, parentId: null, parentNom: null })
  const openCreateMineure = (majeure) => {
    if (!expanded.has(majeure.id)) toggle(majeure.id)
    setModal({ open: true, categorie: null, parentId: majeure.id, parentNom: majeure.nom })
  }
  const closeModal = () =>
    setModal({ open: false, categorie: null, parentId: null, parentNom: null })

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-lg font-medium text-content">Catégories</h1>
          <p className="text-sm text-content-2 mt-0.5">
            {majeures.length} principale{majeures.length !== 1 ? 's' : ''}
            {' · '}
            {mineures.length} sous-catégorie{mineures.length !== 1 ? 's' : ''}
          </p>
        </div>
        <Button variant="primary" onClick={openCreateMajeure}>+ Nouvelle catégorie</Button>
      </div>

      {isLoading && <Loading message="Chargement des catégories..." />}
      {isError && <ErrorState message="Impossible de charger les catégories." onRetry={refetch} />}

      {!isLoading && !isError && majeures.length === 0 && (
        <EmptyState
          icon="🏷️"
          message="Aucune catégorie configurée."
          action={
            <Button variant="primary" onClick={openCreateMajeure}>
              Créer une catégorie
            </Button>
          }
        />
      )}

      {!isLoading && !isError && majeures.length > 0 && (
        <div className="flex flex-col gap-2">
          {majeures.map((maj) => (
            <MajeureBlock
              key={maj.id}
              majeure={maj}
              mineures={mineures.filter((m) => String(m.parent) === String(maj.id))}
              isExpanded={expanded.has(maj.id)}
              onToggle={() => toggle(maj.id)}
              onEdit={() => openEdit(maj)}
              onAddMineure={() => openCreateMineure(maj)}
              onEditMineure={(m) => openEdit(m)}
            />
          ))}
        </div>
      )}

      <CategorieFormModal
        isOpen={modal.open}
        onClose={closeModal}
        categorie={modal.categorie}
        parentId={modal.parentId}
        parentNom={modal.parentNom}
      />
    </div>
  )
}

function MajeureBlock({ majeure, mineures, isExpanded, onToggle, onEdit, onAddMineure, onEditMineure }) {
  const deleteCategorie = useDeleteResource('categories')
  const desactiverAction = useResourceAction('categories')

  const handleDelete = (cat) => {
    if (!window.confirm(`Supprimer « ${cat.nom} » ?`)) return
    deleteCategorie.mutate(cat.id, {
      onError: (err) => {
        const detail = err.response?.data?.detail || 'Impossible de supprimer cette catégorie.'
        if (window.confirm(`${detail}\n\nDésactiver à la place ?`)) {
          desactiverAction.mutate({ id: cat.id, action: 'desactiver' })
        }
      },
    })
  }

  return (
    <div className="rounded-xl border border-border-app overflow-hidden bg-surface">
      {/* En-tête de la catégorie principale */}
      <div className="flex items-center gap-2 px-4 py-3 hover:bg-surface-3 transition-colors">
        <button
          onClick={onToggle}
          className="flex items-center gap-2.5 flex-1 min-w-0 cursor-pointer"
        >
          {isExpanded
            ? <ChevronDown size={15} className="text-content-3 shrink-0" />
            : <ChevronRight size={15} className="text-content-3 shrink-0" />}
          <IconBadge Icon={Tag} size={14} className="w-8 h-8 shrink-0" />
          <span className="font-medium text-sm text-content truncate">{majeure.nom}</span>
          <span className="text-xs text-content-3 shrink-0 ml-1">
            {mineures.length > 0 ? `${mineures.length} sous-cat.` : 'sans subdivision'}
          </span>
          {!majeure.actif && <Badge variant="neutre">Inactif</Badge>}
        </button>
        <div className="flex gap-0.5 shrink-0">
          <button
            onClick={onAddMineure}
            title="Ajouter une sous-catégorie"
            className="p-1.5 rounded-md text-content-2 hover:text-purple-600 hover:bg-surface-3 cursor-pointer"
          >
            <Plus size={14} />
          </button>
          <button
            onClick={onEdit}
            title="Modifier"
            className="p-1.5 rounded-md text-content-2 hover:text-content hover:bg-surface-3 cursor-pointer"
          >
            <Pencil size={13} />
          </button>
          <button
            onClick={() => handleDelete(majeure)}
            title="Supprimer"
            disabled={deleteCategorie.isPending}
            className="p-1.5 rounded-md text-content-2 hover:text-red-600 hover:bg-red-50 cursor-pointer disabled:opacity-50"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>

      {/* Sous-catégories */}
      {isExpanded && (
        <div className="border-t border-border-app bg-surface-2">
          {mineures.length === 0 ? (
            <div className="px-4 py-3 text-xs text-content-3 italic">
              Aucune sous-catégorie —{' '}
              <button
                onClick={onAddMineure}
                className="text-purple-600 dark:text-purple-400 hover:underline cursor-pointer bg-transparent border-none"
              >
                en ajouter une
              </button>
            </div>
          ) : (
            mineures.map((m, i) => (
              <MineureRow
                key={m.id}
                mineure={m}
                isLast={i === mineures.length - 1}
                onEdit={() => onEditMineure(m)}
                onDelete={() => handleDelete(m)}
                isPending={deleteCategorie.isPending}
              />
            ))
          )}
        </div>
      )}
    </div>
  )
}

function MineureRow({ mineure, isLast, onEdit, onDelete, isPending }) {
  return (
    <div
      className={[
        'flex items-center gap-3 px-4 py-2.5',
        !isLast ? 'border-b border-border-app' : '',
      ].join(' ')}
    >
      <div className="w-5 shrink-0" />
      <div className="w-1.5 h-1.5 rounded-full bg-content-3 shrink-0" />
      <span className="text-sm text-content flex-1 truncate">{mineure.nom}</span>
      {!mineure.actif && <Badge variant="neutre">Inactif</Badge>}
      <div className="flex gap-0.5 shrink-0">
        <button
          onClick={onEdit}
          title="Modifier"
          className="p-1 rounded text-content-2 hover:text-content hover:bg-surface-3 cursor-pointer"
        >
          <Pencil size={12} />
        </button>
        <button
          onClick={onDelete}
          title="Supprimer"
          disabled={isPending}
          className="p-1 rounded text-content-2 hover:text-red-600 hover:bg-red-50 cursor-pointer disabled:opacity-50"
        >
          <Trash2 size={12} />
        </button>
      </div>
    </div>
  )
}

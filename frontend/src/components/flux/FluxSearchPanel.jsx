import { useEffect, useMemo, useRef, useState } from 'react'
import { Pencil, Trash2, Search, X } from 'lucide-react'
import {
  useInfiniteResource,
  useDeleteResource,
  useResourceList,
  useCategories,
} from '../../hooks/useResource'
import { useTitulaires } from '../../hooks/useReferentiels'
import useDebouncedValue from '../../hooks/useDebouncedValue'
import { useIsMobile } from '../../hooks/useMediaQuery'
import { formatEuro, formatDate } from '../../utils/format'
import Card from '../ui/Card'
import Button from '../ui/Button'
import Input from '../ui/Input'
import Select from '../ui/Select'
import { Loading, ErrorState, EmptyState } from '../ui/States'
import FluxFormModal from './FluxFormModal'

const EMPTY_FILTERS = {
  search: '',
  compte: '',
  titulaire_compte: '',
  categorie: '',
  est_definitif: '',
  sens: '',
  date_min: '',
  date_max: '',
}

/**
 * Panneau de recherche + liste des flux, chargement paginé à la demande.
 * Réutilisé par FluxPage (global) et CompteDetailPage (scopé à un compte).
 *
 * Props :
 * - baseParams : filtres fixes fusionnés dans chaque requête (ex. { compte: id }).
 * - hideCompteFilter : masque le select Compte (page compte).
 * - enableCreate : affiche le bouton « + Nouveau flux ».
 */
export default function FluxSearchPanel({
  baseParams = {},
  hideCompteFilter = false,
  enableCreate = false,
}) {
  const isMobile = useIsMobile()
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const debouncedSearch = useDebouncedValue(filters.search, 350)

  const [modalOpen, setModalOpen] = useState(false)
  const [selectedFlux, setSelectedFlux] = useState(null)
  const openCreate = () => { setSelectedFlux(null); setModalOpen(true) }
  const openEdit = (f) => { setSelectedFlux(f); setModalOpen(true) }
  const closeModal = () => { setModalOpen(false); setSelectedFlux(null) }

  const set = (key, value) => setFilters((f) => ({ ...f, [key]: value }))
  const reset = () => setFilters(EMPTY_FILTERS)

  // Options des filtres
  const { data: comptesData } = useResourceList('comptes', { page_size: 1000 })
  const { options: titulairesOpts } = useTitulaires()
  const { data: categoriesData } = useCategories()

  const comptesOpts = (comptesData?.results ?? []).map((c) => ({
    value: String(c.id),
    label: (c.etablissement_libelle ? `${c.nom} — ${c.etablissement_libelle}` : c.nom)
      + (c.est_commun ? ' · Commun' : ''),
  }))

  const allCats = categoriesData?.results ?? []
  const majeures = allCats.filter((c) => c.est_racine)
  const mineures = allCats.filter((c) => !c.est_racine)
  const categoriesOpts = majeures
    .filter((maj) => !mineures.some((m) => String(m.parent) === String(maj.id)))
    .map((maj) => ({ value: String(maj.id), label: maj.nom }))
  const categoriesGroups = majeures
    .filter((maj) => mineures.some((m) => String(m.parent) === String(maj.id)))
    .map((maj) => ({
      label: maj.nom,
      options: mineures
        .filter((m) => String(m.parent) === String(maj.id))
        .map((m) => ({ value: String(m.id), label: m.nom })),
    }))

  // Construction des query params à partir des filtres actifs
  const params = useMemo(() => {
    const p = { ...baseParams, ordering: '-date_flux' }
    if (debouncedSearch.trim()) p.search = debouncedSearch.trim()
    if (filters.compte) p.compte = filters.compte
    if (filters.titulaire_compte) p.titulaire_compte = filters.titulaire_compte
    if (filters.categorie) p.categorie = filters.categorie
    if (filters.est_definitif) p.est_definitif = filters.est_definitif
    if (filters.date_min) p.date_min = filters.date_min
    if (filters.date_max) p.date_max = filters.date_max
    // Sens dérivé du signe du montant (dépense < 0, recette > 0)
    if (filters.sens === 'depense') p.montant_max = '-0.01'
    if (filters.sens === 'recette') p.montant_min = '0.01'
    return p
  }, [baseParams, debouncedSearch, filters])

  const query = useInfiniteResource('flux', params)
  const flux = query.data?.pages.flatMap((pg) => pg.results) ?? []
  const count = query.data?.pages[0]?.count ?? 0

  const hasActiveFilters = Object.entries(filters).some(([, v]) => v !== '')

  // Chargement dynamique : charge la page suivante quand la sentinelle entre
  // dans le viewport (fallback : bouton « Charger plus »).
  const { hasNextPage, isFetchingNextPage, fetchNextPage } = query
  const sentinelRef = useRef(null)
  useEffect(() => {
    const el = sentinelRef.current
    if (!el) return
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage()
        }
      },
      { rootMargin: '250px' }
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [hasNextPage, isFetchingNextPage, fetchNextPage])

  return (
    <div className="flex flex-col gap-4">
      {/* Barre d'outils : compteur + création */}
      <div className="flex justify-between items-center gap-2">
        <p className="text-sm text-content-2">
          {count} mouvement{count > 1 ? 's' : ''}
          {hasActiveFilters ? ' (filtrés)' : ''}
        </p>
        {enableCreate && (
          <Button variant="primary" onClick={openCreate}>+ Nouveau flux</Button>
        )}
      </div>

      {/* Filtres */}
      <Card bodyClassName="p-3 sm:p-4">
        <div className="flex flex-col gap-3">
          <div className="relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-content-3 pointer-events-none" />
            <input
              type="text"
              value={filters.search}
              onChange={(e) => set('search', e.target.value)}
              placeholder="Rechercher un flux (libellé, référence, notes)…"
              className="w-full h-11 sm:h-10 pl-9 pr-3 rounded-lg border border-border-app bg-surface text-sm text-content outline-none focus:border-purple-600"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {!hideCompteFilter && (
              <Select
                label="Compte" value={filters.compte} onChange={(v) => set('compte', v)}
                options={comptesOpts} placeholder="Tous les comptes"
              />
            )}
            <Select
              label="Propriétaire du compte" value={filters.titulaire_compte}
              onChange={(v) => set('titulaire_compte', v)}
              options={titulairesOpts} placeholder="Tous les propriétaires"
            />
            <Select
              label="Catégorie" value={filters.categorie} onChange={(v) => set('categorie', v)}
              options={categoriesOpts} groups={categoriesGroups} placeholder="Toutes les catégories"
            />
            <Select
              label="Statut" value={filters.est_definitif} onChange={(v) => set('est_definitif', v)}
              options={[
                { value: 'true', label: 'Validé' },
                { value: 'false', label: 'Prévisionnel' },
              ]}
              placeholder="Tous les statuts"
            />
            <Select
              label="Sens" value={filters.sens} onChange={(v) => set('sens', v)}
              options={[
                { value: 'depense', label: 'Dépense' },
                { value: 'recette', label: 'Recette' },
              ]}
              placeholder="Tous les sens"
            />
            <Input
              label="Du" type="date" value={filters.date_min}
              onChange={(v) => set('date_min', v)}
            />
            <Input
              label="Au" type="date" value={filters.date_max}
              onChange={(v) => set('date_max', v)}
            />
          </div>

          {hasActiveFilters && (
            <button
              onClick={reset}
              className="self-start inline-flex items-center gap-1 text-xs text-content-2 hover:text-content cursor-pointer"
            >
              <X size={13} /> Réinitialiser les filtres
            </button>
          )}
        </div>
      </Card>

      {/* Résultats */}
      {query.isLoading && <Loading message="Chargement des flux..." />}
      {query.isError && <ErrorState message="Impossible de charger les flux." onRetry={query.refetch} />}

      {!query.isLoading && !query.isError && flux.length === 0 && (
        <EmptyState
          icon="🔍"
          message={hasActiveFilters ? 'Aucun flux ne correspond aux filtres.' : 'Aucun flux enregistré.'}
          action={
            hasActiveFilters
              ? <Button variant="secondary" onClick={reset}>Réinitialiser</Button>
              : enableCreate
                ? <Button variant="primary" onClick={openCreate}>Saisir mon premier flux</Button>
                : null
          }
        />
      )}

      {!query.isLoading && !query.isError && flux.length > 0 && (
        isMobile
          ? <FluxCards flux={flux} onEdit={openEdit} />
          : <FluxTable flux={flux} onEdit={openEdit} />
      )}

      {/* Sentinelle + bouton de chargement */}
      <div ref={sentinelRef} />
      {query.hasNextPage && (
        <Button
          variant="secondary"
          onClick={() => query.fetchNextPage()}
          disabled={query.isFetchingNextPage}
          className="self-center"
        >
          {query.isFetchingNextPage ? 'Chargement…' : 'Charger plus'}
        </Button>
      )}

      <FluxFormModal isOpen={modalOpen} onClose={closeModal} flux={selectedFlux} />
    </div>
  )
}

function MontantBadge({ montant }) {
  const value = Number(montant)
  return (
    <span className={`text-sm font-medium ${value < 0 ? 'text-red-600' : 'text-teal-600'}`}>
      {formatEuro(value)}
    </span>
  )
}

function Tag({ label }) {
  return (
    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 border border-amber-200">
      {label}
    </span>
  )
}

function FluxActions({ flux, onEdit, inline = false }) {
  const deleteFlux = useDeleteResource('flux')

  const handleDelete = () => {
    if (!window.confirm(`Supprimer « ${flux.libelle} » ? Le solde du compte sera recalculé.`)) return
    deleteFlux.mutate(flux.id)
  }

  const wrap = inline ? 'flex gap-0.5 justify-end' : 'flex gap-1 shrink-0'

  // Un flux de transfert / d'ajustement ne se supprime jamais seul.
  if (flux.est_ajustement || flux.est_transfert) {
    return (
      <div className={wrap}>
        <button
          onClick={() => onEdit(flux)} title="Voir le détail"
          className="p-1.5 rounded-md text-content-2 hover:text-content hover:bg-surface-3 cursor-pointer"
        >
          <Pencil size={13} />
        </button>
      </div>
    )
  }

  return (
    <div className={wrap}>
      <button
        onClick={() => onEdit(flux)} title="Modifier"
        className="p-1.5 rounded-md text-content-2 hover:text-content hover:bg-surface-3 cursor-pointer"
      >
        <Pencil size={13} />
      </button>
      <button
        onClick={handleDelete} title="Supprimer" disabled={deleteFlux.isPending}
        className="p-1.5 rounded-md text-content-2 hover:text-red-600 hover:bg-red-50 cursor-pointer disabled:opacity-50"
      >
        <Trash2 size={13} />
      </button>
    </div>
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
                  {f.libelle || '—'}
                  {f.est_transfert && <Tag label="Transfert" />}
                  {f.est_ajustement && <Tag label="Ajustement" />}
                </div>
              </td>
              <td className="px-4 py-3 text-content">{f.categorie_nom || '—'}</td>
              <td className="px-4 py-3 text-content">{f.compte_nom || '—'}</td>
              <td className="px-4 py-3 text-right"><MontantBadge montant={f.montant} /></td>
              <td className="px-4 py-3">
                <div className="opacity-0 group-hover:opacity-100 transition-opacity">
                  <FluxActions flux={f} onEdit={onEdit} inline />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
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
                <div className="text-sm font-medium text-content truncate">{f.libelle || '—'}</div>
                {f.est_transfert && <Tag label="Transfert" />}
                {f.est_ajustement && <Tag label="Ajustement" />}
              </div>
              <div className="text-xs text-content-2 mt-0.5">
                {f.categorie_nom || '—'} · {f.compte_nom || '—'} · {formatDate(f.date_flux)}
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <MontantBadge montant={f.montant} />
              <FluxActions flux={f} onEdit={onEdit} />
            </div>
          </div>
        </Card>
      ))}
    </div>
  )
}

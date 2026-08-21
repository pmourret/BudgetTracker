import { useEffect, useMemo, useRef, useState } from 'react'
import {
  useInfiniteResource,
  useDeleteResource,
  useResourceList,
} from '../hooks/useResource'
import useDebouncedValue from '../hooks/useDebouncedValue'
import { useIsMobile } from '../hooks/useMediaQuery'
import { formatEuro, formatDate } from '../utils/format'
import { ArrowRight, Repeat, Trash2, Search, X } from 'lucide-react'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import Select from '../components/ui/Select'
import IconBadge from '../components/ui/IconBadge'
import { Loading, ErrorState, EmptyState } from '../components/ui/States'
import TransfertFormModal from '../components/transferts/TransfertFormModal'
import TransfertsAnalyse from '../components/transferts/TransfertsAnalyse'

const EMPTY_FILTERS = {
  search: '',
  compte_source: '',
  compte_destination: '',
  est_definitif: '',
  date_min: '',
  date_max: '',
}

export default function TransfertsPage() {
  const [tab, setTab] = useState('liste')
  const [modalOpen, setModalOpen] = useState(false)

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-lg font-medium text-content">Transferts</h1>
          <p className="text-sm text-content-2 mt-0.5">
            Mouvements internes entre vos comptes
          </p>
        </div>
        <Button variant="primary" onClick={() => setModalOpen(true)}>
          + Nouveau transfert
        </Button>
      </div>

      <div className="flex gap-1 border-b border-border-app">
        <TabBtn active={tab === 'liste'} onClick={() => setTab('liste')}>Liste</TabBtn>
        <TabBtn active={tab === 'analyse'} onClick={() => setTab('analyse')}>Analyse</TabBtn>
      </div>

      {tab === 'analyse' ? (
        <TransfertsAnalyse />
      ) : (
        <TransfertsListe onCreate={() => setModalOpen(true)} />
      )}

      <TransfertFormModal isOpen={modalOpen} onClose={() => setModalOpen(false)} />
    </div>
  )
}

function TabBtn({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={[
        'px-3 py-2 text-sm cursor-pointer border-b-2 -mb-px transition-colors',
        active
          ? 'border-purple-600 text-content font-medium'
          : 'border-transparent text-content-2 hover:text-content',
      ].join(' ')}
    >
      {children}
    </button>
  )
}

function TransfertsListe({ onCreate }) {
  const isMobile = useIsMobile()
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const debouncedSearch = useDebouncedValue(filters.search, 350)

  const set = (key, value) => setFilters((f) => ({ ...f, [key]: value }))
  const reset = () => setFilters(EMPTY_FILTERS)

  const { data: comptesData } = useResourceList('comptes', { page_size: 1000 })
  const comptesOpts = (comptesData?.results ?? []).map((c) => ({
    value: String(c.id),
    label: (c.etablissement_libelle ? `${c.nom} — ${c.etablissement_libelle}` : c.nom)
      + (c.est_commun ? ' · Commun' : ''),
  }))

  const params = useMemo(() => {
    const p = { ordering: '-date_flux' }
    if (debouncedSearch.trim()) p.search = debouncedSearch.trim()
    if (filters.compte_source) p.compte_source = filters.compte_source
    if (filters.compte_destination) p.compte_destination = filters.compte_destination
    if (filters.est_definitif) p.est_definitif = filters.est_definitif
    if (filters.date_min) p.date_min = filters.date_min
    if (filters.date_max) p.date_max = filters.date_max
    return p
  }, [debouncedSearch, filters])

  const query = useInfiniteResource('transferts', params)
  const transferts = query.data?.pages.flatMap((pg) => pg.results) ?? []
  const count = query.data?.pages[0]?.count ?? 0
  const hasActiveFilters = Object.values(filters).some((v) => v !== '')

  // Chargement dynamique à l'approche de la sentinelle.
  const { hasNextPage, isFetchingNextPage, fetchNextPage } = query
  const sentinelRef = useRef(null)
  useEffect(() => {
    const el = sentinelRef.current
    if (!el) return
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) fetchNextPage()
      },
      { rootMargin: '250px' }
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [hasNextPage, isFetchingNextPage, fetchNextPage])

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-content-2">
        {count} transfert{count > 1 ? 's' : ''}{hasActiveFilters ? ' (filtrés)' : ''}
      </p>

      {/* Filtres */}
      <Card bodyClassName="p-3 sm:p-4">
        <div className="flex flex-col gap-3">
          <div className="relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-content-3 pointer-events-none" />
            <input
              type="text"
              value={filters.search}
              onChange={(e) => set('search', e.target.value)}
              placeholder="Rechercher (compte, notes)…"
              className="w-full h-11 lg:h-10 pl-9 pr-3 rounded-lg border border-border-app bg-surface text-sm text-content outline-none focus:border-purple-600"
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <Select
              label="Compte source" value={filters.compte_source}
              onChange={(v) => set('compte_source', v)}
              options={comptesOpts} placeholder="Tous les comptes"
            />
            <Select
              label="Compte destination" value={filters.compte_destination}
              onChange={(v) => set('compte_destination', v)}
              options={comptesOpts} placeholder="Tous les comptes"
            />
            <Select
              label="Statut" value={filters.est_definitif}
              onChange={(v) => set('est_definitif', v)}
              options={[
                { value: 'true', label: 'Validé' },
                { value: 'false', label: 'Prévisionnel' },
              ]}
              placeholder="Tous les statuts"
            />
            <Input label="Du" type="date" value={filters.date_min} onChange={(v) => set('date_min', v)} />
            <Input label="Au" type="date" value={filters.date_max} onChange={(v) => set('date_max', v)} />
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

      {query.isLoading && <Loading message="Chargement des transferts..." />}
      {query.isError && <ErrorState message="Impossible de charger les transferts." onRetry={query.refetch} />}

      {!query.isLoading && !query.isError && transferts.length === 0 && (
        <EmptyState
          Icon={Repeat}
          message={hasActiveFilters ? 'Aucun transfert ne correspond aux filtres.' : 'Aucun transfert enregistré.'}
          action={
            hasActiveFilters
              ? <Button variant="secondary" onClick={reset}>Réinitialiser</Button>
              : <Button variant="primary" onClick={onCreate}>Créer un transfert</Button>
          }
        />
      )}

      {!query.isLoading && !query.isError && transferts.length > 0 && (
        isMobile
          ? <TransfertsCards transferts={transferts} />
          : <TransfertsTable transferts={transferts} />
      )}

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
    </div>
  )
}

function StatutBadge({ t }) {
  return t.est_definitif
    ? <Badge variant="success">Validé</Badge>
    : <Badge variant="neutre">Prévisionnel</Badge>
}

function DeleteBtn({ t, inline = false }) {
  const deleteTransfert = useDeleteResource('transferts')
  const handleDelete = () => {
    if (!window.confirm('Annuler ce transfert ? Les deux flux liés seront supprimés.')) return
    deleteTransfert.mutate(t.id)
  }
  return (
    <button
      onClick={handleDelete}
      title="Annuler le transfert"
      disabled={deleteTransfert.isPending}
      className={`p-1.5 rounded-md text-content-2 hover:text-red-texte hover:bg-red-50 cursor-pointer disabled:opacity-50 shrink-0 ${inline ? '' : ''}`}
    >
      <Trash2 size={13} />
    </button>
  )
}

function TransfertsTable({ transferts }) {
  return (
    <Card bodyClassName="p-0">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-border-app">
            <th className="text-left px-4 py-3 text-xs font-medium text-content-2">Date</th>
            <th className="text-left px-4 py-3 text-xs font-medium text-content-2">Source</th>
            <th className="px-2 py-3"></th>
            <th className="text-left px-4 py-3 text-xs font-medium text-content-2">Destination</th>
            <th className="text-left px-4 py-3 text-xs font-medium text-content-2">Statut</th>
            <th className="text-right px-4 py-3 text-xs font-medium text-content-2">Montant</th>
            <th className="px-4 py-3 w-12"></th>
          </tr>
        </thead>
        <tbody>
          {transferts.map((t) => (
            <tr key={t.id} className="border-b border-border-app last:border-b-0 group">
              <td className="px-4 py-3 text-content whitespace-nowrap">{formatDate(t.date_flux)}</td>
              <td className="px-4 py-3 text-content">{t.compte_source_nom}</td>
              <td className="px-2 py-3"><ArrowRight size={14} className="text-content-3" /></td>
              <td className="px-4 py-3 text-content">{t.compte_destination_nom}</td>
              <td className="px-4 py-3"><StatutBadge t={t} /></td>
              <td className="px-4 py-3 text-right font-medium text-content tabular-nums">{formatEuro(t.montant)}</td>
              <td className="px-4 py-3">
                <div className="actions-ligne flex justify-end">
                  <DeleteBtn t={t} inline />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}

function TransfertsCards({ transferts }) {
  return (
    <div className="flex flex-col gap-2">
      {transferts.map((t) => (
        <Card key={t.id} bodyClassName="px-4 py-3.5">
          <div className="flex items-start gap-2.5">
            <IconBadge Icon={Repeat} size={16} className="w-9 h-9 shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5 text-sm font-medium text-content">
                <span className="truncate">{t.compte_source_nom}</span>
                <ArrowRight size={13} className="text-content-3 shrink-0" />
                <span className="truncate">{t.compte_destination_nom}</span>
              </div>
              <div className="text-xs text-content-2 mt-0.5 flex items-center gap-1.5">
                {formatDate(t.date_flux)} <StatutBadge t={t} />
              </div>
              {t.notes && <div className="text-xs text-content-2 mt-1 truncate">{t.notes}</div>}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-base font-medium text-content tabular-nums">{formatEuro(t.montant)}</span>
              <DeleteBtn t={t} />
            </div>
          </div>
        </Card>
      ))}
    </div>
  )
}

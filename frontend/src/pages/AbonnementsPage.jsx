import { useState, useEffect, useMemo } from 'react'
import {
  useResourceList,
  useResourceAction,
  useDeleteResource,
  useCategories,
} from '../hooks/useResource'
import { useFrequences, useStatutsFlux } from '../hooks/useReferentiels'
import useDebouncedValue from '../hooks/useDebouncedValue'
import { formatEuro } from '../utils/format'
import { Pencil, Trash2, FilePlus, Search, RefreshCw } from 'lucide-react'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import Select from '../components/ui/Select'
import Tooltip from '../components/ui/Tooltip'
import { DEFINITIONS } from '../constants/definitions'
import { Loading, ErrorState, EmptyState } from '../components/ui/States'
import AbonnementFormModal from '../components/abonnements/AbonnementFormModal'
import AbonnementsAnalyse from '../components/abonnements/AbonnementsAnalyse'
import FluxFormModal from '../components/flux/FluxFormModal'
import Metric, { MetricRow } from '../components/ui/Metric'

function echeanceISO(jour) {
  const d = new Date()
  if (jour) {
    const dernier = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate()
    d.setDate(Math.min(jour, dernier))
  }
  return d.toISOString().slice(0, 10)
}

const FILTRES_INITIAUX = { search: '', compte: 'tous', categorie: 'tous', frequence: 'tous', actif: 'tous' }

export default function AbonnementsPage() {
  const [tab, setTab] = useState('liste')
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedAbonnement, setSelectedAbonnement] = useState(null)
  const [generateFor, setGenerateFor] = useState(null)
  const [filtres, setFiltres] = useState(FILTRES_INITIAUX)

  const debouncedSearch = useDebouncedValue(filtres.search, 350)

  // Détecte les abonnements « en retard » à l'ouverture (miroir patrimoine).
  const verifierEcheances = useResourceAction('abonnements')
  useEffect(() => {
    verifierEcheances.mutate({ action: 'verifier-echeances' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const params = useMemo(() => {
    const p = {}
    if (debouncedSearch) p.search = debouncedSearch
    if (filtres.compte !== 'tous') p.compte = filtres.compte
    if (filtres.categorie !== 'tous') p.categorie = filtres.categorie
    if (filtres.frequence !== 'tous') p.frequence = filtres.frequence
    if (filtres.actif !== 'tous') p.actif = filtres.actif
    return p
  }, [debouncedSearch, filtres])

  const { data, isLoading, isError, refetch } = useResourceList('abonnements', params)
  const abonnements = data?.results ?? []

  const { data: comptesData } = useResourceList('comptes')
  const { data: categoriesData } = useCategories()
  const { options: frequencesOpts } = useFrequences()
  const { data: statutsData } = useStatutsFlux()

  const statutDefinitifId =
    (statutsData ?? []).find((s) => s.est_definitif)?.id ??
    (statutsData ?? [])[0]?.id ??
    null

  const comptesOpts = [
    { value: 'tous', label: 'Tous les comptes' },
    ...(comptesData?.results ?? []).map((c) => ({
      value: String(c.id),
      label: (c.etablissement_libelle ? `${c.nom} — ${c.etablissement_libelle}` : c.nom) + (c.est_commun ? ' · Commun' : ''),
    })),
  ]

  const allCats = categoriesData?.results ?? []
  const majeures = allCats.filter((c) => c.est_racine)
  const mineures = allCats.filter((c) => !c.est_racine)
  const categoriesOpts = [
    { value: 'tous', label: 'Toutes les catégories' },
    ...majeures
      .filter((maj) => !mineures.some((m) => String(m.parent) === String(maj.id)))
      .map((maj) => ({ value: String(maj.id), label: maj.nom })),
  ]
  const categoriesGroups = majeures
    .filter((maj) => mineures.some((m) => String(m.parent) === String(maj.id)))
    .map((maj) => ({
      label: maj.nom,
      options: mineures
        .filter((m) => String(m.parent) === String(maj.id))
        .map((m) => ({ value: String(m.id), label: m.nom })),
    }))

  const actifs = abonnements.filter((a) => a.actif)
  const enRetard = abonnements.filter((a) => a.est_en_retard).length
  const totalMensuel = actifs.reduce((s, a) => {
    const jours = a.frequence_nb_jours || 30
    return s + (Math.abs(Number(a.montant_attendu)) * 30) / jours
  }, 0)

  const openCreate = () => { setSelectedAbonnement(null); setModalOpen(true) }
  const openEdit = (ab) => { setSelectedAbonnement(ab); setModalOpen(true) }
  const closeModal = () => { setModalOpen(false); setSelectedAbonnement(null) }

  const generateInitial = generateFor && {
    montant: generateFor.montant_attendu,
    libelle: generateFor.nom,
    compte: generateFor.compte,
    categorie: generateFor.categorie,
    date_flux: echeanceISO(generateFor.jour_echeance),
    mode_paiement: generateFor.mode_paiement,
    statut: statutDefinitifId,
    abonnement: generateFor.id,
  }

  const setFiltre = (cle, valeur) => setFiltres((f) => ({ ...f, [cle]: valeur }))
  const filtresActifs =
    filtres.search || filtres.compte !== 'tous' || filtres.categorie !== 'tous' ||
    filtres.frequence !== 'tous' || filtres.actif !== 'tous'

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-lg font-medium text-content">Abonnements</h1>
          <p className="text-sm text-content-2 mt-0.5">
            Référentiel de vos prélèvements récurrents · générez le flux à chaque échéance
          </p>
        </div>
        <Button variant="primary" onClick={openCreate}>
          + Nouvel abonnement
        </Button>
      </div>

      <div className="flex gap-1 border-b border-border-app">
        <TabBtn active={tab === 'liste'} onClick={() => setTab('liste')}>Liste</TabBtn>
        <TabBtn active={tab === 'analyse'} onClick={() => setTab('analyse')}>Analyse</TabBtn>
      </div>

      {tab === 'analyse' ? (
        <AbonnementsAnalyse />
      ) : (
      <>
      <MetricRow colonnes={3}>
        <Metric label="Total mensuel estimé" value={formatEuro(-totalMensuel)} def={DEFINITIONS.abo_total_mensuel} />
        <Metric label="Abonnements actifs" value={String(actifs.length)} />
        <Metric
          label="En retard"
          value={String(enRetard)}
          valueClass={enRetard > 0 ? 'text-amber-texte' : 'text-content'}
          def={DEFINITIONS.abo_en_retard}
          defAlign="right"
        />
      </MetricRow>

      {/* Filtres */}
      <Card>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5">
          <div className="lg:col-span-1 relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-content-3 pointer-events-none" />
            <input
              type="text"
              value={filtres.search}
              onChange={(e) => setFiltre('search', e.target.value)}
              placeholder="Rechercher..."
              className="w-full h-11 lg:h-10 pl-9 pr-3 rounded-lg border border-border-app bg-surface text-sm text-content outline-none focus:border-purple-600"
            />
          </div>
          <Select value={filtres.compte} onChange={(v) => setFiltre('compte', v)} options={comptesOpts} />
          <Select value={filtres.categorie} onChange={(v) => setFiltre('categorie', v)} options={categoriesOpts} groups={categoriesGroups} />
          <Select value={filtres.frequence} onChange={(v) => setFiltre('frequence', v)} options={[{ value: 'tous', label: 'Toutes les fréquences' }, ...frequencesOpts]} />
          <Select value={filtres.actif} onChange={(v) => setFiltre('actif', v)} options={[{ value: 'tous', label: 'Tous les états' }, { value: 'true', label: 'Actifs' }, { value: 'false', label: 'Inactifs' }]} />
        </div>
        {filtresActifs && (
          <div className="mt-2.5">
            <button
              onClick={() => setFiltres(FILTRES_INITIAUX)}
              className="text-xs text-content-2 hover:text-content cursor-pointer bg-transparent border-none"
            >
              Réinitialiser les filtres
            </button>
          </div>
        )}
      </Card>

      {isLoading && <Loading message="Chargement des abonnements..." />}
      {isError && <ErrorState message="Impossible de charger les abonnements." onRetry={refetch} />}

      {!isLoading && !isError && (
        abonnements.length === 0 ? (
          <EmptyState
            Icon={RefreshCw}
            message={filtresActifs ? 'Aucun abonnement ne correspond aux filtres.' : 'Aucun abonnement enregistré.'}
            action={
              !filtresActifs && (
                <Button variant="primary" onClick={openCreate}>
                  Ajouter un abonnement
                </Button>
              )
            }
          />
        ) : (
          <AbonnementsTable
            abonnements={abonnements}
            onEdit={openEdit}
            onGenerate={setGenerateFor}
          />
        )
      )}
      </>
      )}

      <AbonnementFormModal isOpen={modalOpen} onClose={closeModal} abonnement={selectedAbonnement} />
      <FluxFormModal
        isOpen={!!generateFor}
        onClose={() => setGenerateFor(null)}
        initialValues={generateInitial}
      />
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


function StatutBadge({ abonnement }) {
  if (!abonnement.actif) return <Badge variant="neutre">Inactif</Badge>
  if (abonnement.materialise_ce_mois) return <Badge variant="success">✓ Généré ce mois</Badge>
  if (abonnement.est_en_retard) return <Badge variant="avertissement">⚠ En retard</Badge>
  return <Badge variant="neutre">À générer</Badge>
}

function AbonnementsTable({ abonnements, onEdit, onGenerate }) {
  return (
    <>
      {/* Desktop */}
      <div className="hidden lg:block overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-content-2 border-b border-border-app">
              <th className="py-2 pr-3 font-medium">Nom</th>
              <th className="py-2 pr-3 font-medium">Compte</th>
              <th className="py-2 pr-3 font-medium">Catégorie</th>
              <th className="py-2 pr-3 font-medium text-right">Montant</th>
              <th className="py-2 pr-3 font-medium">Fréquence</th>
              <th className="py-2 pr-3 font-medium text-center">Échéance</th>
              <th className="py-2 pr-3 font-medium">Statut</th>
              <th className="py-2 pl-3 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {abonnements.map((ab) => (
              <tr key={ab.id} className="border-b border-border-app/60 hover:bg-surface-3/50 group">
                <td className="py-2.5 pr-3 text-content font-medium">{ab.nom}</td>
                <td className="py-2.5 pr-3 text-content-2">{ab.compte_nom || '—'}</td>
                <td className="py-2.5 pr-3 text-content-2">{ab.categorie_nom || '—'}</td>
                <td className="py-2.5 pr-3 text-right tabular-nums text-content">{formatEuro(ab.montant_attendu)}</td>
                <td className="py-2.5 pr-3 text-content-2">{ab.frequence_libelle}</td>
                <td className="py-2.5 pr-3 text-center text-content-2">{ab.jour_echeance || '—'}</td>
                <td className="py-2.5 pr-3"><StatutBadge abonnement={ab} /></td>
                <td className="py-2.5 pl-3">
                  <RowActions ab={ab} onEdit={onEdit} onGenerate={onGenerate} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile */}
      <div className="lg:hidden flex flex-col gap-2.5">
        {abonnements.map((ab) => (
          <Card key={ab.id}>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="text-sm font-medium text-content truncate">{ab.nom}</div>
                <div className="text-xs text-content-2">{ab.categorie_nom || '—'} · {ab.compte_nom || '—'}</div>
              </div>
              <div className="text-sm font-medium text-content tabular-nums shrink-0">
                {formatEuro(ab.montant_attendu)}
              </div>
            </div>
            <div className="text-xs text-content-2 mt-1">
              {ab.frequence_libelle}{ab.jour_echeance ? ` · échéance le ${ab.jour_echeance}` : ''}
            </div>
            <div className="flex items-center justify-between mt-3 pt-3 border-t border-border-app">
              <StatutBadge abonnement={ab} />
              <RowActions ab={ab} onEdit={onEdit} onGenerate={onGenerate} showLabels />
            </div>
          </Card>
        ))}
      </div>
    </>
  )
}

function RowActions({ ab, onEdit, onGenerate, showLabels = false }) {
  const deleteAbonnement = useDeleteResource('abonnements')

  const handleDelete = () => {
    if (!window.confirm(`Supprimer l'abonnement « ${ab.nom} » ?`)) return
    deleteAbonnement.mutate(ab.id)
  }

  const genererDesactive = !ab.actif || ab.materialise_ce_mois
  const genererTitle = !ab.actif
    ? 'Abonnement inactif'
    : ab.materialise_ce_mois
      ? 'Déjà généré ce mois'
      : 'Générer le flux du mois'

  return (
    <div className={`flex gap-1 justify-end ${showLabels ? '' : 'actions-ligne'}`}>
      <button
        onClick={() => onGenerate(ab)}
        disabled={genererDesactive}
        title={genererTitle}
        className="p-1.5 rounded-md text-purple-texte hover:bg-purple-50 dark:hover:bg-purple-950/40 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
      >
        <FilePlus size={15} />
      </button>
      <button
        onClick={() => onEdit(ab)}
        title="Modifier"
        className="p-1.5 rounded-md text-content-2 hover:text-content hover:bg-surface-3 cursor-pointer"
      >
        <Pencil size={14} />
      </button>
      <button
        onClick={handleDelete}
        title="Supprimer"
        disabled={deleteAbonnement.isPending}
        className="p-1.5 rounded-md text-content-2 hover:text-red-texte hover:bg-red-50 cursor-pointer disabled:opacity-50"
      >
        <Trash2 size={14} />
      </button>
    </div>
  )
}

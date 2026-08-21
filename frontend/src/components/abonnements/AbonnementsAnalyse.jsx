import { useState, useMemo } from 'react'
import useAbonnementsAnalyse from '../../hooks/useAbonnementsAnalyse'
import { useResourceList } from '../../hooks/useResource'
import { formatEuro, formatDate, formatPercent } from '../../utils/format'
import { DEFINITIONS } from '../../constants/definitions'
import Card from '../ui/Card'
import Badge from '../ui/Badge'
import Tooltip from '../ui/Tooltip'
import Modal from '../ui/Modal'
import PeriodSelector from '../ui/PeriodSelector'
import { Loading, ErrorState, EmptyState } from '../ui/States'
import BarChart from '../charts/BarChart'
import { usePaletteDonnees } from '../charts/paletteDonnees'
import AbonnementFormModal from './AbonnementFormModal'
import {
  AlertTriangle, TrendingUp, CheckCircle2, Pencil, ChevronRight,
  Users, Tag, LayoutGrid, ChartColumn
} from 'lucide-react'

const RAISON_LABEL = {
  en_retard: { label: 'En retard', variant: 'avertissement' },
  divergence_montant: { label: 'Montant divergent', variant: 'critique' },
  jamais_genere: { label: 'Jamais généré', variant: 'neutre' },
}

// Stats communes d'un bucket (personne / catégorie / global) pour l'en-tête du modal.
function statsOf(bucket, nbKey = 'nb') {
  return [
    { label: 'Mensuel', value: formatEuro(bucket.total_mensuel) },
    { label: 'Annuel', value: formatEuro(bucket.total_annuel) },
    { label: 'Nombre', value: String(bucket[nbKey]) },
  ]
}

// Petit libellé de fiabilité (estimatif = référentiel, réel = flux générés).
function FiabiliteTag({ value }) {
  const map = {
    estimatif: { txt: 'estimatif', cls: 'text-content-3' },
    reel: { txt: 'réel', cls: 'text-teal-texte dark:text-teal-400' },
  }
  const f = map[value] || map.estimatif
  return <span className={`text-[11px] uppercase tracking-wide ${f.cls}`}>{f.txt}</span>
}

function SectionTitle({ children, def, fiabilite }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <h2 className="text-sm font-medium text-content flex items-center gap-1">
        {children}
        {def && <Tooltip {...def} />}
      </h2>
      {fiabilite && <FiabiliteTag value={fiabilite} />}
    </div>
  )
}

function EditBtn({ onClick, title = 'Modifier (changer de compte, résilier…)' }) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="p-1.5 rounded-md text-content-2 hover:text-content hover:bg-surface-3 cursor-pointer shrink-0"
    >
      <Pencil size={14} />
    </button>
  )
}

export default function AbonnementsAnalyse() {
  const [nbMois, setNbMois] = useState(6)
  const { data, isLoading, isError, refetch } = useAbonnementsAnalyse(nbMois)

  // Un seul modal de détail (config-driven) + le modal d'édition d'un abo.
  const [detail, setDetail] = useState(null)
  const [editAbo, setEditAbo] = useState(null)
  const { data: abosData } = useResourceList('abonnements', { page_size: 1000 })
  const abosById = useMemo(() => {
    const map = {}
    for (const a of abosData?.results ?? []) map[a.id] = a
    return map
  }, [abosData])

  const handleEdit = (id) => {
    const full = abosById[id]
    if (full) { setDetail(null); setEditAbo(full) }
  }

  const openTitulaire = (b) => setDetail({
    title: `Abonnements — ${b.nom}`,
    icon: Users,
    badge: b.est_commun ? <Badge variant="info">Commun</Badge> : null,
    hint: b.est_commun
      ? null
      : 'Ces abonnements sont prélevés sur des comptes personnels. Pour en basculer un sur un compte commun, éditez-le et changez le compte.',
    stats: statsOf(b),
    items: b.abonnements,
  })

  const openCategorie = (c) => setDetail({
    title: `Abonnements — ${c.nom}`,
    icon: Tag,
    hint: 'Détail des abonnements de cette catégorie — repérez lesquels résilier.',
    stats: statsOf(c),
    items: c.abonnements,
  })

  const openTous = (synthese) => setDetail({
    title: 'Tous les abonnements',
    icon: LayoutGrid,
    hint: 'Vue complète, triée par coût — le haut de la liste est le plus « rentable » à résilier.',
    stats: [
      { label: 'Mensuel', value: formatEuro(synthese.total_mensuel) },
      { label: 'Annuel', value: formatEuro(synthese.total_annuel) },
      { label: 'Nombre', value: String(synthese.nb_recurrents) },
    ],
    items: synthese.abonnements,
  })

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-content-2">
          Où partent vos prélèvements récurrents, ramenés au mois et à l'année.
        </p>
        <div className="flex items-center gap-2">
          <span className="text-xs text-content-3">Poids sur</span>
          <PeriodSelector value={nbMois} onChange={setNbMois} />
        </div>
      </div>

      {isLoading && <Loading message="Chargement de l'analyse..." />}
      {isError && <ErrorState message="Impossible de charger l'analyse." onRetry={refetch} />}

      {!isLoading && !isError && data && (
        data.synthese.nb_actifs === 0 ? (
          <EmptyState Icon={ChartColumn} message="Aucun abonnement actif à analyser pour l'instant." />
        ) : (
          <>
            <Synthese synthese={data.synthese} onOpenAll={openTous} onEdit={handleEdit} />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <ParCategorie bloc={data.par_categorie} onSelect={openCategorie} />
              <ParTitulaire bloc={data.par_titulaire} onSelect={openTitulaire} />
            </div>
            <DerivePrix bloc={data.derive_prix} onEdit={handleEdit} />
            <ARisque bloc={data.a_risque} onEdit={handleEdit} />
          </>
        )
      )}

      <AbonnementsDetailModal detail={detail} onClose={() => setDetail(null)} onEdit={handleEdit} />
      <AbonnementFormModal isOpen={!!editAbo} onClose={() => setEditAbo(null)} abonnement={editAbo} />
    </div>
  )
}

// -------------------------------------------------------------------------
// Modal générique : détail d'un agrégat (liste d'abonnements) + édition
// -------------------------------------------------------------------------
function AboLine({ a, onEdit }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2.5">
      <div className="min-w-0">
        <div className="text-sm text-content truncate">{a.nom}</div>
        <div className="text-xs text-content-3 truncate">
          {a.categorie_nom || 'Sans catégorie'} · {a.compte_nom}{a.compte_est_commun ? ' · Commun' : ''} · {a.frequence_libelle}
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <div className="text-right">
          <div className="text-sm text-content tabular-nums">{formatEuro(a.cout_mensuel)}<span className="text-content-3">/mois</span></div>
          <div className="text-xs text-content-3 tabular-nums">{formatEuro(a.cout_annuel)}/an</div>
        </div>
        <EditBtn onClick={() => onEdit(a.id)} />
      </div>
    </div>
  )
}

function AbonnementsDetailModal({ detail, onClose, onEdit }) {
  if (!detail) return null
  const { title, icon: Icon, badge, hint, stats, items = [] } = detail

  return (
    <Modal
      isOpen={!!detail}
      onClose={onClose}
      title={
        <span className="flex items-center gap-2">
          {Icon && <Icon size={16} className="text-content-2" />}
          {title}
          {badge}
        </span>
      }
    >
      <div className="flex flex-col gap-3">
        {stats && (
          <div className="flex gap-4 text-sm flex-wrap">
            {stats.map((s) => (
              <div key={s.label}>
                <span className="text-content-3">{s.label} </span>
                <span className="text-content tabular-nums">{s.value}</span>
              </div>
            ))}
          </div>
        )}
        {hint && (
          <p className="text-xs text-content-2 bg-surface-3 rounded-lg px-3 py-2">{hint}</p>
        )}
        <div className="flex flex-col divide-y divide-border-app/60 max-h-96 overflow-y-auto">
          {items.map((a) => <AboLine key={a.id} a={a} onEdit={onEdit} />)}
        </div>
      </div>
    </Modal>
  )
}

// -------------------------------------------------------------------------
// Synthèse : coût mensuel/annuel + poids + top abonnements
// -------------------------------------------------------------------------
function Synthese({ synthese, onOpenAll, onEdit }) {
  const tiles = [
    { label: 'Total mensuel', value: formatEuro(synthese.total_mensuel), def: DEFINITIONS.abo_total_mensuel },
    { label: 'Total annuel', value: formatEuro(synthese.total_annuel), def: DEFINITIONS.abo_total_annuel },
    { label: 'Poids sur dépenses', value: formatPercent(synthese.poids_depenses_pct), def: DEFINITIONS.abo_poids_depenses },
    { label: 'Poids sur revenus', value: formatPercent(synthese.poids_revenus_pct), def: DEFINITIONS.abo_poids_revenus },
  ]
  const top = synthese.abonnements.slice(0, 8)
  const reste = synthese.nb_recurrents - top.length

  return (
    <Card>
      <SectionTitle fiabilite="estimatif">Synthèse</SectionTitle>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5 mb-4">
        {tiles.map((t) => (
          <div key={t.label} className="bg-surface-3 rounded-lg px-4 py-3.5">
            <div className="text-xs text-content-2 mb-1 flex items-center gap-1">
              {t.label}
              {t.def && <Tooltip {...t.def} />}
            </div>
            <div className="text-xl font-medium text-content tabular-nums">{t.value}</div>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-content-2">
          Vos plus gros abonnements ({synthese.nb_recurrents} récurrents)
        </span>
        <button
          onClick={() => onOpenAll(synthese)}
          className="text-xs text-purple-texte hover:underline cursor-pointer"
        >
          Tout voir
        </button>
      </div>
      <div className="flex flex-col divide-y divide-border-app/60">
        {top.map((a) => (
          <div key={a.id} className="flex items-center justify-between py-2 gap-3">
            <div className="min-w-0">
              <div className="text-sm text-content truncate">{a.nom}</div>
              <div className="text-xs text-content-3 truncate">{a.categorie_nom || 'Sans catégorie'} · {a.compte_nom} · {a.frequence_libelle}</div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <div className="text-right">
                <div className="text-sm text-content tabular-nums">{formatEuro(a.cout_mensuel)}<span className="text-content-3">/mois</span></div>
                <div className="text-xs text-content-3 tabular-nums">{formatEuro(a.cout_annuel)}/an</div>
              </div>
              <EditBtn onClick={() => onEdit(a.id)} />
            </div>
          </div>
        ))}
      </div>
      {reste > 0 && (
        <button
          onClick={() => onOpenAll(synthese)}
          className="text-xs text-content-2 hover:text-content mt-2 cursor-pointer"
        >
          + {reste} autre{reste > 1 ? 's' : ''}…
        </button>
      )}
    </Card>
  )
}

// -------------------------------------------------------------------------
// Répartition par catégorie (chaque catégorie = agrégat cliquable)
// -------------------------------------------------------------------------
function ParCategorie({ bloc, onSelect }) {
  const { couleurDe } = usePaletteDonnees(
    (bloc?.par_categorie ?? []).map((r) => r.id)
  )
  const rows = bloc.par_categorie
  return (
    <Card>
      <SectionTitle def={DEFINITIONS.abo_par_categorie} fiabilite="estimatif">
        Par catégorie
      </SectionTitle>
      {rows.length === 0 ? (
        <p className="text-sm text-content-3">Aucune donnée.</p>
      ) : (
        <>
          <BarChart
            labels={rows.map((r) => r.nom)}
            datasets={[{
              label: 'Coût mensuel',
              data: rows.map((r) => Number(r.total_mensuel)),
              color: rows.map((r) => couleurDe(r.id)),
            }]}
            height={200}
          />
          <div className="flex flex-col gap-1 mt-3">
            {rows.map((r) => (
              <button
                key={r.id}
                onClick={() => onSelect(r)}
                className="text-left w-full flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-surface-3 cursor-pointer group"
              >
                <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: couleurDe(r.id) }} />
                <div className="flex-1 min-w-0">
                  <div className="flex justify-between text-sm">
                    <span className="text-content truncate">{r.nom} <span className="text-content-3">· {r.nb}</span></span>
                    <span className="text-content tabular-nums">{formatEuro(r.total_mensuel)}<span className="text-content-3">/mois</span></span>
                  </div>
                  <div className="h-1 rounded-full bg-surface-3 mt-1 overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${r.part_pct}%`, background: couleurDe(r.id) }} />
                  </div>
                </div>
                <span className="text-xs text-content-3 tabular-nums w-12 text-right">{formatPercent(r.part_pct)}</span>
                <ChevronRight size={15} className="text-content-3 group-hover:text-content-2 shrink-0" />
              </button>
            ))}
          </div>
        </>
      )}
    </Card>
  )
}

// -------------------------------------------------------------------------
// Qui paye quoi (chaque personne = agrégat cliquable)
// -------------------------------------------------------------------------
function ParTitulaire({ bloc, onSelect }) {
  const rows = bloc.par_titulaire
  return (
    <Card>
      <SectionTitle def={DEFINITIONS.abo_par_titulaire} fiabilite="estimatif">
        Qui paye quoi
      </SectionTitle>
      {rows.length === 0 ? (
        <p className="text-sm text-content-3">Aucune donnée.</p>
      ) : (
        <div className="flex flex-col gap-1">
          {rows.map((r) => (
            <button
              key={r.id}
              onClick={() => onSelect(r)}
              className="text-left w-full rounded-lg px-2 py-2 hover:bg-surface-3 cursor-pointer group"
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-sm text-content truncate">{r.nom}</span>
                  {r.est_commun && <Badge variant="info">Commun</Badge>}
                  <span className="text-xs text-content-3">· {r.nb} abo</span>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <span className="text-sm text-content tabular-nums">{formatEuro(r.total_mensuel)}<span className="text-content-3">/mois</span></span>
                  <ChevronRight size={15} className="text-content-3 group-hover:text-content-2" />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-1.5 rounded-full bg-surface-3 overflow-hidden">
                  <div className={`h-full rounded-full ${r.est_commun ? 'bg-violet-500' : 'bg-purple-500'}`} style={{ width: `${r.part_pct}%` }} />
                </div>
                <span className="text-xs text-content-3 tabular-nums w-12 text-right">{formatPercent(r.part_pct)}</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </Card>
  )
}

// -------------------------------------------------------------------------
// Dérive de prix (réel) — 1 ligne = 1 abo, éditable
// -------------------------------------------------------------------------
function DerivePrix({ bloc, onEdit }) {
  const rows = bloc.par_abonnement
  return (
    <Card>
      <SectionTitle def={DEFINITIONS.abo_derive_prix} fiabilite="reel">
        <TrendingUp size={15} className="text-content-2" /> Dérive de prix
      </SectionTitle>
      {rows.length === 0 ? (
        <p className="text-sm text-content-3">
          Aucun flux généré pour l'instant : générez les prélèvements depuis l'onglet Liste pour comparer le réel au montant attendu.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-content-2 border-b border-border-app">
                <th className="py-2 pr-3 font-medium">Abonnement</th>
                <th className="py-2 pr-3 font-medium text-right">Attendu</th>
                <th className="py-2 pr-3 font-medium text-right">Dernier réel</th>
                <th className="py-2 pr-3 font-medium text-center">Le</th>
                <th className="py-2 pr-3 font-medium text-right">Écart</th>
                <th className="py-2 pl-3 font-medium text-right"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-border-app/60">
                  <td className="py-2 pr-3 text-content">{r.nom}</td>
                  <td className="py-2 pr-3 text-right tabular-nums text-content-2">{formatEuro(r.montant_attendu)}</td>
                  <td className="py-2 pr-3 text-right tabular-nums text-content">{formatEuro(r.dernier_montant_reel)}</td>
                  <td className="py-2 pr-3 text-center text-content-3 text-xs">{formatDate(r.dernier_date)}</td>
                  <td className="py-2 pr-3 text-right">
                    <EcartChip ecart={r.ecart_pct} divergence={r.en_divergence} />
                  </td>
                  <td className="py-2 pl-3 text-right">
                    <EditBtn onClick={() => onEdit(r.id)} title="Modifier l'abonnement" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

function EcartChip({ ecart, divergence }) {
  if (ecart === null || ecart === undefined) return <span className="text-content-3">—</span>
  const n = Number(ecart)
  const signe = n > 0 ? '+' : ''
  const cls = divergence
    ? 'text-red-texte dark:text-red-400 font-medium'
    : n === 0 ? 'text-content-3' : 'text-content-2'
  return <span className={`tabular-nums text-sm ${cls}`}>{signe}{formatPercent(n)}</span>
}

// -------------------------------------------------------------------------
// À surveiller — 1 ligne = 1 abo, éditable
// -------------------------------------------------------------------------
function ARisque({ bloc, onEdit }) {
  const rows = bloc.a_risque
  return (
    <Card>
      <SectionTitle def={DEFINITIONS.abo_a_risque} fiabilite="reel">
        <AlertTriangle size={15} className="text-content-2" /> À surveiller
      </SectionTitle>
      {rows.length === 0 ? (
        <div className="flex items-center gap-2 text-sm text-content-2">
          <CheckCircle2 size={16} className="text-emerald-500" />
          Aucun abonnement à signaler — tout est à jour.
        </div>
      ) : (
        <div className="flex flex-col divide-y divide-border-app/60">
          {rows.map((r) => (
            <div key={r.id} className="flex items-center justify-between py-2.5 gap-3">
              <div className="min-w-0">
                <div className="text-sm text-content truncate">{r.nom}</div>
                <div className="flex flex-wrap gap-1 mt-1">
                  {r.raisons.map((raison) => {
                    const info = RAISON_LABEL[raison] || { label: raison, variant: 'neutre' }
                    return (
                      <Badge key={raison} variant={info.variant}>
                        {info.label}
                        {raison === 'divergence_montant' && r.ecart_pct != null
                          ? ` (${Number(r.ecart_pct) > 0 ? '+' : ''}${formatPercent(r.ecart_pct)})`
                          : ''}
                      </Badge>
                    )
                  })}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-sm text-content-2 tabular-nums">
                  {r.cout_mensuel != null ? `${formatEuro(r.cout_mensuel)}/mois` : formatEuro(r.montant_attendu)}
                </span>
                <EditBtn onClick={() => onEdit(r.id)} title="Modifier l'abonnement" />
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

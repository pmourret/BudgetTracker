import { useState } from 'react'
import useAbonnementsAnalyse from '../../hooks/useAbonnementsAnalyse'
import { formatEuro, formatDate, formatPercent } from '../../utils/format'
import { DEFINITIONS } from '../../constants/definitions'
import Card from '../ui/Card'
import Badge from '../ui/Badge'
import Tooltip from '../ui/Tooltip'
import PeriodSelector from '../ui/PeriodSelector'
import { Loading, ErrorState, EmptyState } from '../ui/States'
import BarChart from '../charts/BarChart'
import { CAT_PALETTE } from '../charts/DepensesCategories'
import { AlertTriangle, TrendingUp, CheckCircle2 } from 'lucide-react'

const RAISON_LABEL = {
  en_retard: { label: 'En retard', variant: 'avertissement' },
  divergence_montant: { label: 'Montant divergent', variant: 'critique' },
  jamais_genere: { label: 'Jamais généré', variant: 'neutre' },
}

// Petit libellé de fiabilité (estimatif = référentiel, réel = flux générés).
function FiabiliteTag({ value }) {
  const map = {
    estimatif: { txt: 'estimatif', cls: 'text-content-3' },
    reel: { txt: 'réel', cls: 'text-teal-600 dark:text-teal-400' },
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

export default function AbonnementsAnalyse() {
  const [nbMois, setNbMois] = useState(6)
  const { data, isLoading, isError, refetch } = useAbonnementsAnalyse(nbMois)

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
          <EmptyState icon="📊" message="Aucun abonnement actif à analyser pour l'instant." />
        ) : (
          <>
            <Synthese synthese={data.synthese} />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <ParCategorie bloc={data.par_categorie} />
              <ParTitulaire bloc={data.par_titulaire} />
            </div>
            <DerivePrix bloc={data.derive_prix} />
            <ARisque bloc={data.a_risque} />
          </>
        )
      )}
    </div>
  )
}

// -------------------------------------------------------------------------
// Synthèse : coût mensuel/annuel + poids + top abonnements
// -------------------------------------------------------------------------
function Synthese({ synthese }) {
  const tiles = [
    { label: 'Total mensuel', value: formatEuro(synthese.total_mensuel), def: DEFINITIONS.abo_total_mensuel },
    { label: 'Total annuel', value: formatEuro(synthese.total_annuel), def: DEFINITIONS.abo_total_annuel },
    { label: 'Poids sur dépenses', value: formatPercent(synthese.poids_depenses_pct), def: DEFINITIONS.abo_poids_depenses },
    { label: 'Poids sur revenus', value: formatPercent(synthese.poids_revenus_pct), def: DEFINITIONS.abo_poids_revenus },
  ]
  const top = synthese.abonnements.slice(0, 8)

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

      <div className="text-xs text-content-2 mb-2">
        Vos plus gros abonnements ({synthese.nb_recurrents} récurrents)
      </div>
      <div className="flex flex-col divide-y divide-border-app/60">
        {top.map((a) => (
          <div key={a.id} className="flex items-center justify-between py-2 gap-3">
            <div className="min-w-0">
              <div className="text-sm text-content truncate">{a.nom}</div>
              <div className="text-xs text-content-3">{a.frequence_libelle} · {a.compte_nom}</div>
            </div>
            <div className="text-right shrink-0">
              <div className="text-sm text-content tabular-nums">{formatEuro(a.cout_mensuel)}<span className="text-content-3">/mois</span></div>
              <div className="text-xs text-content-3 tabular-nums">{formatEuro(a.cout_annuel)}/an</div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}

// -------------------------------------------------------------------------
// Répartition par catégorie
// -------------------------------------------------------------------------
function ParCategorie({ bloc }) {
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
              color: rows.map((_, i) => CAT_PALETTE[i % CAT_PALETTE.length]),
            }]}
            height={200}
          />
          <div className="flex flex-col gap-2 mt-3">
            {rows.map((r, i) => (
              <div key={r.id} className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: CAT_PALETTE[i % CAT_PALETTE.length] }} />
                <div className="flex-1 min-w-0">
                  <div className="flex justify-between text-sm">
                    <span className="text-content truncate">{r.nom} <span className="text-content-3">· {r.nb}</span></span>
                    <span className="text-content tabular-nums">{formatEuro(r.total_mensuel)}<span className="text-content-3">/mois</span></span>
                  </div>
                  <div className="h-1 rounded-full bg-surface-3 mt-1 overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${r.part_pct}%`, background: CAT_PALETTE[i % CAT_PALETTE.length] }} />
                  </div>
                </div>
                <span className="text-xs text-content-3 tabular-nums w-12 text-right">{formatPercent(r.part_pct)}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </Card>
  )
}

// -------------------------------------------------------------------------
// Qui paye quoi (par titulaire)
// -------------------------------------------------------------------------
function ParTitulaire({ bloc }) {
  const rows = bloc.par_titulaire
  return (
    <Card>
      <SectionTitle def={DEFINITIONS.abo_par_titulaire} fiabilite="estimatif">
        Qui paye quoi
      </SectionTitle>
      {rows.length === 0 ? (
        <p className="text-sm text-content-3">Aucune donnée.</p>
      ) : (
        <div className="flex flex-col gap-3">
          {rows.map((r) => (
            <div key={r.id}>
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-sm text-content truncate">{r.nom}</span>
                  {r.est_commun && <Badge variant="info">Commun</Badge>}
                  <span className="text-xs text-content-3">· {r.nb} abo</span>
                </div>
                <div className="text-right shrink-0">
                  <span className="text-sm text-content tabular-nums">{formatEuro(r.total_mensuel)}<span className="text-content-3">/mois</span></span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-1.5 rounded-full bg-surface-3 overflow-hidden">
                  <div className={`h-full rounded-full ${r.est_commun ? 'bg-violet-500' : 'bg-purple-500'}`} style={{ width: `${r.part_pct}%` }} />
                </div>
                <span className="text-xs text-content-3 tabular-nums w-12 text-right">{formatPercent(r.part_pct)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

// -------------------------------------------------------------------------
// Dérive de prix (réel)
// -------------------------------------------------------------------------
function DerivePrix({ bloc }) {
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
                <th className="py-2 pl-3 font-medium text-right">Écart</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-border-app/60">
                  <td className="py-2 pr-3 text-content">{r.nom}</td>
                  <td className="py-2 pr-3 text-right tabular-nums text-content-2">{formatEuro(r.montant_attendu)}</td>
                  <td className="py-2 pr-3 text-right tabular-nums text-content">{formatEuro(r.dernier_montant_reel)}</td>
                  <td className="py-2 pr-3 text-center text-content-3 text-xs">{formatDate(r.dernier_date)}</td>
                  <td className="py-2 pl-3 text-right">
                    <EcartChip ecart={r.ecart_pct} divergence={r.en_divergence} />
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
    ? 'text-red-600 dark:text-red-400 font-medium'
    : n === 0 ? 'text-content-3' : 'text-content-2'
  return <span className={`tabular-nums text-sm ${cls}`}>{signe}{formatPercent(n)}</span>
}

// -------------------------------------------------------------------------
// À surveiller
// -------------------------------------------------------------------------
function ARisque({ bloc }) {
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
              <div className="text-right shrink-0 text-sm text-content-2 tabular-nums">
                {r.cout_mensuel != null ? `${formatEuro(r.cout_mensuel)}/mois` : formatEuro(r.montant_attendu)}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

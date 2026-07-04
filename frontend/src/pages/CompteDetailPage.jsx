import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Users } from 'lucide-react'
import apiClient from '../api/client'
import { formatEuro, formatDate } from '../utils/format'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Tooltip from '../components/ui/Tooltip'
import { DEFINITIONS } from '../constants/definitions'
import { Loading, ErrorState } from '../components/ui/States'
import BarChart from '../components/charts/BarChart'
import DepensesCategories, { CAT_PALETTE } from '../components/charts/DepensesCategories'
import FluxSearchPanel from '../components/flux/FluxSearchPanel'

function useCompteDashboard(id) {
  return useQuery({
    queryKey: ['analytics', 'compte', id],
    queryFn: async () => {
      const { data } = await apiClient.get(`/analytics/compte/${id}/`)
      return data
    },
    enabled: !!id,
  })
}

export default function CompteDetailPage() {
  const { id } = useParams()
  const { data, isLoading, isError, refetch } = useCompteDashboard(id)

  const compte = data?.compte
  const m = data?.metriques

  return (
    <div className="flex flex-col gap-4">
      <div>
        <Link
          to="/comptes"
          className="inline-flex items-center gap-1 text-sm text-content-2 hover:text-content mb-2"
        >
          <ArrowLeft size={14} /> Comptes
        </Link>
        <div className="flex items-center gap-2">
          <h1 className="text-lg font-medium text-content">
            {compte ? (compte.etablissement_libelle || compte.nom) : 'Compte'}
          </h1>
          {compte?.est_commun && (
            <Badge variant="purple">
              <span className="flex items-center gap-1"><Users size={11} /> Commun</span>
            </Badge>
          )}
          {compte && !compte.actif && (
            <span className="text-[11px] text-content-3 bg-surface-3 rounded px-2 py-0.5">
              Compte désactivé
            </span>
          )}
        </div>
        {compte && (
          <p className="text-sm text-content-2 mt-0.5">
            {compte.nom} · {compte.titulaire_libelle} · {compte.type_compte_libelle}
          </p>
        )}
      </div>

      {isLoading && <Loading message="Chargement du compte..." />}
      {isError && <ErrorState message="Impossible de charger ce compte." onRetry={refetch} />}

      {!isLoading && !isError && data && (
        <>
          {/* Soldes du compte */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
            <MetricCard label="Solde théorique" value={formatEuro(compte.solde_theorique)} def={DEFINITIONS.solde_theorique} />
            <MetricCard label="Solde confirmé" value={formatEuro(compte.solde_reel)} def={DEFINITIONS.solde_reel} />
            <MetricCard
              label="En attente"
              value={formatEuro(compte.ecart_solde)}
              valueClass={Number(compte.ecart_solde) > 0 ? 'text-amber-600' : 'text-teal-600'}
              def={DEFINITIONS.ecart_solde}
              defAlign="right"
            />
          </div>

          {/* Dépenses / revenus du mois */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5">
            <MetricCard label="Dépenses du mois" value={`−${formatEuro(m.depenses_mois)}`} valueClass="text-red-600" def={DEFINITIONS.depenses_mois} />
            <MetricCard label="Revenus du mois" value={`+${formatEuro(m.revenus_mois)}`} valueClass="text-teal-600" def={DEFINITIONS.revenus_mois} />
            <MetricCard
              label="Épargne nette"
              value={formatEuro(m.epargne_nette)}
              valueClass={Number(m.epargne_nette) >= 0 ? 'text-purple-400' : 'text-red-600'}
              def={DEFINITIONS.epargne_nette}
            />
            <MetricCard label="Mouvements" value={m.nb_flux} def={DEFINITIONS.compte_nb_flux} defAlign="right" />
          </div>

          {/* Dépenses par catégorie : histogramme + donut/légende */}
          <Card
            title={
              <span className="inline-flex items-center gap-1">
                Dépenses par catégorie
                <Tooltip {...DEFINITIONS.depenses_par_categorie} align="left" />
              </span>
            }
          >
            {data.depenses_par_categorie.length === 0 ? (
              <p className="text-sm text-content-3 py-4 text-center">
                Aucune dépense catégorisée ce mois.
              </p>
            ) : (
              <div className="flex flex-col gap-6">
                <BarChart
                  labels={data.depenses_par_categorie.map((c) => c.nom)}
                  datasets={[{
                    label: 'Dépenses',
                    data: data.depenses_par_categorie.map((c) => Number(c.total)),
                    color: data.depenses_par_categorie.map((_, i) => CAT_PALETTE[i % CAT_PALETTE.length]),
                  }]}
                  height={220}
                />
                <DepensesCategories
                  data={data.depenses_par_categorie}
                  mois={data.mois_courant}
                  compteId={id}
                />
              </div>
            )}
          </Card>

          {/* Top dépenses du mois */}
          <Card
            title={
              <span className="inline-flex items-center gap-1">
                Top dépenses du mois
                <Tooltip {...DEFINITIONS.compte_top_depenses} align="left" />
              </span>
            }
          >
            {data.top_depenses.length === 0 ? (
              <p className="text-sm text-content-3 py-4 text-center">
                Aucune dépense ce mois.
              </p>
            ) : (
              <div className="flex flex-col">
                {data.top_depenses.map((f) => (
                  <div key={f.id} className="flex justify-between items-center py-2 border-b border-border-app last:border-b-0">
                    <div className="min-w-0">
                      <div className="text-sm text-content truncate">{f.libelle || 'Sans libellé'}</div>
                      <div className="text-xs text-content-3">
                        {f.categorie_nom || '—'} · {formatDate(f.date_flux)}
                      </div>
                    </div>
                    <span className="text-sm font-medium text-red-600 shrink-0">
                      {formatEuro(f.montant)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Recherche + liste des flux du compte (édition possible) */}
          <div>
            <h2 className="text-sm font-medium text-content mb-2">Flux du compte</h2>
            <FluxSearchPanel baseParams={{ compte: id }} hideCompteFilter />
          </div>
        </>
      )}
    </div>
  )
}

function MetricCard({ label, value, valueClass = 'text-content', def, defAlign = 'left' }) {
  return (
    <div className="bg-surface border border-border-app rounded-xl px-4 py-3.5">
      <div className="text-xs text-content-2 mb-1 flex items-center gap-1">
        {label}
        {def && <Tooltip {...def} align={defAlign} />}
      </div>
      <div className={`text-xl font-medium ${valueClass}`}>{value}</div>
    </div>
  )
}

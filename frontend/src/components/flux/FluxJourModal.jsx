import { useResourceList } from '../../hooks/useResource'
import Modal from '../ui/Modal'
import { Loading, ErrorState } from '../ui/States'
import { formatEuro, formatDate } from '../../utils/format'

/**
 * Détail des dépenses d'un jour (drill-down de la heatmap « Calendrier des
 * dépenses »). Lecture seule.
 *
 * Réutilise l'endpoint /flux/ (filtres `date_min`=`date_max`=jour,
 * `est_transfert`) — aucun nouvel endpoint. Si `compteId` est fourni, le détail
 * est scopé à ce compte. Seules les dépenses (montant < 0) sont listées, comme
 * la heatmap (recettes et ajustements exclus).
 *
 * Props :
 * - date     : "YYYY-MM-DD" ou null (modal fermé si null)
 * - compteId : uuid optionnel — restreint le détail à un compte
 * - onClose  : () => void
 */
export default function FluxJourModal({ date, compteId, onClose }) {
  const isOpen = !!date

  const params = {
    date_min: date,
    date_max: date,
    est_transfert: false,
    ordering: 'montant', // dépenses (négatives) → plus grosses en premier
    page_size: 1000,
  }
  if (compteId) params.compte = compteId

  const { data, isLoading, isError, refetch } = useResourceList(
    'flux',
    params,
    { enabled: isOpen },
  )

  const flux = (data?.results ?? []).filter(
    (f) => !f.est_ajustement && Number(f.montant) < 0,
  )
  const total = flux.reduce((s, f) => s + Math.abs(Number(f.montant)), 0)

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={date ? `Dépenses · ${formatDate(date)}` : ''}
    >
      {isLoading && <Loading message="Chargement des flux..." />}
      {isError && <ErrorState message="Impossible de charger les flux." onRetry={refetch} />}

      {!isLoading && !isError && (
        flux.length === 0 ? (
          <p className="text-sm text-content-3 py-6 text-center">
            Aucune dépense ce jour-là.
          </p>
        ) : (
          <div className="flex flex-col">
            {flux.map((f) => (
              <div
                key={f.id}
                className="flex items-center justify-between gap-3 py-2.5 border-b border-border-app last:border-b-0"
              >
                <div className="min-w-0">
                  <div className="text-sm text-content truncate">
                    {f.libelle || f.categorie_nom || '—'}
                  </div>
                  <div className="text-xs text-content-3 truncate">
                    {f.categorie_nom || '—'}
                    {!compteId && f.compte_nom ? ` · ${f.compte_nom}` : ''}
                  </div>
                </div>
                <span className="text-sm font-medium text-red-600 shrink-0 tabular-nums">
                  {formatEuro(f.montant)}
                </span>
              </div>
            ))}

            <div className="flex items-center justify-between gap-3 pt-3 mt-1">
              <span className="text-xs text-content-2">
                {flux.length} flux
              </span>
              <span className="text-sm font-medium text-content tabular-nums">
                Total −{formatEuro(total)}
              </span>
            </div>
          </div>
        )
      )}
    </Modal>
  )
}

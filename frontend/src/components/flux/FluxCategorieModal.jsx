import { useResourceList } from '../../hooks/useResource'
import Modal from '../ui/Modal'
import { Loading, ErrorState } from '../ui/States'
import { formatEuro, formatDate } from '../../utils/format'

/**
 * Détail des flux d'une catégorie pour un mois donné (drill-down du donut
 * « Dépenses par catégorie »). Lecture seule.
 *
 * Réutilise l'endpoint /flux/ (filtres `categorie`, `mois`, `est_transfert`).
 * Si `compteId` est fourni, le détail est scopé à ce compte (dashboard par compte).
 *
 * Props :
 * - categorie : { id, nom } ou null (modal fermé si null)
 * - mois      : "YYYY-MM-DD" (1er du mois)
 * - compteId  : uuid optionnel — restreint le détail à un compte
 * - onClose   : () => void
 */
export default function FluxCategorieModal({ categorie, mois, compteId, onClose }) {
  const isOpen = !!categorie

  const params = {
    categorie: categorie?.id,
    mois,
    est_transfert: false,
    ordering: 'montant', // dépenses (négatives) → plus grosses en premier
    page_size: 1000,
  }
  if (compteId) params.compte = compteId

  const { data, isLoading, isError, refetch } = useResourceList('flux', params)

  // L'agrégat dashboard exclut déjà les ajustements ; on s'aligne ici.
  const flux = (data?.results ?? []).filter((f) => !f.est_ajustement)
  const total = flux.reduce((s, f) => s + Math.abs(Number(f.montant)), 0)

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={categorie ? `Dépenses · ${categorie.nom}` : ''}
    >
      {isLoading && <Loading message="Chargement des flux..." />}
      {isError && <ErrorState message="Impossible de charger les flux." onRetry={refetch} />}

      {!isLoading && !isError && (
        flux.length === 0 ? (
          <p className="text-sm text-content-3 py-6 text-center">
            Aucune dépense pour cette catégorie ce mois-ci.
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
                    {formatDate(f.date_flux)}
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

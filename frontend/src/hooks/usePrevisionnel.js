import { useQuery } from '@tanstack/react-query'
import apiClient from '../api/client'

// La query key partage le préfixe 'analytics' : les invalidations de
// RESOURCE_DEPENDENCIES (flux, transferts, budgets, abonnements, comptes...)
// la couvrent par prefix-matching React Query.
export default function usePrevisionnel(nbMois = 6) {
  return useQuery({
    queryKey: ['analytics', 'previsionnel', nbMois],
    queryFn: async () => {
      const { data } = await apiClient.get('/analytics/previsionnel/', {
        params: { nb_mois: nbMois },
      })
      return data
    },
  })
}

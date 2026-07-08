import { useQuery, keepPreviousData } from '@tanstack/react-query'
import apiClient from '../api/client'

// Analyse rétrospective (Phase 13) — lecture seule, fiabilité réelle.
// La query key partage le préfixe 'analytics' : les invalidations de
// RESOURCE_DEPENDENCIES (flux, transferts, budgets, comptes...) la couvrent
// par prefix-matching React Query.
export default function useAnalyse(nbMois = 6) {
  return useQuery({
    queryKey: ['analytics', 'analyse', nbMois],
    queryFn: async () => {
      const { data } = await apiClient.get('/analytics/analyse/', {
        params: { nb_mois: nbMois },
      })
      return data
    },
    placeholderData: keepPreviousData,
  })
}

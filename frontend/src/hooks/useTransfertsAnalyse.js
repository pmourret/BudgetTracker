import { useQuery, keepPreviousData } from '@tanstack/react-query'
import apiClient from '../api/client'

// Analyse des transferts internes — lecture seule, fiabilité réelle.
// Query key sous le préfixe 'analytics' : les invalidations de
// RESOURCE_DEPENDENCIES (transferts → analytics) la couvrent par
// prefix-matching React Query.
export default function useTransfertsAnalyse(nbMois = 6) {
  return useQuery({
    queryKey: ['analytics', 'transferts', nbMois],
    queryFn: async () => {
      const { data } = await apiClient.get('/analytics/transferts/', {
        params: { nb_mois: nbMois },
      })
      return data
    },
    placeholderData: keepPreviousData,
  })
}

import { useQuery } from '@tanstack/react-query'
import apiClient from '../api/client'

// Système de points (mécanique B, socle 12-B-1). Query key sous le préfixe
// 'analytics' : les invalidations de RESOURCE_DEPENDENCIES (budgets…) et de
// useUpdateParametres (valeur_point) la couvrent par prefix-matching.
export default function usePoints(nbMois = 6) {
  return useQuery({
    queryKey: ['analytics', 'points', nbMois],
    queryFn: async () => {
      const { data } = await apiClient.get('/analytics/points/', {
        params: { nb_mois: nbMois },
      })
      return data
    },
  })
}

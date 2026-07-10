import { useQuery, keepPreviousData } from '@tanstack/react-query'
import apiClient from '../api/client'

// Analyse des abonnements — lecture seule. Base référentiel (estimatif) pour
// synthese/par_categorie/par_titulaire ; derive_prix/a_risque croisent le réel.
// Query key sous le préfixe 'analytics' : couverte par les invalidations de
// RESOURCE_DEPENDENCIES (abonnements, flux...) via prefix-matching React Query.
export default function useAbonnementsAnalyse(nbMois = 6) {
  return useQuery({
    queryKey: ['analytics', 'abonnements', nbMois],
    queryFn: async () => {
      const { data } = await apiClient.get('/analytics/abonnements/', {
        params: { nb_mois: nbMois },
      })
      return data
    },
    placeholderData: keepPreviousData,
  })
}

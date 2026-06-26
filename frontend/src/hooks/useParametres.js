import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '../api/client'

const ENDPOINT = '/referentiels/parametres-budget/'
const KEY = ['parametres-budget']

// Paramètres globaux du foyer (singleton). Pas de useResource ici : la
// ressource n'est pas une liste paginée mais un objet unique sans id d'URL.
export function useParametres() {
  return useQuery({
    queryKey: KEY,
    queryFn: async () => {
      const { data } = await apiClient.get(ENDPOINT)
      return data
    },
  })
}

export function useUpdateParametres() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload) => {
      const { data } = await apiClient.patch(ENDPOINT, payload)
      return data
    },
    onSuccess: (data) => {
      queryClient.setQueryData(KEY, data)
      // Changer le jour de bascule remappe le `mois` de TOUS les flux côté
      // backend → soldes, budgets et tous les agrégats mensuels changent.
      // On invalide largement (préfixe 'analytics' couvre dashboard +
      // prévisionnel + dashboards par compte).
      ;['flux', 'comptes', 'budgets', 'alertes', 'analytics'].forEach((k) =>
        queryClient.invalidateQueries({ queryKey: [k] })
      )
    },
  })
}

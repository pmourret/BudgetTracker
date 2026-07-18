import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import apiClient from '../api/client'

// Rapprochement bancaire (phase 14-A). Ressource hors `useResource` générique :
// l'upload est multipart et le « rapport » est un endpoint calculé, pas un CRUD.
// L'invalidation par préfixe ['imports'] couvre la liste ET les rapports
// (['imports','rapport',id]).

export function useImportsList() {
  return useQuery({
    queryKey: ['imports', 'list'],
    queryFn: async () => {
      const { data } = await apiClient.get('/imports/')
      return data
    },
  })
}

export function useRapport(lotId) {
  return useQuery({
    queryKey: ['imports', 'rapport', lotId],
    queryFn: async () => {
      const { data } = await apiClient.get(`/imports/${lotId}/rapport/`)
      return data
    },
    enabled: !!lotId,
  })
}

export function useUploadImport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ compte, banque, fichier }) => {
      const form = new FormData()
      form.append('compte', compte)
      form.append('banque', banque)
      form.append('fichier', fichier)
      // axios retire le Content-Type par défaut quand le corps est un FormData
      // et laisse le navigateur poser le boundary multipart.
      const { data } = await apiClient.post('/imports/', form)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['imports'] })
    },
  })
}

// Valider / rejeter un ambigu, ou relancer un rapprochement. Toutes ces
// mutations rafraîchissent le rapport du lot (préfixe ['imports']).
function useLigneAction(build) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (args) => {
      const { url, payload } = build(args)
      const { data } = await apiClient.post(url, payload ?? {})
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['imports'] })
    },
  })
}

export function useValiderLigne() {
  return useLigneAction(({ ligneId, fluxId }) => ({
    url: `/imports-lignes/${ligneId}/valider/`,
    payload: { flux_id: fluxId },
  }))
}

export function useRejeterLigne() {
  return useLigneAction(({ ligneId }) => ({
    url: `/imports-lignes/${ligneId}/rejeter/`,
  }))
}

export function useRelancerRapprochement() {
  return useLigneAction(({ lotId }) => ({
    url: `/imports/${lotId}/relancer/`,
  }))
}

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '../api/client'

function useReferentiel(endpoint) {
  return useQuery({
    queryKey: ['referentiel', endpoint],
    queryFn: async () => {
      const { data } = await apiClient.get(`/referentiels/${endpoint}/`, {
        params: { actif: true },
      })
      return data.results ?? data
    },
    staleTime: 1000 * 60 * 30, // 30 min — les référentiels changent rarement
  })
}

function toOptions(items = []) {
  return items.map((item) => ({
    value: item.id,
    label: item.libelle,
  }))
}

export function useTypesFlux() {
  const query = useReferentiel('types-flux')
  return { ...query, options: toOptions(query.data) }
}

export function useTitulaires() {
  const query = useReferentiel('titulaires')
  return { ...query, options: toOptions(query.data) }
}

export function useModesPaiement() {
  const query = useReferentiel('modes-paiement')
  return { ...query, options: toOptions(query.data) }
}

export function useStatutsFlux() {
  const query = useReferentiel('statuts-flux')
  return { ...query, options: toOptions(query.data) }
}

export function useDevises() {
  const query = useReferentiel('devises')
  return { ...query, options: toOptions(query.data) }
}

export function useFrequences() {
  const query = useReferentiel('frequences')
  return { ...query, options: toOptions(query.data) }
}

export function useTypesCompte() {
  const query = useReferentiel('types-compte')
  return { ...query, options: toOptions(query.data) }
}

export function useEtablissements() {
  const query = useReferentiel('etablissements')
  return { ...query, options: toOptions(query.data) }
}

export function useFiscalites() {
  const query = useReferentiel('fiscalites')
  return { ...query, options: toOptions(query.data) }
}

export function useCreateTitulaire() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload) => {
      const { data } = await apiClient.post('/referentiels/titulaires/', payload)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['referentiel', 'titulaires'] })
    },
  })
}

export function useCreateEtablissement() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload) => {
      const { data } = await apiClient.post('/referentiels/etablissements/', payload)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['referentiel', 'etablissements'] })
    },
  })
}
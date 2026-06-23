import {
  useQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query'
import apiClient from '../api/client'

const RESOURCE_DEPENDENCIES = {
  flux:               ['comptes', 'budgets', 'alertes', 'analytics'],
  transferts:         ['comptes', 'flux', 'analytics'],
  budgets:            ['analytics'],
  'budget-templates': ['budgets', 'analytics'],
  abonnements:        ['analytics'],
  comptes:            ['flux', 'analytics'],
  patrimoine:         ['analytics'],
  alertes:            ['analytics'],
  categories:         ['flux', 'budgets', 'abonnements', 'budget-templates'],
}

function invalidateWithDependencies(queryClient, resource) {
  queryClient.invalidateQueries({ queryKey: [resource] })
  const deps = RESOURCE_DEPENDENCIES[resource] || []
  deps.forEach((dep) => {
    queryClient.invalidateQueries({ queryKey: [dep] })
  })
}

export function useResourceList(resource, params = {}, options = {}) {
  return useQuery({
    queryKey: [resource, 'list', params],
    queryFn: async () => {
      const { data } = await apiClient.get(`/${resource}/`, { params })
      return data
    },
    ...options,
  })
}

// Les catégories forment un référentiel à volume borné, consommé en entier
// par l'UI (accordéon majeures/mineures, optgroups des selects). On demande
// toutes les lignes en une page via ?page_size (garde-fou max_page_size=1000
// côté backend) pour éviter qu'une catégorie au-delà de la 50e « disparaisse »
// dans une page 2 jamais chargée. TOUS les consommateurs de /categories/
// doivent passer par ce hook.
export function useCategories(params = {}) {
  const merged = { page_size: 1000, ...params }
  return useQuery({
    queryKey: ['categories', 'list', merged],
    queryFn: async () => {
      const { data } = await apiClient.get('/categories/', { params: merged })
      // Déballage défensif : compat si la pagination était un jour désactivée.
      const results = data?.results ?? data ?? []
      return Array.isArray(data) ? { results } : { ...data, results }
    },
  })
}

export function useResourceDetail(resource, id) {
  return useQuery({
    queryKey: [resource, 'detail', id],
    queryFn: async () => {
      const { data } = await apiClient.get(`/${resource}/${id}/`)
      return data
    },
    enabled: !!id,
  })
}

export function useCreateResource(resource) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload) => {
      const { data } = await apiClient.post(`/${resource}/`, payload)
      return data
    },
    onSuccess: () => {
      invalidateWithDependencies(queryClient, resource)
    },
  })
}

export function useUpdateResource(resource) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, payload, method = 'patch' }) => {
      const { data } = await apiClient[method](`/${resource}/${id}/`, payload)
      return data
    },
    onSuccess: () => {
      invalidateWithDependencies(queryClient, resource)
    },
  })
}

export function useDeleteResource(resource) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id) => {
      await apiClient.delete(`/${resource}/${id}/`)
      return id
    },
    onSuccess: () => {
      invalidateWithDependencies(queryClient, resource)
    },
  })
}

export function useResourceAction(resource) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, action, payload = {}, method = 'post' }) => {
      const url = id
        ? `/${resource}/${id}/${action}/`
        : `/${resource}/${action}/`
      const { data } = await apiClient[method](url, payload)
      return data
    },
    onSuccess: () => {
      invalidateWithDependencies(queryClient, resource)
    },
  })
}
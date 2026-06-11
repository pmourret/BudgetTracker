import {
  useQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query'
import apiClient from '../api/client'

const RESOURCE_DEPENDENCIES = {
  flux:        ['comptes', 'budgets', 'alertes', 'analytics'],
  transferts:  ['comptes', 'flux', 'analytics'],
  budgets:     ['analytics'],
  comptes:     ['flux', 'analytics'],
  patrimoine:  ['analytics'],
  alertes:     ['analytics'],
  categories:  ['flux', 'budgets', 'abonnements'],
}

function invalidateWithDependencies(queryClient, resource) {
  queryClient.invalidateQueries({ queryKey: [resource] })
  const deps = RESOURCE_DEPENDENCIES[resource] || []
  deps.forEach((dep) => {
    queryClient.invalidateQueries({ queryKey: [dep] })
  })
}

export function useResourceList(resource, params = {}) {
  return useQuery({
    queryKey: [resource, 'list', params],
    queryFn: async () => {
      const { data } = await apiClient.get(`/${resource}/`, { params })
      return data
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
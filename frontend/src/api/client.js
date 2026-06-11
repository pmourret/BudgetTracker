import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
})

apiClient.interceptors.request.use(
  (config) => config,
  (error) => Promise.reject(error)
)

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const message = error.response?.data?.detail || 'Une erreur est survenue.'

    if (status === 404) {
      console.warn('Ressource introuvable :', error.config?.url)
    }
    if (status === 500) {
      console.error('Erreur serveur :', message)
    }

    return Promise.reject(error)
  }
)

export default apiClient
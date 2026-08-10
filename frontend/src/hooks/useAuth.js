import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'

import apiClient from '../api/client'
import { useAuthStore } from '../stores/authStore'

/**
 * Qui est connecté. Sert à afficher un nom, rien de plus.
 *
 * ⚠️ **Ne jamais y lire un droit** : le serializer n'expose ni `is_staff` ni
 * `is_superuser`, précisément pour qu'aucun écran ne prenne l'habitude de
 * décider de ce qu'il montre d'après une réponse d'API. La garantie est au
 * serveur (test de régression côté backend).
 */
export function useMoi() {
  const refresh = useAuthStore((etat) => etat.refresh)
  return useQuery({
    queryKey: ['auth', 'moi'],
    queryFn: async () => (await apiClient.get('/auth/me/')).data,
    enabled: !!refresh,
    // Le nom de l'utilisateur ne change pas en cours de session : inutile de le
    // redemander, et surtout inutile de réessayer — un échec ici veut dire que
    // la session est tombée, ce que l'intercepteur a déjà traité.
    staleTime: Infinity,
    retry: false,
  })
}

/**
 * Qui authentifie cette instance — donc **où se gère le mot de passe**.
 *
 * Lu avant toute connexion, par `axios` nu : il n'y a pas encore de jeton, et
 * l'intercepteur d'`apiClient` n'a rien à faire sur une route anonyme.
 *
 * ⚠️ **Ne jamais faire dépendre la connexion de cette réponse.** Elle n'ajuste
 * qu'un libellé : `retry: false`, et l'écran retombe sur sa formulation neutre
 * si l'appel échoue. Bloquer le formulaire parce qu'un texte d'aide n'est pas
 * arrivé transformerait un détail de confort en panne d'accès.
 */
export function useContexteAuth() {
  return useQuery({
    queryKey: ['auth', 'contexte'],
    queryFn: async () => (await axios.get('/api/v1/auth/contexte/')).data,
    // Un réglage de déploiement : il ne bouge pas en cours de session.
    staleTime: Infinity,
    retry: false,
  })
}

/**
 * Connexion. **Passe par `axios` nu, pas par `apiClient`.**
 *
 * L'intercepteur d'`apiClient` interprète les 401 comme « jeton expiré » et
 * tente un renouvellement. Or ici, un 401 est la réponse métier normale à un
 * mauvais mot de passe : il doit remonter tel quel jusqu'à l'écran. Le client
 * l'exclut déjà par l'URL, mais s'en remettre à ce garde-fou pour la route qui
 * *crée* la session serait fragile.
 */
export function useConnexion() {
  const setTokens = useAuthStore((etat) => etat.setTokens)
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ identifiant, motDePasse }) => {
      const { data } = await axios.post('/api/v1/auth/token/', {
        username: identifiant,
        password: motDePasse,
      })
      return data
    },
    onSuccess: (jetons) => {
      setTokens({ access: jetons.access, refresh: jetons.refresh })
      // Le cache peut contenir les erreurs des requêtes tombées en 401 avant la
      // connexion : sans ce vidage, l'écran s'ouvre sur des cartes en erreur.
      queryClient.clear()
    },
  })
}

/**
 * Déconnexion — jetons effacés **et cache vidé**.
 *
 * Le vidage n'est pas du confort : React Query garde les réponses en mémoire, et
 * sans lui la personne suivante verrait les comptes et les flux de la
 * précédente le temps que les requêtes se rejouent.
 */
export function useDeconnexion() {
  const logout = useAuthStore((etat) => etat.logout)
  const queryClient = useQueryClient()

  return () => {
    // Révoquer **avant** d'effacer : après, on n'a plus le jeton à révoquer.
    // Sans cet appel, la déconnexion n'efface que le navigateur et le refresh
    // reste valable ses 7 jours — sur un poste partagé, ça ne déconnecte pas.
    const { refresh } = useAuthStore.getState()
    if (refresh) {
      // Sans `await` ni traitement d'erreur : la déconnexion locale ne doit
      // **jamais** dépendre du réseau. Un serveur injoignable laisserait sinon
      // la personne connectée sur l'écran qu'elle quitte.
      apiClient.post('/auth/deconnexion/', { refresh }).catch(() => {})
    }
    logout()
    queryClient.clear()
  }
}

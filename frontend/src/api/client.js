import axios from 'axios'

import { useAuthStore } from '../stores/authStore'

/**
 * Client HTTP de BudgetTracker.
 *
 * Injecte le jeton d'accès, et le renouvelle **une fois** sur 401 avant de
 * rejouer la requête. Depuis le durcissement (août 2026), toute l'API est
 * fermée : sans cet intercepteur, l'interface entière reçoit 401.
 */
const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
})

apiClient.interceptors.request.use((config) => {
  const { access } = useAuthStore.getState()
  if (access) config.headers.Authorization = `Bearer ${access}`
  return config
})

/**
 * Le renouvellement en cours, **partagé par tous les appels**.
 *
 * Un écran charge une dizaine de ressources en parallèle ; à l'expiration du
 * jeton, elles reçoivent toutes 401 en même temps. Sans mise en commun, ce sont
 * dix renouvellements simultanés pour un seul besoin.
 *
 * ⚠️ **Aujourd'hui c'est une économie ; demain c'est une condition de
 * correction.** `ROTATE_REFRESH_TOKENS` est actif côté serveur, mais **sans
 * `BLACKLIST_AFTER_ROTATION`** (vérifié : rejouer un ancien jeton renvoie
 * toujours 200). Les dix renouvellements aboutiraient donc, et le dernier
 * écrasant les autres, rien ne casserait. **Le jour où le blacklistage est
 * activé** — il devrait l'être, la rotation ne révoque rien sans lui — le
 * premier renouvellement invalide le jeton que les neuf autres s'apprêtent à
 * présenter : ils sont refusés, et l'utilisateur est déconnecté en ouvrant une
 * page. Ne pas retirer cette mise en commun en la croyant décorative.
 */
let renouvellement = null

/**
 * Le serveur a-t-il **rejeté** le jeton, ou n'a-t-il simplement pas répondu ?
 *
 * ⚠️ Distinction vitale, apprise sur FoyerOS et portée ici avant d'avoir eu à la
 * réapprendre : un `catch` qui attrape *toute* erreur attrape aussi un 502
 * pendant un redéploiement, ou une coupure réseau d'une seconde. Résultat
 * là-bas : un déploiement effaçait les jetons et renvoyait l'écran mural sur la
 * page de connexion, dans un couloir, sans clavier.
 *
 * Un jeton n'est invalide que si le serveur le dit (401/403). Tout le reste est
 * passager : on garde la session, la requête échoue, React Query réessaiera.
 */
function jetonRejete(erreur) {
  const statut = erreur?.response?.status
  return statut === 401 || statut === 403
}

apiClient.interceptors.response.use(
  (reponse) => reponse,
  async (erreur) => {
    const origine = erreur.config
    const statut = erreur.response?.status
    const { refresh, setTokens, logout } = useAuthStore.getState()

    // Un 401 sur la connexion elle-même est une réponse, pas un incident : c'est
    // un mot de passe faux. Le renouveler n'aurait aucun sens et masquerait le
    // message d'erreur que l'écran doit afficher.
    const estRouteAuth = origine?.url?.includes('/auth/token')

    if (statut === 401 && refresh && !origine?._retente && !estRouteAuth) {
      origine._retente = true
      try {
        renouvellement =
          renouvellement ||
          axios.post('/api/v1/auth/token/refresh/', { refresh })
        const { data } = await renouvellement
        renouvellement = null
        // `refresh` peut ne pas revenir si la rotation est désactivée un jour :
        // on conserve alors l'ancien plutôt que d'effacer la session.
        setTokens({ access: data.access, refresh: data.refresh ?? refresh })
        origine.headers.Authorization = `Bearer ${data.access}`
        return apiClient(origine)
      } catch (echec) {
        renouvellement = null
        if (jetonRejete(echec)) logout()
        return Promise.reject(erreur)
      }
    }

    if (statut === 404) {
      console.warn('Ressource introuvable :', origine?.url)
    }
    if (statut === 500) {
      console.error('Erreur serveur :', erreur.response?.data?.detail)
    }

    return Promise.reject(erreur)
  },
)

export default apiClient

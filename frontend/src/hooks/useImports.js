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

/**
 * Le contrôle de solde d'un **compte**, hors de la page d'import.
 *
 * ⚠️ **`204` = « ce compte n'a jamais été rapproché »**, et se traduit par
 * `null`, pas par une erreur : axios rend alors `data === ''`, qui passerait
 * pour un objet vide et ferait afficher un widget rempli de « — ». Le compte
 * jamais rapproché n'affiche simplement rien.
 *
 * Clé sous le préfixe `['imports']` : importer un relevé, supprimer un lot ou
 * créer un flux depuis une ligne invalide déjà ce préfixe — le widget suit
 * sans qu'aucune de ces mutations ait à le connaître.
 */
export function useControleSoldeCompte(compteId) {
  return useQuery({
    queryKey: ['imports', 'controle-compte', compteId],
    queryFn: async () => {
      const reponse = await apiClient.get('/imports/controle-compte/', {
        params: { compte: compteId },
      })
      return reponse.status === 204 ? null : reponse.data
    },
    enabled: !!compteId,
  })
}

export function useUploadImport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ compte, banque, fichier }) => {
      const form = new FormData()
      // Compte optionnel : omis → le backend le résout via le N° de compte du
      // fichier. On n'envoie PAS de chaîne vide (invaliderait le PK).
      if (compte) form.append('compte', compte)
      form.append('banque', banque)
      form.append('fichier', fichier)
      // ⚠️ **`Content-Type: null`, et surtout PAS un axios nu.**
      //
      // Deux pièges se croisent ici, et n'en éviter qu'un casse l'autre :
      //
      // 1. Le défaut `Content-Type: application/json` d'`apiClient` fait que
      //    axios v1 **sérialise le FormData en JSON**
      //    (`defaults/index.js` : `hasJSONContentType ? JSON.stringify(...)`)
      //    → le backend renvoie **415**.
      // 2. Un axios nu évite le 415… mais sort de `apiClient`, donc des deux
      //    intercepteurs : plus d'`Authorization`, plus de renouvellement sur
      //    401. L'upload répondait « Informations d'authentification non
      //    fournies » **en production**, depuis le durcissement d'août 2026.
      //
      // `null` (pas `undefined`, pas `'multipart/form-data'`) résout les deux :
      // `getContentType()` rend `''`, donc le FormData part tel quel ; et
      // `AxiosHeaders.toJSON` écarte les en-têtes `null`, donc rien n'est
      // envoyé et le **navigateur pose lui-même le boundary**. Forcer
      // `multipart/form-data` à la main ne marcherait pas : le boundary
      // manquerait.
      const { data } = await apiClient.post('/imports/', form, {
        headers: { 'Content-Type': null },
      })
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['imports'] })
    },
  })
}

export function useDeleteImport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (lotId) => {
      await apiClient.delete(`/imports/${lotId}/`)
      return lotId
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

// Création d'un flux depuis une ligne (14-B). Un nouveau flux impacte soldes,
// budgets, alertes et analytics → on invalide large (comme une mutation de flux).
export function useCreerFluxDepuisLigne() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ ligneId, categorie, libelle }) => {
      const { data } = await apiClient.post(
        `/imports-lignes/${ligneId}/creer-flux/`,
        { categorie, libelle },
      )
      return data
    },
    onSuccess: () => {
      ;['imports', 'flux', 'comptes', 'budgets', 'alertes', 'analytics'].forEach(
        (key) => queryClient.invalidateQueries({ queryKey: [key] })
      )
    },
  })
}

// Création d'un virement interne depuis une ligne. Deux flux naissent sur DEUX
// comptes, et la ligne du relevé d'en face peut être rapprochée dans la foulée
// → mêmes invalidations que la création de flux, plus `transferts`.
export function useCreerTransfertDepuisLigne() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ ligneId, compteContrepartie, libelle, notes }) => {
      const { data } = await apiClient.post(
        `/imports-lignes/${ligneId}/creer-transfert/`,
        { compte_contrepartie: compteContrepartie, libelle, notes },
      )
      return data
    },
    onSuccess: () => {
      ;['imports', 'transferts', 'flux', 'comptes', 'analytics'].forEach((key) =>
        queryClient.invalidateQueries({ queryKey: [key] })
      )
    },
  })
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

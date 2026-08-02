import { create } from 'zustand'
import { persist } from 'zustand/middleware'

/**
 * Jetons JWT — état client global, persisté dans le navigateur.
 *
 * Même forme que `FoyerOS/frontend/src/stores/authStore.js`, volontairement :
 * les deux applications convergeront vers un service d'identité commun, et deux
 * mécaniques de session divergentes seraient une dette à payer au moment de la
 * fusion. La seule différence est l'absence de foyer courant — ici, une instance
 * *est* un foyer (décision de suite du 2026-08-01).
 *
 * ⚠️ **`refresh` fait foi pour « suis-je connecté ? »**, pas `access`. Ce dernier
 * expire au bout de 30 minutes : s'y fier renverrait l'utilisateur sur l'écran de
 * connexion à chaque retour sur l'onglet, alors que sa session est parfaitement
 * valide et que le client sait la renouveler tout seul.
 */
export const useAuthStore = create(
  persist(
    (set) => ({
      access: null,
      refresh: null,

      setTokens: ({ access, refresh }) => set({ access, refresh }),
      logout: () => set({ access: null, refresh: null }),
    }),
    { name: 'budgettracker-auth' },
  ),
)

/** Vrai tant qu'une session est ouverte — voir l'avertissement ci-dessus. */
export const estConnecte = (etat) => !!etat.refresh

import { Inbox, TriangleAlert } from 'lucide-react'

export function Loading({ message = 'Chargement...' }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 px-4 text-content-2">
      <div className="w-7 h-7 border-[3px] border-border-app border-t-purple-600 rounded-full animate-spin" />
      <span className="text-sm">{message}</span>
    </div>
  )
}

export function ErrorState({ message = 'Une erreur est survenue.', onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 px-4 text-center">
      <TriangleAlert size={30} className="text-red-texte" />
      <span className="text-sm text-content">{message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-2 px-4 py-2 rounded-lg border border-border-app bg-surface text-purple-texte text-sm font-medium cursor-pointer hover:bg-surface-3"
        >
          Réessayer
        </button>
      )}
    </div>
  )
}

/**
 * État vide.
 *
 * `Icon` est un **composant lucide-react**, jamais un emoji : rendu par le
 * navigateur, un emoji est une image couleur dessinée par le système
 * d'exploitation — il ne suit ni la couleur du texte, ni le thème sombre, ni la
 * graisse, et change d'aspect entre Windows, macOS et Android.
 * (D08 de la revue UI/UX du 2026-08-20 ; règle déjà posée en §7 du CLAUDE.md.)
 *
 * Par convention, reprendre **l'icône que la barre latérale donne à la page** :
 * l'état vide parle alors le même vocabulaire que la navigation.
 */
export function EmptyState({ message = 'Aucune donnée à afficher.', Icon = Inbox, action }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 px-4 text-center">
      <Icon size={34} className="text-content-3" strokeWidth={1.5} />
      <span className="text-sm text-content-2">{message}</span>
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}

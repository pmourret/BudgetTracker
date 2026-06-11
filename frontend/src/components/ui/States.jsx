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
      <div className="text-3xl">⚠️</div>
      <span className="text-sm text-content">{message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-2 px-4 py-2 rounded-lg border border-border-app bg-surface text-purple-600 text-sm font-medium cursor-pointer hover:bg-surface-3"
        >
          Réessayer
        </button>
      )}
    </div>
  )
}

export function EmptyState({ message = 'Aucune donnée à afficher.', icon = '📭', action }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 px-4 text-center">
      <div className="text-4xl opacity-60">{icon}</div>
      <span className="text-sm text-content-2">{message}</span>
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
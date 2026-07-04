import { useEffect, useState } from 'react'

/**
 * Renvoie `value` après un délai de stabilité (`delay` ms sans changement).
 * Utilisé pour la recherche texte : évite de relancer une requête à chaque
 * frappe. Reset propre du timer à chaque nouvelle valeur.
 */
export default function useDebouncedValue(value, delay = 350) {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(id)
  }, [value, delay])

  return debounced
}

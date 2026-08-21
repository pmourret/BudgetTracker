import { useState, useEffect } from 'react'

/**
 * Frontière mobile / desktop — **1024 px**, alignée sur ADR 0033.
 *
 * ⚠️ Cette valeur doit rester égale au point de rupture `lg` de Tailwind, qui
 * porte la même bascule côté CSS (`Layout.jsx`, `Modal.jsx`, tableau ↔ cartes).
 * CSS et JS qui divergent, c'est une mise en page qui bascule à deux largeurs
 * différentes selon qui décide.
 *
 * Ne pas confondre avec `sm:` (640 px), qui reste le reflow de contenu — une
 * grille qui passe de 1 à 2 colonnes n'est pas un changement de mode.
 */
const LARGEUR_DESKTOP = 1024

export const mediaQueries = {
  // ⚠️ `1023.98`, pas `1023` : le `.98` couvre les largeurs fractionnaires du
  // zoom navigateur. À 1023,5 px, `max-width: 1023px` est faux alors que le
  // `lg:` du CSS ne s'applique pas encore — le JS servirait le rendu desktop
  // pendant que le CSS montre déjà la barre du bas. (ADR-0033.)
  mobile: `(max-width: ${LARGEUR_DESKTOP - 0.02}px)`,
  desktop: `(min-width: ${LARGEUR_DESKTOP}px)`,
}

export function useMediaQuery(query) {
  const [matches, setMatches] = useState(
    () => window.matchMedia(query).matches
  )

  useEffect(() => {
    const mql = window.matchMedia(query)
    const handler = (e) => setMatches(e.matches)

    mql.addEventListener('change', handler)
    return () => mql.removeEventListener('change', handler)
  }, [query])

  return matches
}

export function useIsMobile() {
  return useMediaQuery(mediaQueries.mobile)
}

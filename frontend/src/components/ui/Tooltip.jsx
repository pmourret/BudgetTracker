import { useEffect, useId, useRef, useState } from 'react'
import { Info } from 'lucide-react'

/**
 * Info-bulle d'aide réutilisable.
 *
 * Une petite icône « i » qui révèle une explication au survol (desktop)
 * ET au clic/tap (indispensable sur mobile/tactile, où le survol n'existe pas).
 *
 * Contenu : on passe soit `texte` seul, soit `titre` + `texte` + `formule`.
 * `formule` est rendue en plus discret (mono) pour distinguer le « comment
 * c'est calculé » de la définition. Conçu pour être alimenté depuis
 * src/constants/definitions.js : `<Tooltip {...DEFINITIONS.solde_total} />`.
 *
 * `align` ancre le panneau pour éviter qu'il déborde près d'un bord :
 *   'center' (défaut) · 'left' (panneau vers la droite) · 'right' (vers la gauche).
 */
export default function Tooltip({
  titre,
  texte,
  formule,
  align = 'center',
  size = 13,
  className = '',
}) {
  const [open, setOpen] = useState(false)
  const wrapperRef = useRef(null)
  const panelId = useId()

  // Ferme au clic en dehors et à la touche Échap (tant que c'est ouvert).
  useEffect(() => {
    if (!open) return
    const onPointer = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const alignClass =
    align === 'left'
      ? 'left-0'
      : align === 'right'
      ? 'right-0'
      : 'left-1/2 -translate-x-1/2'

  return (
    <span
      ref={wrapperRef}
      className={`relative inline-flex items-center align-middle ${className}`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        aria-label={titre ? `Aide : ${titre}` : 'Aide'}
        aria-expanded={open}
        aria-describedby={open ? panelId : undefined}
        onClick={(e) => {
          e.stopPropagation()
          setOpen((v) => !v)
        }}
        className="inline-flex items-center justify-center text-content-3 hover:text-content-2 cursor-help focus:outline-none focus-visible:ring-2 focus-visible:ring-purple-400 rounded-full"
      >
        <Info size={size} />
      </button>

      {open && (
        <span
          id={panelId}
          role="tooltip"
          className={[
            'absolute bottom-full mb-2 z-50',
            alignClass,
            'w-60 max-w-[min(16rem,calc(100vw-2rem))]',
            'rounded-lg border border-border-app bg-surface shadow-lg',
            'px-3 py-2 text-left font-normal normal-case',
            'cursor-default',
          ].join(' ')}
          // Évite que le clic dans le panneau referme via le toggle parent.
          onClick={(e) => e.stopPropagation()}
        >
          {titre && (
            <span className="block text-xs font-semibold text-content mb-0.5">
              {titre}
            </span>
          )}
          {texte && (
            <span className="block text-xs text-content-2 leading-relaxed">
              {texte}
            </span>
          )}
          {formule && (
            <span className="block mt-1.5 text-[11px] text-content-3 leading-relaxed">
              <span className="font-medium">Calcul : </span>
              {formule}
            </span>
          )}
        </span>
      )}
    </span>
  )
}

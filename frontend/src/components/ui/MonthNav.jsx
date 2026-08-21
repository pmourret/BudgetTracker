import { ChevronLeft, ChevronRight } from 'lucide-react'

import { formatMonth } from '../../utils/format'

/**
 * Navigation de mois — « ‹ août 2026 › ».
 *
 * Écrite deux fois et différemment jusqu'au 2026-08-21 : boutons d'icône sans
 * bordure sur le Tableau de bord, boîtes bordées portant les **glyphes
 * textuels** `‹` et `›` sur Budgets. Deux gestes pour une même action, sur deux
 * écrans voisins. (D10 de la revue UI/UX du 2026-08-20.)
 *
 * ⚠️ **Cibles tactiles.** L'original du Tableau de bord posait `p-0.5` autour
 * d'une icône de 18 px, soit une cible de 22 px — inatteignable au doigt. Ici
 * 44 px sous 1024 px, 36 px au-delà, comme les autres contrôles de
 * l'application (ADR-0065).
 *
 * `peutReculer` / `peutAvancer` sont optionnels : un écran qui ne borne pas sa
 * plage les laisse à `true` plutôt que d'inventer une limite.
 */
export default function MonthNav({
  mois,
  onChange,
  peutReculer = true,
  peutAvancer = true,
}) {
  const bouton =
    'h-11 w-11 lg:h-9 lg:w-9 grid place-items-center rounded-md text-content-2 ' +
    'cursor-pointer hover:bg-surface-3 disabled:opacity-30 ' +
    'disabled:hover:bg-transparent disabled:cursor-not-allowed'

  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        onClick={() => onChange(-1)}
        disabled={!peutReculer}
        aria-label="Mois précédent"
        className={bouton}
      >
        <ChevronLeft size={18} />
      </button>
      <span className="text-sm text-content-2 capitalize min-w-[8rem] text-center">
        {formatMonth(mois)}
      </span>
      <button
        type="button"
        onClick={() => onChange(1)}
        disabled={!peutAvancer}
        aria-label="Mois suivant"
        className={bouton}
      >
        <ChevronRight size={18} />
      </button>
    </div>
  )
}

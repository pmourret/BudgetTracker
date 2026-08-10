import { Link } from 'react-router-dom'
import { AlertTriangle, CheckCircle2 } from 'lucide-react'

import Tooltip from '../ui/Tooltip'
import { DEFINITIONS } from '../../constants/definitions'
import { formatEuro, formatDate } from '../../utils/format'
import { useControleSoldeCompte } from '../../hooks/useImports'

/**
 * Confrontation du solde d'un compte à son dernier relevé — **hors page d'import**.
 *
 * Le contrôle existait depuis 14-A, mais seulement dans le rapport d'un lot :
 * il n'était donc visible que le jour où l'on charge un relevé, alors que la
 * question qu'il répond — « mon solde est-il juste ? » — se pose devant un
 * compte.
 *
 * ⚠️ **Deux tons, pas trois : concordant ou non.** L'ancienneté du relevé est
 * écrite en toutes lettres mais ne change **jamais** la couleur — la teinter
 * au-delà de N jours reviendrait à coder un seuil en dur (règle 1), et à
 * décider à la place du foyer à partir de quand un relevé « ne compte plus ».
 * Le nombre de jours est donné ; la lecture reste humaine.
 *
 * Silencieux quand le compte n'a jamais été rapproché (`204` → `null`) : un
 * encart « aucune donnée » sur chaque compte jamais importé serait du bruit.
 */
export default function ControleSoldeCompte({ compteId }) {
  const { data: ctrl, isError } = useControleSoldeCompte(compteId)

  // Un contrôle absent ou en panne ne dit rien de faux : il ne dit rien. Le
  // solde reste affiché au-dessus, et c'est lui la vérité de l'application.
  if (isError || !ctrl) return null

  const coherent = ctrl.coherent
  const jours = ctrl.anciennete_jours

  return (
    <div
      className={`rounded-xl px-4 py-3 ${
        coherent ? 'bg-teal-50 text-teal-800' : 'bg-amber-50 text-amber-800'
      }`}
    >
      <div className="flex items-center gap-1.5 text-sm font-medium">
        {coherent ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
        {coherent ? 'Solde concordant avec le relevé' : `Écart de ${formatEuro(ctrl.ecart)}`}
        <Tooltip {...DEFINITIONS.controle_solde_compte} align="left" size={13} />
      </div>

      <div className="flex flex-wrap gap-x-6 gap-y-1 mt-1.5 text-xs">
        <span>
          Application (actuel) : <strong>{formatEuro(ctrl.solde_app)}</strong>
        </span>
        <span>
          Relevé au {formatDate(ctrl.date_reference)} :{' '}
          <strong>{formatEuro(ctrl.solde_banque)}</strong>
        </span>
        {/* L'âge conditionne la lecture de l'écart : il n'est pas décoratif. */}
        <span>
          {jours === 0
            ? "Relevé du jour"
            : `Relevé vieux de ${jours} jour${jours > 1 ? 's' : ''}`}
        </span>
      </div>

      {!coherent && (
        <div className="text-[11px] mt-1.5 leading-relaxed">
          Deux causes possibles, et la seconde n'est pas un problème : une
          opération non saisie ou mal saisie, ou simplement les mouvements
          survenus depuis le {formatDate(ctrl.date_reference)}.{' '}
          <Link to="/imports" className="underline hover:no-underline">
            Ouvrir le rapprochement
          </Link>{' '}
          pour trancher.
        </div>
      )}
    </div>
  )
}

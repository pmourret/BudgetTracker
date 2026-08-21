import Tooltip from './Tooltip'

/**
 * Un relevé de chiffre : une étiquette, une valeur, parfois une précision.
 *
 * ⚠️ **Pas de carte.** Il était écrit sept fois dans l'application, chaque fois
 * enveloppé d'une bordure et d'un fond. Quand chaque élément d'une page porte la
 * même bordure et le même fond, aucun ne ressort : la hiérarchie s'aplatit et
 * l'œil n'a plus de point d'entrée. La carte se réserve à ce qu'on **compare**
 * ou à ce qu'on **sélectionne** ; un chiffre se lit très bien en typographie
 * nue. (D16 de la revue UI/UX du 2026-08-20.)
 *
 * La rangée qui les contient porte la séparation — voir `MetricRow`.
 */
export default function Metric({
  label,
  value,
  valueClass = 'text-content',
  sub,
  def,
  defAlign = 'left',
}) {
  return (
    <div className="px-4 py-3 first:pl-0">
      <div className="text-xs text-content-2 mb-1 flex items-center gap-1">
        {label}
        {def && <Tooltip {...def} align={defAlign} />}
      </div>
      <div className={`text-xl font-medium tabular-nums ${valueClass}`}>{value}</div>
      {sub && <div className="text-[11px] text-teal-texte mt-0.5">{sub}</div>}
    </div>
  )
}

/**
 * La rangée de relevés.
 *
 * Un filet vertical sépare les colonnes sur écran large — c'est tout ce qu'il
 * faut pour les distinguer, là où quatre boîtes bordées créaient quatre objets
 * concurrents. Sous 640 px la rangée s'empile et les filets deviennent
 * horizontaux : une bordure gauche sur un élément pleine largeur ne sépare rien.
 */
export function MetricRow({ children, colonnes = 4 }) {
  const grille = {
    2: 'sm:grid-cols-2',
    3: 'sm:grid-cols-3',
    4: 'grid-cols-2 lg:grid-cols-4',
  }[colonnes]

  return (
    <div
      className={`grid grid-cols-1 ${grille} divide-y divide-border-app sm:divide-y-0 sm:divide-x sm:divide-border-app`}
    >
      {children}
    </div>
  )
}

import { useMemo } from 'react'

import { useThemeStore } from '../../stores/themeStore'

/**
 * La rampe des **couleurs de données** — disjointe des couleurs d'état.
 *
 * ## Pourquoi elle existe
 *
 * L'application enseigne une sémantique monétaire sur toute sa surface :
 * turquoise = entrant, rouge = sortant, ambre = alerte, violet = marque. La
 * palette catégorielle réutilisait ces mêmes teintes pour désigner des
 * catégories : le turquoise signifiait « revenu » sur un graphique, puis
 * « TEST3 » sur celui juste en dessous, puis « épargne » plus bas. Une même
 * teinte changeait de sens trois fois en un défilement, et le lecteur
 * désapprenait ce que le reste de l'application lui avait appris.
 * (D05 de la revue UI/UX du 2026-08-20.)
 *
 * **Aucune teinte ci-dessous ne reprend une couleur d'état.**
 *
 * ## Pourquoi ces valeurs-là
 *
 * Elles ne sont pas choisies à l'œil. Les deux rampes passent les cinq
 * contrôles d'une palette catégorielle — bande de clarté, plancher de chroma,
 * séparation en vision des couleurs déficiente (protan / deutan / tritan),
 * plancher en vision normale, contraste sur la surface. L'ancienne palette en
 * échouait trois, dont une paire à ΔE 3,7 en deutéranopie : indiscernable.
 *
 * ⚠️ **Le thème sombre a ses propres crans**, il n'est pas une inversion du
 * clair. Sur `--color-surface` en sombre (#1e293b), la rampe claire tombait
 * sous 3:1 pour trois de ses six teintes.
 *
 * ⚠️ **L'ordre compte** : les contrôles portent sur les paires **adjacentes**.
 * Réordonner la liste peut faire échouer la séparation — revalider après tout
 * changement, ne pas juger à l'œil.
 *
 * ## Six, et pas douze
 *
 * Au-delà, deux teintes finissent toujours par se ressembler. Un foyer a peu de
 * catégories majeures ; s'il en a davantage, la couleur cesse d'être le bon
 * véhicule et le libellé prend le relais — il est présent partout ici, donc
 * l'identité ne repose jamais sur la couleur seule.
 */
const RAMPE_CLAIRE = [
  '#2F6FD0', // bleu
  '#D6247E', // magenta
  '#7A4FD4', // violet — distinct du violet de marque #534AB7
  '#C2610F', // orange brûlé — distinct de l'ambre d'alerte #EF9F27
  '#1E8FA8', // cyan — distinct du turquoise « entrant » #1D9E75
  '#4E7A1E', // olive
]

const RAMPE_SOMBRE = [
  '#4E82D8',
  '#DE3B85',
  '#8C6BDC',
  '#CB6E22',
  '#2E9CB6',
  '#659A2C',
]

/**
 * Le rang d'une entité dans la rampe, **dérivé de son identifiant**.
 *
 * ⚠️ Jamais l'index de la liste. Indexée par rang, une catégorie changeait de
 * couleur dès qu'une autre était ajoutée, retirée, ou simplement absente du
 * mois affiché — et la même catégorie portait deux couleurs sur deux écrans
 * voisins. La couleur suit l'entité, pas son classement.
 *
 * Hachage FNV-1a : court, déterministe, sans dépendance.
 */
function rangDe(identifiant, taille) {
  let h = 0x811c9dc5
  const texte = String(identifiant ?? '')
  for (let i = 0; i < texte.length; i += 1) {
    h ^= texte.charCodeAt(i)
    h = Math.imul(h, 0x01000193)
  }
  return Math.abs(h) % taille
}

/**
 * `usePaletteDonnees(identifiants)` — une couleur stable par entité.
 *
 * ## Comment le cran est attribué
 *
 * 1. chaque identifiant vise le cran donné par son hachage ;
 * 2. si ce cran est déjà pris, on avance au suivant libre.
 *
 * Le sondage est indispensable : sans lui, trois catégories pour six crans se
 * télescopaient **une fois sur deux** — deux séries de la même couleur dans une
 * barre empilée, ce que ni le libellé ni la légende ne rattrapent vraiment.
 * Constaté à l'écran le 2026-08-21, sur trois catégories.
 *
 * ⚠️ Les identifiants sont parcourus dans un ordre **trié**, jamais dans celui
 * de la liste affichée. C'est ce qui fait qu'un tri par montant, un changement
 * de période ou un filtre ne repeignent pas les survivants : la couleur dépend
 * de l'ensemble présent, jamais du classement.
 *
 * Limite assumée : ajouter ou retirer une catégorie peut décaler celles qui
 * partageaient son cran. La supprimer demanderait une couleur **stockée** sur
 * la catégorie — un référentiel administrable (§4.1), donc une migration.
 *
 * `identifiants` est optionnel : sans lui, on retombe sur le hachage nu.
 */
export function usePaletteDonnees(identifiants) {
  const isDark = useThemeStore((s) => s.isDark)
  const rampe = isDark ? RAMPE_SOMBRE : RAMPE_CLAIRE

  const cle = identifiants
    ? [...new Set(identifiants.map(String))].sort().join('|')
    : ''

  const attribue = useMemo(() => {
    if (!cle) return null
    const pris = new Array(rampe.length).fill(false)
    const table = new Map()
    for (const id of cle.split('|')) {
      let cran = rangDe(id, rampe.length)
      for (let essai = 0; essai < rampe.length && pris[cran]; essai += 1) {
        cran = (cran + 1) % rampe.length
      }
      pris[cran] = true
      table.set(id, rampe[cran])
    }
    return table
  }, [cle, rampe])

  return {
    rampe,
    couleurDe: (identifiant) =>
      attribue?.get(String(identifiant)) ??
      rampe[rangDe(identifiant, rampe.length)],
  }
}

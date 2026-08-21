import { useEffect, useState } from 'react'
import { AlertTriangle, ArrowLeftRight, Receipt } from 'lucide-react'
import Modal from '../ui/Modal'
import Button from '../ui/Button'
import Input from '../ui/Input'
import Select from '../ui/Select'
import { useCategories, useResourceList } from '../../hooks/useResource'
import {
  useCreerFluxDepuisLigne,
  useCreerTransfertDepuisLigne,
} from '../../hooks/useImports'
import { formatEuro, formatDate } from '../../utils/format'

// Une ligne dont le libellé commence par « VIR » est très probablement un
// virement interne. On s'en sert pour PRÉ-SÉLECTIONNER la nature, jamais pour
// décider : le libellé bancaire n'est pas une clé de détection (un « VIR » peut
// partir chez un tiers, un virement interne peut s'appeler autrement).
const ressembleAVirement = (libelle) => /^\s*vir\b/i.test(libelle || '')

const NATURES = [
  { code: 'flux', label: 'Dépense / recette', Icon: Receipt },
  { code: 'transfert', label: 'Virement interne', Icon: ArrowLeftRight },
]

/**
 * Créer le mouvement manquant d'une ligne de relevé, dans sa vraie nature.
 *
 * Un virement interne ne peut pas être créé en flux simple : il ne toucherait
 * qu'un compte et serait compté en dépense ou en recette (règle §4.4). Il
 * fallait donc quitter le rapprochement pour la page Transferts et y
 * ressaisir un montant et une date déjà lus sur le relevé. Les deux natures
 * vivent maintenant dans la même modale ; le **sens** du virement n'est pas
 * demandé, il se dérive du signe de la ligne côté serveur.
 */
export default function CreerMouvementModal({
  ligne, compteId, compteNom, onClose, onCreated,
}) {
  const [nature, setNature] = useState('flux')
  const [categorie, setCategorie] = useState('')
  const [contrepartie, setContrepartie] = useState('')
  const [libelle, setLibelle] = useState('')
  const [error, setError] = useState('')

  const { data: categoriesData } = useCategories()
  const { data: comptesData } = useResourceList('comptes')
  const creerFlux = useCreerFluxDepuisLigne()
  const creerTransfert = useCreerTransfertDepuisLigne()
  const enCours = creerFlux.isPending || creerTransfert.isPending

  // Le libellé par défaut dépend de la nature : celui du relevé pour un flux,
  // VIDE pour un virement — « VIR SEPA LIVRET A » serait faux du côté du livret,
  // et le service transferts pose alors deux libellés qui disent le sens chacun
  // de leur côté. Changer de nature reprend donc le défaut de cette nature.
  const libelleParDefaut = (code) => (code === 'transfert' ? '' : ligne?.libelle || '')

  useEffect(() => {
    if (!ligne) return
    const initiale = ressembleAVirement(ligne.libelle) ? 'transfert' : 'flux'
    setNature(initiale)
    setCategorie('')
    setContrepartie('')
    setLibelle(initiale === 'transfert' ? '' : ligne.libelle || '')
    setError('')
  }, [ligne])

  const allCats = categoriesData?.results ?? []
  const majeures = allCats.filter((c) => c.est_racine)
  const mineures = allCats.filter((c) => !c.est_racine)
  const categoriesOpts = majeures
    .filter((maj) => !mineures.some((m) => String(m.parent) === String(maj.id)))
    .map((maj) => ({ value: String(maj.id), label: maj.nom }))
  const categoriesGroups = majeures
    .filter((maj) => mineures.some((m) => String(m.parent) === String(maj.id)))
    .map((maj) => ({
      label: maj.nom,
      options: mineures
        .filter((m) => String(m.parent) === String(maj.id))
        .map((m) => ({ value: String(m.id), label: m.nom })),
    }))

  // Le compte du relevé est déjà un des deux côtés du virement : il ne peut pas
  // être sa propre contrepartie (le backend refuse aussi, en 400).
  const comptesOpts = (comptesData?.results ?? [])
    .filter((c) => String(c.id) !== String(compteId))
    .map((c) => ({
      value: String(c.id),
      label: c.etablissement_libelle ? `${c.nom} — ${c.etablissement_libelle}` : c.nom,
    }))

  const echec = (err, defaut) =>
    setError(err.response?.data?.detail || defaut)

  const handleSubmit = () => {
    setError('')
    if (nature === 'flux') {
      if (!categorie) { setError('Choisissez une catégorie.'); return }
      creerFlux.mutate(
        { ligneId: ligne.id, categorie, libelle: libelle || undefined },
        {
          onSuccess: () => onCreated?.(),
          onError: (err) => echec(err, 'Création impossible.'),
        }
      )
      return
    }
    if (!contrepartie) { setError('Choisissez le compte de contrepartie.'); return }
    creerTransfert.mutate(
      { ligneId: ligne.id, compteContrepartie: contrepartie, libelle: libelle || '' },
      {
        onSuccess: (data) => onCreated?.(data),
        onError: (err) => echec(err, 'Création du virement impossible.'),
      }
    )
  }

  if (!ligne) return null

  const sortant = Number(ligne.montant) < 0
  const contrepartieNom =
    comptesOpts.find((o) => o.value === contrepartie)?.label || '…'
  const estVirement = nature === 'transfert'

  return (
    <Modal
      isOpen={!!ligne}
      onClose={onClose}
      title="Créer le mouvement manquant"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Annuler</Button>
          <Button variant="primary" onClick={handleSubmit} disabled={enCours}>
            {enCours
              ? 'Création…'
              : estVirement ? 'Créer le virement et rapprocher' : 'Créer et rapprocher'}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="rounded-lg bg-surface-3 px-4 py-3">
          <div className="text-sm font-medium text-content">{ligne.libelle}</div>
          <div className="flex justify-between mt-1 text-xs text-content-2">
            <span>{compteNom} · {formatDate(ligne.date_operation)}</span>
            <span className={sortant ? 'text-red-texte' : 'text-teal-texte'}>
              {formatEuro(ligne.montant)}
            </span>
          </div>
        </div>

        <div>
          <div className="text-sm font-medium text-content-2 mb-1.5">
            Nature du mouvement <span className="text-red-texte">*</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {NATURES.map(({ code, label, Icon }) => (
              <button
                key={code}
                type="button"
                onClick={() => { setNature(code); setLibelle(libelleParDefaut(code)); setError('') }}
                className={[
                  'flex items-center justify-center gap-1.5 h-11 lg:h-10 px-3 rounded-lg',
                  'border text-sm cursor-pointer transition-colors',
                  nature === code
                    ? 'border-purple-600 text-content font-medium bg-purple-600/10'
                    : 'border-border-app text-content-2 hover:bg-surface-3',
                ].join(' ')}
              >
                <Icon size={15} /> {label}
              </button>
            ))}
          </div>
        </div>

        {ressembleAVirement(ligne.libelle) && !estVirement && (
          <div className="rounded-md bg-amber-600/15 text-amber-texte text-xs px-3 py-2 flex gap-2 leading-relaxed">
            <AlertTriangle size={15} className="shrink-0 mt-0.5" />
            <span>
              Ce libellé ressemble à un <strong>virement interne</strong>. Créé en
              dépense ou en recette, il ne toucherait qu'un compte et serait
              compté dans vos budgets.
            </span>
          </div>
        )}

        <Input
          label="Libellé"
          value={libelle}
          onChange={setLibelle}
          placeholder={estVirement ? 'Laisser vide pour le libellé automatique' : 'Libellé du flux'}
        />

        {estVirement ? (
          <>
            {comptesOpts.length === 0 ? (
              <div className="rounded-md bg-amber-600/15 text-amber-texte text-xs px-3 py-2 leading-relaxed">
                Aucun autre compte n'est disponible : un virement interne a besoin
                de deux comptes. Créez le compte de contrepartie, ou saisissez ce
                mouvement en dépense ou recette.
              </div>
            ) : null}
            <Select
              label="Compte de contrepartie" value={contrepartie} onChange={setContrepartie}
              options={comptesOpts}
              placeholder={sortant ? 'Compte crédité' : 'Compte débité'}
              required error={error}
            />
            <div className="rounded-lg bg-surface-3 px-3 py-2 text-xs text-content-2 leading-relaxed">
              <div className="flex items-center gap-1.5 text-content font-medium">
                {sortant ? compteNom : contrepartieNom}
                <ArrowLeftRight size={13} className="text-content-3" />
                {sortant ? contrepartieNom : compteNom}
              </div>
              <p className="mt-1">
                Le sens vient du <strong>signe de l'opération</strong> :
                {sortant
                  ? ' le relevé montre un débit, donc ce compte est la source.'
                  : ' le relevé montre un crédit, donc ce compte est la destination.'}
                {' '}Deux flux de {formatEuro(Math.abs(Number(ligne.montant)))} seront
                créés au {formatDate(ligne.date_operation)}, en statut{' '}
                <strong>validé</strong>. Un virement n'a pas de catégorie et
                n'entre ni dans les dépenses, ni dans les recettes.
              </p>
            </div>
          </>
        ) : (
          <>
            <Select
              label="Catégorie" value={categorie} onChange={setCategorie}
              options={categoriesOpts} groups={categoriesGroups}
              placeholder="Choisir une catégorie…" required error={error}
            />
            <p className="text-xs text-content-2 leading-relaxed">
              Le flux sera créé sur <strong>{compteNom}</strong> avec le montant et la
              date de l'opération, en statut <strong>validé</strong>, puis rapproché à
              cette ligne.
            </p>
          </>
        )}
      </div>
    </Modal>
  )
}

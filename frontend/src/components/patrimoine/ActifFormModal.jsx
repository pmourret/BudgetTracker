import { useState, useEffect } from 'react'
import { useCreateResource, useUpdateResource } from '../../hooks/useResource'
import { useDevises, useFiscalites, useFrequences } from '../../hooks/useReferentiels'
import Modal from '../ui/Modal'
import Input from '../ui/Input'
import Select from '../ui/Select'
import Button from '../ui/Button'

const TYPES_ACTIF = [
  { value: 'IMMOBILIER',    label: 'Immobilier' },
  { value: 'EPARGNE',       label: 'Épargne bancaire' },
  { value: 'PEA',           label: 'PEA' },
  { value: 'ASSURANCE_VIE', label: 'Assurance-vie' },
  { value: 'COMPTE_TITRES', label: 'Compte-titres' },
  { value: 'CRYPTO',        label: 'Crypto-actifs' },
  { value: 'AUTRE',         label: 'Autre' },
]

export default function ActifFormModal({ isOpen, onClose, actif = null }) {
  const isEdit = Boolean(actif)

  const [nom, setNom] = useState('')
  const [typeActif, setTypeActif] = useState('')
  const [valeurActuelle, setValeurActuelle] = useState('')
  const [valeurAcquisition, setValeurAcquisition] = useState('')
  const [devise, setDevise] = useState('')
  const [fiscalite, setFiscalite] = useState('')
  const [frequenceValo, setFrequenceValo] = useState('')
  const [actifActif, setActifActif] = useState(true)
  const [errors, setErrors] = useState({})

  const createActif = useCreateResource('patrimoine')
  const updateActif = useUpdateResource('patrimoine')
  const { data: devises, options: devisesOpts } = useDevises()
  const { options: fiscalitesOpts } = useFiscalites()
  const { options: frequencesOpts } = useFrequences()

  useEffect(() => {
    if (!isOpen) return
    if (isEdit && actif) {
      setNom(actif.nom ?? '')
      setTypeActif(actif.type_actif ?? '')
      setValeurActuelle(String(actif.valeur_actuelle ?? ''))
      setValeurAcquisition(actif.valeur_acquisition ? String(actif.valeur_acquisition) : '')
      setDevise(actif.devise ? String(actif.devise) : '')
      setFiscalite(actif.fiscalite ? String(actif.fiscalite) : '')
      setFrequenceValo(actif.frequence_valorisation ? String(actif.frequence_valorisation) : '')
      setActifActif(actif.actif ?? true)
    } else {
      setNom(''); setTypeActif(''); setValeurActuelle(''); setValeurAcquisition('')
      setFiscalite(''); setFrequenceValo(''); setActifActif(true)
      const deviseDefaut = (devises ?? []).find((d) => d.est_defaut) || (devises ?? [])[0]
      setDevise(deviseDefaut?.id ? String(deviseDefaut.id) : '')
    }
    setErrors({})
  }, [isOpen, isEdit, actif, devises])

  const parseDecimal = (s) => parseFloat(String(s).replace(',', '.')) || 0

  const validate = () => {
    const e = {}
    const valeur = parseDecimal(valeurActuelle)
    if (!nom.trim()) e.nom = 'Nom requis.'
    if (!typeActif) e.typeActif = 'Type requis.'
    if (valeur < 0) e.valeurActuelle = 'La valeur ne peut pas être négative.'
    if (!devise) e.devise = 'Devise requise.'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = () => {
    if (!validate()) return
    const valeur = parseDecimal(valeurActuelle)
    const acquisition = valeurAcquisition ? parseDecimal(valeurAcquisition) : null

    const payload = {
      nom: nom.trim(),
      type_actif: typeActif,
      valeur_actuelle: valeur.toFixed(2),
      valeur_acquisition: acquisition !== null ? acquisition.toFixed(2) : null,
      devise,
      fiscalite: fiscalite || null,
      frequence_valorisation: frequenceValo || null,
      actif: actifActif,
    }

    if (!isEdit) {
      payload.date_valorisation = valeur > 0 ? new Date().toISOString().slice(0, 10) : null
    }

    const mutation = isEdit ? updateActif : createActif
    const mutateArg = isEdit ? { id: actif.id, payload } : payload

    mutation.mutate(mutateArg, {
      onSuccess: () => onClose(),
      onError: (err) => {
        const apiErrors = err.response?.data || {}
        setErrors((prev) => ({
          ...prev,
          ...Object.fromEntries(
            Object.entries(apiErrors).map(([k, v]) => [
              k, Array.isArray(v) ? v[0] : String(v),
            ])
          ),
        }))
      },
    })
  }

  const isPending = createActif.isPending || updateActif.isPending

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? 'Modifier l\'actif' : 'Nouvel actif'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Annuler</Button>
          <Button variant="primary" onClick={handleSubmit} disabled={isPending}>
            {isPending ? 'Enregistrement...' : isEdit ? 'Enregistrer' : 'Créer'}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Input
          label="Nom" value={nom} onChange={setNom}
          placeholder="Ex : Appartement Paris" error={errors.nom} required
        />
        <Select
          label="Type d'actif" value={typeActif} onChange={setTypeActif}
          options={TYPES_ACTIF} error={errors.typeActif} required
        />
        <Input
          label="Valeur actuelle estimée (€)" type="text" inputMode="decimal"
          value={valeurActuelle} onChange={setValeurActuelle}
          placeholder="0,00" error={errors.valeurActuelle || errors.valeur_actuelle}
        />
        <Input
          label="Valeur d'acquisition (€)" type="text" inputMode="decimal"
          value={valeurAcquisition} onChange={setValeurAcquisition}
          placeholder="Optionnel" error={errors.valeur_acquisition}
        />
        <Select
          label="Devise" value={devise} onChange={setDevise}
          options={devisesOpts} error={errors.devise} required
        />
        <Select
          label="Fiscalité" value={fiscalite} onChange={setFiscalite}
          options={fiscalitesOpts} placeholder="Optionnel"
        />
        <Select
          label="Rappel de valorisation" value={frequenceValo} onChange={setFrequenceValo}
          options={frequencesOpts} placeholder="Aucun rappel"
        />
        {isEdit && (
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={actifActif}
              onChange={(e) => setActifActif(e.target.checked)}
              className="w-4 h-4 accent-purple-600"
            />
            <span className="text-sm text-content">Actif actif</span>
          </label>
        )}
      </div>
    </Modal>
  )
}

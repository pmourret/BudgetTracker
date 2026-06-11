import { useState, useEffect } from 'react'
import { useCreateResource, useUpdateResource, useResourceList } from '../../hooks/useResource'
import { useTypesFlux, useModesPaiement, useFrequences } from '../../hooks/useReferentiels'
import Modal from '../ui/Modal'
import Input from '../ui/Input'
import Select from '../ui/Select'
import Button from '../ui/Button'

function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

export default function AbonnementFormModal({ isOpen, onClose, abonnement = null }) {
  const isEdit = Boolean(abonnement)

  const [nom, setNom] = useState('')
  const [sens, setSens] = useState('depense')
  const [montant, setMontant] = useState('')
  const [compte, setCompte] = useState('')
  const [categorie, setCategorie] = useState('')
  const [frequence, setFrequence] = useState('')
  const [typeFlux, setTypeFlux] = useState('')
  const [modePaiement, setModePaiement] = useState('')
  const [dateDebut, setDateDebut] = useState(todayISO())
  const [dateFin, setDateFin] = useState('')
  const [jourEcheance, setJourEcheance] = useState('')
  const [seuilDivergence, setSeuilDivergence] = useState('10')
  const [actif, setActif] = useState(true)
  const [errors, setErrors] = useState({})

  const createAbonnement = useCreateResource('abonnements')
  const updateAbonnement = useUpdateResource('abonnements')
  const { data: comptesData } = useResourceList('comptes')
  const { data: categoriesData } = useResourceList('categories')
  const { options: frequencesOpts } = useFrequences()
  const { options: typesFluxOpts } = useTypesFlux()
  const { options: modesPaiementOpts } = useModesPaiement()

  const comptesOpts = (comptesData?.results ?? []).map((c) => ({
    value: c.id,
    label: c.etablissement_libelle ? `${c.nom} — ${c.etablissement_libelle}` : c.nom,
  }))

  const allCats = categoriesData?.results ?? []
  const majCats = allCats.filter((c) => c.est_racine)
  const minCats = allCats.filter((c) => !c.est_racine)
  const categoriesOpts = majCats
    .filter((maj) => !minCats.some((m) => String(m.parent) === String(maj.id)))
    .map((maj) => ({ value: String(maj.id), label: maj.nom }))
  const categoriesGroups = majCats
    .filter((maj) => minCats.some((m) => String(m.parent) === String(maj.id)))
    .map((maj) => ({
      label: maj.nom,
      options: minCats
        .filter((m) => String(m.parent) === String(maj.id))
        .map((m) => ({ value: String(m.id), label: m.nom })),
    }))

  useEffect(() => {
    if (!isOpen) return
    if (isEdit && abonnement) {
      const m = Number(abonnement.montant_attendu)
      setNom(abonnement.nom ?? '')
      setSens(m < 0 ? 'depense' : 'recette')
      setMontant(String(Math.abs(m)))
      setCompte(abonnement.compte ? String(abonnement.compte) : '')
      setCategorie(abonnement.categorie ? String(abonnement.categorie) : '')
      setFrequence(abonnement.frequence ? String(abonnement.frequence) : '')
      setTypeFlux(abonnement.type_flux ? String(abonnement.type_flux) : '')
      setModePaiement(abonnement.mode_paiement ? String(abonnement.mode_paiement) : '')
      setDateDebut(abonnement.date_debut ?? todayISO())
      setDateFin(abonnement.date_fin ?? '')
      setJourEcheance(abonnement.jour_echeance ? String(abonnement.jour_echeance) : '')
      setSeuilDivergence(String(abonnement.seuil_divergence_pct ?? '10'))
      setActif(abonnement.actif ?? true)
    } else {
      setNom(''); setSens('depense'); setMontant(''); setCompte('')
      setCategorie(''); setFrequence(''); setTypeFlux(''); setModePaiement('')
      setDateDebut(todayISO()); setDateFin(''); setJourEcheance('')
      setSeuilDivergence('10'); setActif(true)
    }
    setErrors({})
  }, [isOpen, isEdit, abonnement])

  const montantNum = parseFloat(String(montant).replace(',', '.')) || 0
  const montantSigne = sens === 'depense' ? -Math.abs(montantNum) : Math.abs(montantNum)

  const validate = () => {
    const e = {}
    if (!nom.trim()) e.nom = 'Nom requis.'
    if (!montantNum || montantNum <= 0) e.montant = 'Montant requis (> 0).'
    if (!compte) e.compte = 'Compte requis.'
    if (!frequence) e.frequence = 'Fréquence requise.'
    if (!typeFlux) e.typeFlux = 'Type de flux requis.'
    if (jourEcheance && (Number(jourEcheance) < 1 || Number(jourEcheance) > 31)) {
      e.jourEcheance = 'Jour entre 1 et 31.'
    }
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = () => {
    if (!validate()) return

    const payload = {
      nom: nom.trim(),
      compte,
      categorie: categorie || null,
      type_flux: typeFlux,
      mode_paiement: modePaiement || null,
      frequence,
      montant_attendu: montantSigne.toFixed(2),
      seuil_divergence_pct: parseFloat(String(seuilDivergence).replace(',', '.')) || 10,
      date_debut: dateDebut,
      date_fin: dateFin || null,
      jour_echeance: jourEcheance ? parseInt(jourEcheance, 10) : null,
      actif,
    }

    const mutation = isEdit ? updateAbonnement : createAbonnement
    const mutateArg = isEdit ? { id: abonnement.id, payload } : payload

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

  const isPending = createAbonnement.isPending || updateAbonnement.isPending

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? 'Modifier l\'abonnement' : 'Nouvel abonnement'}
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
          placeholder="Ex : Netflix" error={errors.nom} required
        />

        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-content-2">Type d'opération</label>
          <div className="flex gap-2">
            <button
              onClick={() => setSens('depense')}
              className={[
                'flex-1 h-10 rounded-lg border text-sm font-medium cursor-pointer',
                sens === 'depense'
                  ? 'bg-red-50 border-red-600 text-red-800'
                  : 'bg-surface border-border-app text-content-2',
              ].join(' ')}
            >
              ↓ Dépense
            </button>
            <button
              onClick={() => setSens('recette')}
              className={[
                'flex-1 h-10 rounded-lg border text-sm font-medium cursor-pointer',
                sens === 'recette'
                  ? 'bg-teal-50 border-teal-600 text-teal-800'
                  : 'bg-surface border-border-app text-content-2',
              ].join(' ')}
            >
              ↑ Recette
            </button>
          </div>
        </div>

        <div className="flex flex-col gap-1">
          <Input
            label="Montant attendu (€)" type="text" inputMode="decimal"
            value={montant} onChange={setMontant} placeholder="0,00"
            error={errors.montant || errors.montant_attendu} required
          />
          {montantNum > 0 && (
            <span className="text-xs text-content-2">
              Sera enregistré : {montantSigne.toFixed(2).replace('.', ',')} €
            </span>
          )}
        </div>

        <Select
          label="Compte" value={compte} onChange={setCompte}
          options={comptesOpts} error={errors.compte} required
        />
        <Select
          label="Catégorie" value={categorie} onChange={setCategorie}
          options={categoriesOpts} groups={categoriesGroups} placeholder="Optionnel"
        />
        <Select
          label="Fréquence" value={frequence} onChange={setFrequence}
          options={frequencesOpts} error={errors.frequence} required
        />
        <Select
          label="Type de flux" value={typeFlux} onChange={setTypeFlux}
          options={typesFluxOpts} error={errors.typeFlux} required
        />
        <Select
          label="Mode de paiement" value={modePaiement} onChange={setModePaiement}
          options={modesPaiementOpts} placeholder="Optionnel"
        />

        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Date de début" type="date"
            value={dateDebut} onChange={setDateDebut}
            error={errors.date_debut} required
          />
          <Input
            label="Date de fin" type="date"
            value={dateFin} onChange={setDateFin}
            error={errors.date_fin}
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Jour d'échéance" type="number"
            value={jourEcheance} onChange={setJourEcheance}
            placeholder="1-31" error={errors.jourEcheance || errors.jour_echeance}
          />
          <Input
            label="Seuil de divergence (%)" type="text" inputMode="decimal"
            value={seuilDivergence} onChange={setSeuilDivergence}
            placeholder="10"
          />
        </div>

        {isEdit && (
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={actif}
              onChange={(e) => setActif(e.target.checked)}
              className="w-4 h-4 accent-purple-600"
            />
            <span className="text-sm text-content">Abonnement actif</span>
          </label>
        )}
      </div>
    </Modal>
  )
}

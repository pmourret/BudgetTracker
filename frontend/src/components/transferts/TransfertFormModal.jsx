import { useState, useEffect } from 'react'
import { useCreateResource, useResourceList } from '../../hooks/useResource'
import { useTypesFlux, useStatutsFlux, useDevises } from '../../hooks/useReferentiels'
import Modal from '../ui/Modal'
import Input from '../ui/Input'
import Select from '../ui/Select'
import Button from '../ui/Button'

function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

export default function TransfertFormModal({ isOpen, onClose }) {
  const [compteSource, setCompteSource] = useState('')
  const [compteDestination, setCompteDestination] = useState('')
  const [montant, setMontant] = useState('')
  const [date, setDate] = useState(todayISO())
  const [statut, setStatut] = useState('')
  const [notes, setNotes] = useState('')
  const [errors, setErrors] = useState({})

  const createTransfert = useCreateResource('transferts')
  const { data: comptesData } = useResourceList('comptes')
  const { data: typesFluxData } = useTypesFlux()
  const { data: statutsData, options: statutsOpts } = useStatutsFlux()
  const { data: devises } = useDevises()

  const comptesOpts = (comptesData?.results ?? []).map((c) => ({
    value: String(c.id),
    label:
      (c.etablissement_libelle ? `${c.nom} — ${c.etablissement_libelle}` : c.nom) +
      (c.est_commun ? ' · Commun' : ''),
  }))

  // Défaut : le statut définitif (« Validé ») — un transfert saisi est en général réalisé.
  useEffect(() => {
    if (!isOpen) return
    setCompteSource(''); setCompteDestination(''); setMontant('')
    setDate(todayISO()); setNotes(''); setErrors({})
    const definitif = (statutsData ?? []).find((s) => s.est_definitif)
    setStatut(definitif ? String(definitif.id) : '')
  }, [isOpen, statutsData])

  const debitId = (typesFluxData ?? []).find((t) => t.code === 'DEBIT')?.id ?? null
  const creditId = (typesFluxData ?? []).find((t) => t.code === 'CREDIT')?.id ?? null

  const montantNum = parseFloat(montant.replace(',', '.')) || 0

  const validate = () => {
    const e = {}
    if (!compteSource) e.compteSource = 'Compte source requis.'
    if (!compteDestination) e.compteDestination = 'Compte destination requis.'
    if (compteSource && compteDestination && compteSource === compteDestination)
      e.compteDestination = 'Source et destination doivent être différents.'
    if (!montantNum || montantNum <= 0) e.montant = 'Montant requis (> 0).'
    if (!statut) e.statut = 'Statut requis.'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = () => {
    if (!validate()) return
    const deviseDefaut = (devises ?? []).find((d) => d.est_defaut) || (devises ?? [])[0]
    const payload = {
      compte_source: compteSource,
      compte_destination: compteDestination,
      montant: montantNum.toFixed(2),
      date,
      type_flux_debit: debitId,
      type_flux_credit: creditId,
      statut,
      devise: deviseDefaut?.id,
      notes: notes.trim(),
    }
    createTransfert.mutate(payload, {
      onSuccess: () => onClose(),
      onError: (err) => {
        const apiErrors = err.response?.data || {}
        setErrors((prev) => ({
          ...prev,
          compteSource: apiErrors.compte_source?.[0] ?? prev.compteSource,
          compteDestination: apiErrors.compte_destination?.[0] ?? prev.compteDestination,
          montant: apiErrors.montant?.[0] ?? prev.montant,
          general: apiErrors.non_field_errors?.[0] ?? apiErrors.detail,
        }))
      },
    })
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Nouveau transfert"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Annuler</Button>
          <Button variant="primary" onClick={handleSubmit} disabled={createTransfert.isPending}>
            {createTransfert.isPending ? 'Création...' : 'Créer le transfert'}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <p className="text-xs text-content-2">
          Un transfert déplace de l'argent entre deux de vos comptes (ex. courant → épargne).
          Il débite la source et crédite la destination de façon atomique, et n'est compté
          ni comme une dépense ni comme une recette.
        </p>

        {errors.general && (
          <div className="rounded-lg bg-red-50 text-red-700 text-sm px-3 py-2">{errors.general}</div>
        )}

        <Select
          label="Compte source" value={compteSource} onChange={setCompteSource}
          options={comptesOpts} required error={errors.compteSource}
          placeholder="Compte débité"
        />
        <Select
          label="Compte destination" value={compteDestination} onChange={setCompteDestination}
          options={comptesOpts} required error={errors.compteDestination}
          placeholder="Compte crédité"
        />
        <Input
          label="Montant (€)" type="text" inputMode="decimal"
          value={montant} onChange={setMontant} placeholder="0,00"
          required error={errors.montant}
        />
        <Input
          label="Date" type="date" value={date} onChange={setDate} required
        />
        <Select
          label="Statut" value={statut} onChange={setStatut}
          options={statutsOpts} required error={errors.statut}
        />
        <Input
          label="Notes (optionnel)" type="text" value={notes} onChange={setNotes}
          placeholder="Précision sur ce transfert"
        />
      </div>
    </Modal>
  )
}

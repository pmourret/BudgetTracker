import { useState, useEffect } from 'react'
import { useCreateResource, useUpdateResource, useResourceList } from '../../hooks/useResource'
import Modal from '../ui/Modal'
import Input from '../ui/Input'
import Select from '../ui/Select'
import Button from '../ui/Button'

function moisActuelISO() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`
}

export default function BudgetFormModal({ isOpen, onClose, moisDefaut, budget = null }) {
  const isEdit = Boolean(budget)

  const [categorie, setCategorie] = useState('')
  const [mois, setMois] = useState(moisDefaut || moisActuelISO())
  const [montantPrevu, setMontantPrevu] = useState('')
  const [notes, setNotes] = useState('')
  const [errors, setErrors] = useState({})

  const createBudget = useCreateResource('budgets')
  const updateBudget = useUpdateResource('budgets')
  const { data: categoriesData } = useResourceList('categories')

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
    if (isEdit && budget) {
      setCategorie(budget.categorie ? String(budget.categorie) : '')
      setMois(budget.mois ?? moisDefaut ?? moisActuelISO())
      setMontantPrevu(String(budget.montant_prevu ?? ''))
      setNotes(budget.notes ?? '')
    } else {
      setCategorie('')
      setMois(moisDefaut || moisActuelISO())
      setMontantPrevu('')
      setNotes('')
    }
    setErrors({})
  }, [isOpen, isEdit, budget, moisDefaut])

  const validate = () => {
    const e = {}
    const montant = parseFloat(String(montantPrevu).replace(',', '.')) || 0
    if (!categorie) e.categorie = 'Catégorie requise.'
    if (!montant || montant <= 0) e.montantPrevu = 'Montant prévu requis (> 0).'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = () => {
    if (!validate()) return
    const montant = parseFloat(String(montantPrevu).replace(',', '.'))

    const payload = {
      categorie,
      mois,
      montant_prevu: montant.toFixed(2),
      notes,
    }

    const mutation = isEdit ? updateBudget : createBudget
    const mutateArg = isEdit ? { id: budget.id, payload } : payload

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

  const isPending = createBudget.isPending || updateBudget.isPending

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? 'Modifier le budget' : 'Nouveau budget'}
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
        <Select
          label="Catégorie"
          value={categorie}
          onChange={setCategorie}
          options={categoriesOpts}
          groups={categoriesGroups}
          error={errors.categorie}
          required
        />

        <Input
          label="Mois"
          type="month"
          value={mois.slice(0, 7)}
          onChange={(val) => setMois(`${val}-01`)}
          error={errors.mois}
          required
        />

        <Input
          label="Montant prévu (€)"
          type="text"
          inputMode="decimal"
          value={montantPrevu}
          onChange={setMontantPrevu}
          placeholder="0,00"
          error={errors.montantPrevu || errors.montant_prevu}
          required
        />

        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-content-2">Notes</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Optionnel"
            rows={2}
            className="w-full px-3 py-2 rounded-lg border border-border-app bg-surface text-sm text-content outline-none focus:border-purple-600 resize-none"
          />
        </div>
      </div>
    </Modal>
  )
}

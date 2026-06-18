import { useState, useEffect } from 'react'
import { useCreateResource, useUpdateResource, useCategories } from '../../hooks/useResource'
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
  const [categoriesIncluses, setCategoriesIncluses] = useState([])
  const [errors, setErrors] = useState({})

  const createBudget = useCreateResource('budgets')
  const updateBudget = useUpdateResource('budgets')
  const { data: categoriesData } = useCategories()

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
      options: [
        // La majeure elle-même en premier pour créer un budget d'ensemble
        { value: String(maj.id), label: `${maj.nom} — budget global` },
        ...minCats
          .filter((m) => String(m.parent) === String(maj.id))
          .map((m) => ({ value: String(m.id), label: m.nom })),
      ],
    }))

  // Catégorie sélectionnée et ses informations
  // Majeure = racine avec au moins une sous-catégorie active (cohérent avec le backend)
  const selectedCat = allCats.find((c) => String(c.id) === categorie)
  const mineuresActives = allCats.filter(
    (c) => !c.est_racine && String(c.parent) === categorie && c.actif
  )
  const estMajeure = selectedCat?.est_racine === true && mineuresActives.length > 0

  // Mineures actives de la majeure sélectionnée (déjà calculé dans mineuresActives)
  const mineuresDisponibles = estMajeure ? mineuresActives : []

  // Quand on change de catégorie → resynchroniser les mineures cochées.
  // En édition, revenir à la catégorie d'origine restaure la sélection sauvegardée.
  useEffect(() => {
    if (isEdit && budget && categorie === String(budget.categorie)) {
      setCategoriesIncluses((budget.categories_incluses ?? []).map((id) => String(id)))
    } else if (estMajeure) {
      setCategoriesIncluses(mineuresDisponibles.map((m) => String(m.id)))
    } else {
      setCategoriesIncluses([])
    }
  }, [categorie]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!isOpen) return
    if (isEdit && budget) {
      setCategorie(budget.categorie ? String(budget.categorie) : '')
      setMois(budget.mois ?? moisDefaut ?? moisActuelISO())
      setMontantPrevu(String(budget.montant_prevu ?? ''))
      setNotes(budget.notes ?? '')
      // Pré-cocher les mineures déjà incluses
      setCategoriesIncluses(
        (budget.categories_incluses ?? []).map((id) => String(id))
      )
    } else {
      setCategorie('')
      setMois(moisDefaut || moisActuelISO())
      setMontantPrevu('')
      setNotes('')
      setCategoriesIncluses([])
    }
    setErrors({})
  }, [isOpen, isEdit, budget, moisDefaut])

  const toggleMineure = (id) => {
    setCategoriesIncluses((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    )
  }

  const validate = () => {
    const e = {}
    const montant = parseFloat(String(montantPrevu).replace(',', '.')) || 0
    if (!categorie) e.categorie = 'Catégorie requise.'
    if (!montant || montant <= 0) e.montantPrevu = 'Montant prévu requis (> 0).'
    if (estMajeure && categoriesIncluses.length === 0) {
      e.categoriesIncluses = 'Sélectionnez au moins une sous-catégorie.'
    }
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

    if (estMajeure) {
      payload.categories_incluses = categoriesIncluses
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
  const submitDisabled = isPending || (estMajeure && categoriesIncluses.length === 0)

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? 'Modifier le budget' : 'Nouveau budget'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Annuler</Button>
          <Button variant="primary" onClick={handleSubmit} disabled={submitDisabled}>
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

        {/* Section mineures — visible uniquement pour une catégorie majeure */}
        {estMajeure && mineuresDisponibles.length > 0 && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-content">
                Sous-catégories incluses
              </span>
              <span className="text-xs text-content-3">
                {categoriesIncluses.length} / {mineuresDisponibles.length}
              </span>
            </div>
            <div className="flex flex-col gap-1 rounded-lg border border-border-app bg-surface-2 px-3 py-2">
              {mineuresDisponibles.map((m) => (
                <label key={m.id} className="flex items-center gap-2.5 py-1 cursor-pointer">
                  <input
                    type="checkbox"
                    className="w-4 h-4 accent-purple-600 cursor-pointer"
                    checked={categoriesIncluses.includes(String(m.id))}
                    onChange={() => toggleMineure(String(m.id))}
                  />
                  <span className="text-sm text-content">{m.nom}</span>
                </label>
              ))}
            </div>
            {errors.categoriesIncluses && (
              <p className="text-xs text-red-600">{errors.categoriesIncluses}</p>
            )}
            {errors.categories_incluses && (
              <p className="text-xs text-red-600">{errors.categories_incluses}</p>
            )}
          </div>
        )}

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

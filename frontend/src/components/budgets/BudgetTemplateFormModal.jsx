import { useState, useEffect } from 'react'
import { useCreateResource, useUpdateResource, useResourceList } from '../../hooks/useResource'
import Modal from '../ui/Modal'
import Input from '../ui/Input'
import Select from '../ui/Select'
import Button from '../ui/Button'

export default function BudgetTemplateFormModal({ isOpen, onClose, template = null }) {
  const isEdit = Boolean(template)

  const [categorie, setCategorie] = useState('')
  const [montantDefaut, setMontantDefaut] = useState('')
  const [notes, setNotes] = useState('')
  const [actif, setActif] = useState(true)
  const [categoriesIncluses, setCategoriesIncluses] = useState([])
  const [errors, setErrors] = useState({})

  const createTemplate = useCreateResource('budget-templates')
  const updateTemplate = useUpdateResource('budget-templates')
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
      options: [
        { value: String(maj.id), label: `${maj.nom} — budget global` },
        ...minCats
          .filter((m) => String(m.parent) === String(maj.id))
          .map((m) => ({ value: String(m.id), label: m.nom })),
      ],
    }))

  const selectedCat = allCats.find((c) => String(c.id) === categorie)
  const mineuresActives = allCats.filter(
    (c) => !c.est_racine && String(c.parent) === categorie && c.actif
  )
  const estMajeure = selectedCat?.est_racine === true && mineuresActives.length > 0
  const mineuresDisponibles = estMajeure ? mineuresActives : []

  useEffect(() => {
    if (!isEdit && estMajeure) {
      setCategoriesIncluses(mineuresDisponibles.map((m) => String(m.id)))
    } else if (!isEdit) {
      setCategoriesIncluses([])
    }
  }, [categorie]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!isOpen) return
    if (isEdit && template) {
      setCategorie(template.categorie ? String(template.categorie) : '')
      setMontantDefaut(String(template.montant_defaut ?? ''))
      setNotes(template.notes ?? '')
      setActif(template.actif ?? true)
      setCategoriesIncluses(
        (template.categories_incluses ?? []).map((id) => String(id))
      )
    } else {
      setCategorie('')
      setMontantDefaut('')
      setNotes('')
      setActif(true)
      setCategoriesIncluses([])
    }
    setErrors({})
  }, [isOpen, isEdit, template])

  const toggleMineure = (id) => {
    setCategoriesIncluses((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    )
  }

  const validate = () => {
    const e = {}
    const montant = parseFloat(String(montantDefaut).replace(',', '.')) || 0
    if (!categorie) e.categorie = 'Catégorie requise.'
    if (!montant || montant <= 0) e.montantDefaut = 'Montant par défaut requis (> 0).'
    if (estMajeure && categoriesIncluses.length === 0) {
      e.categoriesIncluses = 'Sélectionnez au moins une sous-catégorie.'
    }
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = () => {
    if (!validate()) return
    const montant = parseFloat(String(montantDefaut).replace(',', '.'))

    const payload = {
      categorie,
      montant_defaut: montant.toFixed(2),
      notes,
      actif,
    }
    if (estMajeure) {
      payload.categories_incluses = categoriesIncluses
    }

    const mutation = isEdit ? updateTemplate : createTemplate
    const mutateArg = isEdit ? { id: template.id, payload } : payload

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

  const isPending = createTemplate.isPending || updateTemplate.isPending
  const submitDisabled = isPending || (estMajeure && categoriesIncluses.length === 0)

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? 'Modifier le modèle' : 'Nouveau modèle de budget'}
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
          disabled={isEdit}
        />

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
          label="Montant par défaut (€)"
          type="text"
          inputMode="decimal"
          value={montantDefaut}
          onChange={setMontantDefaut}
          placeholder="0,00"
          error={errors.montantDefaut || errors.montant_defaut}
          required
        />

        {isEdit && (
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              className="w-4 h-4 accent-purple-600 cursor-pointer"
              checked={actif}
              onChange={(e) => setActif(e.target.checked)}
            />
            <span className="text-sm text-content">Modèle actif (reconduit automatiquement)</span>
          </label>
        )}

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

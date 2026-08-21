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

  const [typeBudget, setTypeBudget] = useState('categorie') // 'categorie' | 'thematique'
  const [categorie, setCategorie] = useState('')
  const [nom, setNom] = useState('')
  const [mois, setMois] = useState(moisDefaut || moisActuelISO())
  const [montantPrevu, setMontantPrevu] = useState('')
  const [notes, setNotes] = useState('')
  const [enJeu, setEnJeu] = useState(false)
  const [categoriesIncluses, setCategoriesIncluses] = useState([])
  const [errors, setErrors] = useState({})

  const createBudget = useCreateResource('budgets')
  const updateBudget = useUpdateResource('budgets')
  const { data: categoriesData } = useCategories()

  const allCats = categoriesData?.results ?? []
  const majCats = allCats.filter((c) => c.est_racine)
  const minCats = allCats.filter((c) => !c.est_racine)

  const estThematique = typeBudget === 'thematique'

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

  // --- Feuilles disponibles pour un budget thématique (tous arbres confondus) ---
  // Une feuille = mineure active, OU racine active sans sous-catégorie active.
  const racinesFeuilles = majCats.filter(
    (maj) => maj.actif && !minCats.some((m) => String(m.parent) === String(maj.id) && m.actif)
  )
  const feuillesGroupees = [
    ...majCats
      .filter((maj) => minCats.some((m) => String(m.parent) === String(maj.id) && m.actif))
      .map((maj) => ({
        label: maj.nom,
        feuilles: minCats
          .filter((m) => String(m.parent) === String(maj.id) && m.actif)
          .map((m) => ({ id: String(m.id), nom: m.nom })),
      })),
    ...(racinesFeuilles.length > 0
      ? [{ label: 'Sans groupe', feuilles: racinesFeuilles.map((c) => ({ id: String(c.id), nom: c.nom })) }]
      : []),
  ]

  // Catégorie sélectionnée (mode "par catégorie")
  const selectedCat = allCats.find((c) => String(c.id) === categorie)
  const mineuresActives = allCats.filter(
    (c) => !c.est_racine && String(c.parent) === categorie && c.actif
  )
  const estMajeure = selectedCat?.est_racine === true && mineuresActives.length > 0
  const mineuresDisponibles = estMajeure ? mineuresActives : []

  // Changement de catégorie (mode "par catégorie") → resynchroniser les mineures cochées.
  useEffect(() => {
    if (estThematique) return
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
      const thematique = !budget.categorie
      setTypeBudget(thematique ? 'thematique' : 'categorie')
      setCategorie(budget.categorie ? String(budget.categorie) : '')
      setNom(budget.nom ?? '')
      setMois(budget.mois ?? moisDefaut ?? moisActuelISO())
      setMontantPrevu(String(budget.montant_prevu ?? ''))
      setNotes(budget.notes ?? '')
      setEnJeu(Boolean(budget.en_jeu))
      setCategoriesIncluses((budget.categories_incluses ?? []).map((id) => String(id)))
    } else {
      setTypeBudget('categorie')
      setCategorie('')
      setNom('')
      setMois(moisDefaut || moisActuelISO())
      setMontantPrevu('')
      setNotes('')
      setEnJeu(false)
      setCategoriesIncluses([])
    }
    setErrors({})
  }, [isOpen, isEdit, budget, moisDefaut])

  // Bascule de type → on repart d'une sélection propre.
  const changeType = (t) => {
    if (t === typeBudget) return
    setTypeBudget(t)
    setCategoriesIncluses([])
    setCategorie('')
    setErrors({})
  }

  const toggleFeuille = (id) => {
    setCategoriesIncluses((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    )
  }

  const validate = () => {
    const e = {}
    const montant = parseFloat(String(montantPrevu).replace(',', '.')) || 0
    if (!montant || montant <= 0) e.montantPrevu = 'Montant prévu requis (> 0).'
    if (estThematique) {
      if (!nom.trim()) e.nom = 'Nom requis.'
      if (categoriesIncluses.length === 0) {
        e.categoriesIncluses = 'Sélectionnez au moins une catégorie.'
      }
    } else {
      if (!categorie) e.categorie = 'Catégorie requise.'
      if (estMajeure && categoriesIncluses.length === 0) {
        e.categoriesIncluses = 'Sélectionnez au moins une sous-catégorie.'
      }
    }
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = () => {
    if (!validate()) return
    const montant = parseFloat(String(montantPrevu).replace(',', '.'))

    const payload = {
      mois,
      montant_prevu: montant.toFixed(2),
      notes,
      en_jeu: enJeu,
    }

    if (estThematique) {
      payload.categorie = null
      payload.nom = nom.trim()
      payload.categories_incluses = categoriesIncluses
    } else {
      payload.categorie = categorie
      if (estMajeure) payload.categories_incluses = categoriesIncluses
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
  const submitDisabled =
    isPending ||
    (estThematique
      ? !nom.trim() || categoriesIncluses.length === 0
      : estMajeure && categoriesIncluses.length === 0)

  const nbFeuilles = feuillesGroupees.reduce((n, g) => n + g.feuilles.length, 0)

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
        {/* Sélecteur de type */}
        <div className="flex gap-1 rounded-lg bg-surface-2 p-1">
          {[
            { key: 'categorie', label: 'Par catégorie' },
            { key: 'thematique', label: 'Thématique' },
          ].map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => changeType(t.key)}
              className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition ${
                typeBudget === t.key
                  ? 'bg-surface text-content shadow-sm'
                  : 'text-content-3 hover:text-content-2'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {estThematique ? (
          <>
            <Input
              label="Nom du budget"
              type="text"
              value={nom}
              onChange={setNom}
              placeholder="Ex. Assurances"
              error={errors.nom}
              required
            />
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-content">
                  Catégories regroupées
                </span>
                <span className="text-xs text-content-3">
                  {categoriesIncluses.length} sélectionnée{categoriesIncluses.length > 1 ? 's' : ''}
                </span>
              </div>
              <p className="text-xs text-content-3">
                Sélectionnez des sous-catégories de différents groupes (ex. mutuelle,
                assurance habitation, assurance animaux). Une catégorie déjà budgétée
                ce mois ne peut pas être reprise.
              </p>
              <div className="flex flex-col gap-3 rounded-lg border border-border-app bg-surface-2 px-3 py-2 max-h-72 overflow-y-auto">
                {nbFeuilles === 0 && (
                  <span className="text-sm text-content-3 py-1">
                    Aucune catégorie disponible.
                  </span>
                )}
                {feuillesGroupees.map((g) => (
                  <div key={g.label} className="flex flex-col gap-1">
                    <span className="text-xs font-semibold uppercase tracking-wide text-content-3">
                      {g.label}
                    </span>
                    {g.feuilles.map((f) => (
                      <label key={f.id} className="flex items-center gap-2.5 py-0.5 cursor-pointer">
                        <input
                          type="checkbox"
                          className="w-4 h-4 accent-purple-600 cursor-pointer"
                          checked={categoriesIncluses.includes(f.id)}
                          onChange={() => toggleFeuille(f.id)}
                        />
                        <span className="text-sm text-content">{f.nom}</span>
                      </label>
                    ))}
                  </div>
                ))}
              </div>
              {(errors.categoriesIncluses || errors.categories_incluses) && (
                <p className="text-xs text-red-texte">
                  {errors.categoriesIncluses || errors.categories_incluses}
                </p>
              )}
            </div>
          </>
        ) : (
          <>
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
                        onChange={() => toggleFeuille(String(m.id))}
                      />
                      <span className="text-sm text-content">{m.nom}</span>
                    </label>
                  ))}
                </div>
                {(errors.categoriesIncluses || errors.categories_incluses) && (
                  <p className="text-xs text-red-texte">
                    {errors.categoriesIncluses || errors.categories_incluses}
                  </p>
                )}
              </div>
            )}
          </>
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

        <label className="flex items-start gap-2.5 cursor-pointer rounded-lg border border-border-app bg-surface-2 px-3 py-2.5">
          <input
            type="checkbox"
            className="w-4 h-4 mt-0.5 accent-purple-600 cursor-pointer"
            checked={enJeu}
            onChange={(e) => setEnJeu(e.target.checked)}
          />
          <span className="text-sm text-content">
            Enveloppe « en jeu » (système de points)
            <span className="block text-xs text-content-3 mt-0.5">
              Rapporte des points si non dépassée, en fait perdre sinon.
            </span>
          </span>
        </label>

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

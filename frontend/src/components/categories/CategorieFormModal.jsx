import { useState, useEffect } from 'react'
import { useCreateResource, useUpdateResource } from '../../hooks/useResource'
import Modal from '../ui/Modal'
import Input from '../ui/Input'
import Button from '../ui/Button'

export default function CategorieFormModal({
  isOpen,
  onClose,
  categorie = null,
  parentId = null,
  parentNom = null,
}) {
  const isEdit = Boolean(categorie)
  const isMineureCreate = !isEdit && Boolean(parentId)

  const [nom, setNom] = useState('')
  const [code, setCode] = useState('')
  const [description, setDescription] = useState('')
  const [ordre, setOrdre] = useState('')
  const [actif, setActif] = useState(true)
  const [errors, setErrors] = useState({})

  const createCategorie = useCreateResource('categories')
  const updateCategorie = useUpdateResource('categories')

  useEffect(() => {
    if (!isOpen) return
    if (isEdit && categorie) {
      setNom(categorie.nom ?? '')
      setCode(categorie.code ?? '')
      setDescription(categorie.description ?? '')
      setOrdre(categorie.ordre != null ? String(categorie.ordre) : '')
      setActif(categorie.actif ?? true)
    } else {
      setNom(''); setCode(''); setDescription(''); setOrdre(''); setActif(true)
    }
    setErrors({})
  }, [isOpen, isEdit, categorie])

  const validate = () => {
    const e = {}
    if (!nom.trim()) e.nom = 'Nom requis.'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = () => {
    if (!validate()) return

    const payload = { nom: nom.trim(), description: description.trim() }
    if (code.trim()) payload.code = code.trim()
    if (ordre !== '') payload.ordre = parseInt(ordre, 10)
    if (!isEdit && isMineureCreate) payload.parent = parentId
    if (isEdit) payload.actif = actif

    const mutation = isEdit ? updateCategorie : createCategorie
    const mutateArg = isEdit ? { id: categorie.id, payload } : payload

    mutation.mutate(mutateArg, {
      onSuccess: () => onClose(),
      onError: (err) => {
        const apiErrors = err.response?.data || {}
        setErrors((prev) => ({
          ...prev,
          ...Object.fromEntries(
            Object.entries(apiErrors).map(([k, v]) => [k, Array.isArray(v) ? v[0] : String(v)])
          ),
        }))
      },
    })
  }

  const isPending = createCategorie.isPending || updateCategorie.isPending

  const title = isEdit
    ? `Modifier « ${categorie.nom} »`
    : isMineureCreate
      ? `Nouvelle sous-catégorie de ${parentNom}`
      : 'Nouvelle catégorie principale'

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={title}
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
        {isMineureCreate && (
          <div className="text-xs text-content-3 bg-surface-3 rounded-lg px-3 py-2">
            Catégorie principale : <strong className="text-content-2">{parentNom}</strong>
          </div>
        )}
        {isEdit && categorie?.parent_nom && (
          <div className="text-xs text-content-3 bg-surface-3 rounded-lg px-3 py-2">
            Catégorie principale : <strong className="text-content-2">{categorie.parent_nom}</strong>
          </div>
        )}

        <Input
          label="Nom"
          value={nom}
          onChange={setNom}
          placeholder={isMineureCreate ? 'Ex : Courses' : 'Ex : Alimentation'}
          error={errors.nom}
          required
        />

        <Input
          label="Code (optionnel — auto-généré si vide)"
          value={code}
          onChange={setCode}
          placeholder="Ex : ALIM"
          error={errors.code}
        />

        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-content-2">Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optionnel"
            rows={2}
            className="w-full px-3 py-2 rounded-lg border border-border-app bg-surface text-sm text-content outline-none focus:border-purple-600 resize-none"
          />
        </div>

        <Input
          label="Ordre d'affichage"
          type="number"
          value={ordre}
          onChange={setOrdre}
          placeholder="0"
          error={errors.ordre}
        />

        {isEdit && (
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={actif}
              onChange={(e) => setActif(e.target.checked)}
              className="w-4 h-4 accent-purple-600"
            />
            <span className="text-sm text-content">Catégorie active</span>
          </label>
        )}
      </div>
    </Modal>
  )
}

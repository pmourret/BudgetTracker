import { useState, useEffect } from 'react'
import { useCreateResource, useUpdateResource } from '../../hooks/useResource'
import {
  useTypesCompte, useTitulaires, useEtablissements, useDevises,
  useCreateTitulaire, useCreateEtablissement,
} from '../../hooks/useReferentiels'
import Modal from '../ui/Modal'
import Input from '../ui/Input'
import Select from '../ui/Select'
import Button from '../ui/Button'

function InlineCreate({ placeholder, onSave, onCancel, isPending, error }) {
  const [nom, setNom] = useState('')
  return (
    <div className="flex flex-col gap-2 p-3 bg-surface-3 rounded-lg border border-border-app">
      <Input
        value={nom}
        onChange={setNom}
        placeholder={placeholder}
        error={error}
      />
      <div className="flex gap-2 justify-end">
        <Button variant="secondary" onClick={onCancel}>Annuler</Button>
        <Button
          variant="primary"
          onClick={() => nom.trim() && onSave(nom.trim())}
          disabled={isPending || !nom.trim()}
        >
          {isPending ? 'Création...' : 'Créer'}
        </Button>
      </div>
    </div>
  )
}

function SelectWithCreate({ label, value, onChange, options, error, required, onCreate }) {
  const [showForm, setShowForm] = useState(false)
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-content-2">
          {label}{required && <span className="text-red-600"> *</span>}
        </label>
        {!showForm && (
          <button
            type="button"
            onClick={() => setShowForm(true)}
            className="text-xs text-purple-600 hover:underline cursor-pointer"
          >
            + Nouveau
          </button>
        )}
      </div>
      <Select
        value={value}
        onChange={onChange}
        options={options}
        error={error}
      />
      {showForm && (
        <onCreate.Component
          onSave={(libelle) => onCreate.save(libelle, () => setShowForm(false))}
          onCancel={() => setShowForm(false)}
          isPending={onCreate.isPending}
          error={onCreate.error}
        />
      )}
    </div>
  )
}

export default function CompteFormModal({ isOpen, onClose, compte = null }) {
  const isEdit = Boolean(compte)

  const [code, setCode] = useState('')
  const [nom, setNom] = useState('')
  const [typeCompte, setTypeCompte] = useState('')
  const [titulaire, setTitulaire] = useState('')
  const [etablissement, setEtablissement] = useState('')
  const [devise, setDevise] = useState('')
  const [soldeInitial, setSoldeInitial] = useState('0')
  const [actif, setActif] = useState(true)
  const [estCommun, setEstCommun] = useState(false)
  const [dateOuverture, setDateOuverture] = useState('')
  const [notes, setNotes] = useState('')
  const [errors, setErrors] = useState({})
  const [newTitulaireError, setNewTitulaireError] = useState('')
  const [newEtablissementError, setNewEtablissementError] = useState('')

  const createCompte = useCreateResource('comptes')
  const updateCompte = useUpdateResource('comptes')
  const createTitulaire = useCreateTitulaire()
  const createEtablissement = useCreateEtablissement()

  const { options: typesCompteOpts } = useTypesCompte()
  const { options: titulairesOpts } = useTitulaires()
  const { options: etablissementsOpts } = useEtablissements()
  const { options: devisesOpts } = useDevises()

  useEffect(() => {
    if (!isOpen) return
    if (isEdit && compte) {
      setCode(compte.code ?? '')
      setNom(compte.nom ?? '')
      setTypeCompte(compte.type_compte ?? '')
      setTitulaire(compte.titulaire ?? '')
      setEtablissement(compte.etablissement ?? '')
      setDevise(compte.devise ?? '')
      setSoldeInitial(String(compte.solde_initial ?? '0'))
      setActif(compte.actif ?? true)
      setEstCommun(compte.est_commun ?? false)
      setDateOuverture(compte.date_ouverture ?? '')
      setNotes(compte.notes ?? '')
    } else {
      setCode('')
      setNom('')
      setTypeCompte('')
      setTitulaire('')
      setEtablissement('')
      setDevise('')
      setSoldeInitial('0')
      setActif(true)
      setEstCommun(false)
      setDateOuverture('')
      setNotes('')
    }
    setErrors({})
    setNewTitulaireError('')
    setNewEtablissementError('')
  }, [isOpen, isEdit, compte])

  const parseDecimal = (s) => parseFloat(String(s).replace(',', '.')) || 0

  const validate = () => {
    const e = {}
    if (!code.trim()) e.code = 'Code requis.'
    if (!nom.trim()) e.nom = 'Nom requis.'
    if (!typeCompte) e.type_compte = 'Type de compte requis.'
    if (!titulaire) e.titulaire = 'Titulaire requis.'
    if (!etablissement) e.etablissement = 'Établissement requis.'
    if (!devise) e.devise = 'Devise requise.'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = () => {
    if (!validate()) return
    const payload = {
      code: code.trim(),
      nom: nom.trim(),
      type_compte: typeCompte,
      titulaire,
      etablissement,
      devise,
      solde_initial: parseDecimal(soldeInitial).toFixed(2),
      actif,
      est_commun: estCommun,
      date_ouverture: dateOuverture || null,
      notes,
    }
    const mutation = isEdit ? updateCompte : createCompte
    const mutateArg = isEdit ? { id: compte.id, payload } : payload
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

  const handleCreateTitulaire = (libelle, closeForm) => {
    setNewTitulaireError('')
    createTitulaire.mutate({ libelle }, {
      onSuccess: (data) => { setTitulaire(String(data.id)); closeForm() },
      onError: (err) => {
        const d = err.response?.data || {}
        setNewTitulaireError(d.libelle?.[0] || d.detail || 'Erreur lors de la création.')
      },
    })
  }

  const handleCreateEtablissement = (libelle, closeForm) => {
    setNewEtablissementError('')
    createEtablissement.mutate({ libelle }, {
      onSuccess: (data) => { setEtablissement(String(data.id)); closeForm() },
      onError: (err) => {
        const d = err.response?.data || {}
        setNewEtablissementError(d.libelle?.[0] || d.detail || 'Erreur lors de la création.')
      },
    })
  }

  const isPending = createCompte.isPending || updateCompte.isPending

  const titulaireCreate = {
    Component: ({ onSave, onCancel, isPending: ip, error }) => (
      <InlineCreate placeholder="Ex : Pierre Dupont" onSave={onSave} onCancel={onCancel} isPending={ip} error={error} />
    ),
    save: handleCreateTitulaire,
    isPending: createTitulaire.isPending,
    error: newTitulaireError,
  }

  const etablissementCreate = {
    Component: ({ onSave, onCancel, isPending: ip, error }) => (
      <InlineCreate placeholder="Ex : BNP Paribas" onSave={onSave} onCancel={onCancel} isPending={ip} error={error} />
    ),
    save: handleCreateEtablissement,
    isPending: createEtablissement.isPending,
    error: newEtablissementError,
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? 'Modifier le compte' : 'Nouveau compte'}
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
        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Code" value={code} onChange={setCode}
            placeholder="CPT-0001" error={errors.code} required
          />
          <Input
            label="Nom" value={nom} onChange={setNom}
            placeholder="Compte courant" error={errors.nom} required
          />
        </div>

        <Select
          label="Type de compte" value={typeCompte} onChange={setTypeCompte}
          options={typesCompteOpts} error={errors.type_compte} required
        />

        <SelectWithCreate
          label="Titulaire" value={titulaire} onChange={setTitulaire}
          options={titulairesOpts} error={errors.titulaire} required
          onCreate={titulaireCreate}
        />

        <SelectWithCreate
          label="Établissement" value={etablissement} onChange={setEtablissement}
          options={etablissementsOpts} error={errors.etablissement} required
          onCreate={etablissementCreate}
        />

        <Select
          label="Devise" value={devise} onChange={setDevise}
          options={devisesOpts} error={errors.devise} required
        />

        <Input
          label="Solde initial (€)" type="text" inputMode="decimal"
          value={soldeInitial} onChange={setSoldeInitial}
          placeholder="0,00"
        />

        <Input
          label="Date d'ouverture" type="date"
          value={dateOuverture} onChange={setDateOuverture}
        />

        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-content-2">Notes</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Informations complémentaires…"
            rows={3}
            className="w-full px-3 py-2 rounded-lg border border-border-app bg-surface text-sm text-content outline-none focus:border-purple-600 resize-none"
          />
        </div>

        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={estCommun}
            onChange={(e) => setEstCommun(e.target.checked)}
            className="w-4 h-4 accent-purple-600"
          />
          <span className="text-sm text-content">Compte commun (partagé du foyer)</span>
        </label>

        {isEdit && (
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={actif}
              onChange={(e) => setActif(e.target.checked)}
              className="w-4 h-4 accent-purple-600"
            />
            <span className="text-sm text-content">Compte actif</span>
          </label>
        )}
      </div>
    </Modal>
  )
}

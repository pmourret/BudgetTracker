import { useState, useEffect } from 'react'
import { useCreateResource, useUpdateResource, useResourceList } from '../../hooks/useResource'
import {
  useTypesFlux, useModesPaiement, useStatutsFlux, useDevises,
} from '../../hooks/useReferentiels'
import Modal from '../ui/Modal'
import Input from '../ui/Input'
import Select from '../ui/Select'
import Button from '../ui/Button'

function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

function shiftDate(iso, days) {
  const d = new Date(iso)
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

export default function FluxFormModal({ isOpen, onClose, flux = null }) {
  const isEdit = Boolean(flux)

  const [sens, setSens] = useState('depense')
  const [montant, setMontant] = useState('')
  const [libelle, setLibelle] = useState('')
  const [compte, setCompte] = useState('')
  const [categorie, setCategorie] = useState('')
  const [dateFlux, setDateFlux] = useState(todayISO())
  const [modePaiement, setModePaiement] = useState('')
  const [statut, setStatut] = useState('')
  const [errors, setErrors] = useState({})

  const createFlux = useCreateResource('flux')
  const updateFlux = useUpdateResource('flux')
  const { data: comptesData } = useResourceList('comptes')
  const { data: categoriesData } = useResourceList('categories')
  const { data: typesFluxData } = useTypesFlux()
  const { options: modesPaiementOpts } = useModesPaiement()
  const { options: statutsOpts } = useStatutsFlux()
  const { data: devises } = useDevises()

  const comptesOpts = (comptesData?.results ?? []).map((c) => ({
    value: c.id,
    label: c.etablissement_libelle ? `${c.nom} — ${c.etablissement_libelle}` : c.nom,
  }))

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

  useEffect(() => {
    if (!isOpen) return
    if (isEdit && flux) {
      const m = Number(flux.montant)
      setSens(m < 0 ? 'depense' : 'recette')
      setMontant(String(Math.abs(m)))
      setLibelle(flux.libelle ?? '')
      setCompte(flux.compte ? String(flux.compte) : '')
      setCategorie(flux.categorie ? String(flux.categorie) : '')
      setDateFlux(flux.date_flux ?? todayISO())
      setModePaiement(flux.mode_paiement ? String(flux.mode_paiement) : '')
      setStatut(flux.statut ? String(flux.statut) : '')
    } else {
      setSens('depense'); setMontant(''); setLibelle(''); setCategorie('')
      setCompte(''); setDateFlux(todayISO())
      setModePaiement(''); setStatut('')
    }
    setErrors({})
  }, [isOpen, isEdit, flux])

  const typeFluxId = (typesFluxData ?? []).find(
    (t) => t.code === (sens === 'depense' ? 'DEBIT' : 'CREDIT')
  )?.id ?? null

  const montantNum = parseFloat(montant.replace(',', '.')) || 0
  const montantSigne = sens === 'depense' ? -Math.abs(montantNum) : Math.abs(montantNum)

  const validate = () => {
    const e = {}
    if (!montantNum || montantNum <= 0) e.montant = 'Montant requis (> 0).'
    if (!libelle.trim()) e.libelle = 'Libellé requis.'
    if (!compte) e.compte = 'Compte requis.'
    if (sens === 'depense' && !categorie) e.categorie = 'Catégorie requise pour une dépense.'
    if (!statut) e.statut = 'Statut requis.'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = () => {
    if (!validate()) return

    const payload = {
      compte,
      categorie: categorie || null,
      type_flux: typeFluxId,
      mode_paiement: modePaiement || null,
      statut,
      montant: montantSigne.toFixed(2),
      date_flux: dateFlux,
      libelle: libelle.trim(),
    }

    if (!isEdit) {
      const deviseDefaut = (devises ?? []).find((d) => d.est_defaut) || (devises ?? [])[0]
      payload.devise = deviseDefaut?.id
      payload.est_transfert = false
    }

    const mutation = isEdit ? updateFlux : createFlux
    const mutateArg = isEdit ? { id: flux.id, payload } : payload

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

  const isPending = createFlux.isPending || updateFlux.isPending

  if (isEdit && flux?.est_transfert) {
    return (
      <Modal isOpen={isOpen} onClose={onClose} title="Modifier le flux"
        footer={<Button variant="secondary" onClick={onClose}>Fermer</Button>}
      >
        <p className="text-sm text-content-2">
          Ce flux fait partie d'un transfert. Modifiez-le depuis la page{' '}
          <strong className="text-content">Transferts</strong>.
        </p>
      </Modal>
    )
  }

  if (isEdit && flux?.est_ajustement) {
    return (
      <Modal isOpen={isOpen} onClose={onClose} title="Flux d'ajustement"
        footer={<Button variant="secondary" onClick={onClose}>Fermer</Button>}
      >
        <p className="text-sm text-content-2">
          Ce flux a été généré automatiquement par la réconciliation de solde.
          Il ne peut pas être modifié manuellement.
        </p>
      </Modal>
    )
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? 'Modifier le flux' : 'Nouveau flux'}
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
        {/* Toggle dépense / recette */}
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

        {/* Montant */}
        <div className="flex flex-col gap-1">
          <Input
            label="Montant (€)" type="text" inputMode="decimal"
            value={montant} onChange={setMontant} placeholder="0,00"
            error={errors.montant} required
          />
          {montantNum > 0 && (
            <span className="text-xs text-content-2">
              Sera enregistré : {montantSigne.toFixed(2).replace('.', ',')} €
            </span>
          )}
        </div>

        <Input
          label="Libellé" value={libelle} onChange={setLibelle}
          placeholder="Ex : Courses Leclerc" error={errors.libelle} required
        />
        <Select
          label="Compte" value={compte} onChange={setCompte}
          options={comptesOpts} error={errors.compte} required
        />
        <Select
          label="Catégorie" value={categorie} onChange={setCategorie}
          options={categoriesOpts} groups={categoriesGroups}
          error={errors.categorie}
          required={sens === 'depense'}
        />

        {/* Date */}
        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-content-2">Date</label>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setDateFlux(shiftDate(dateFlux, -1))}
              aria-label="Jour précédent"
              className="w-10 h-10 rounded-lg border border-border-app bg-surface text-content-2 text-lg cursor-pointer shrink-0 hover:bg-surface-3"
            >
              −
            </button>
            <input
              type="date"
              value={dateFlux}
              onChange={(e) => setDateFlux(e.target.value)}
              className="flex-1 h-10 px-3 rounded-lg border border-border-app bg-surface text-sm text-content outline-none focus:border-purple-600"
            />
            <button
              type="button"
              onClick={() => setDateFlux(shiftDate(dateFlux, 1))}
              aria-label="Jour suivant"
              className="w-10 h-10 rounded-lg border border-border-app bg-surface text-content-2 text-lg cursor-pointer shrink-0 hover:bg-surface-3"
            >
              +
            </button>
          </div>
        </div>

        <Select
          label="Mode de paiement" value={modePaiement} onChange={setModePaiement}
          options={modesPaiementOpts} placeholder="Optionnel"
        />
        <Select
          label="Statut" value={statut} onChange={setStatut}
          options={statutsOpts} error={errors.statut} required
        />
      </div>
    </Modal>
  )
}

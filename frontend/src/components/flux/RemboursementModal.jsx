import { useEffect, useState } from 'react'
import Modal from '../ui/Modal'
import Button from '../ui/Button'
import Input from '../ui/Input'
import { useRembourserFlux } from '../../hooks/useResource'
import { formatEuro, formatDate } from '../../utils/format'

const aujourdhui = () => new Date().toISOString().slice(0, 10)

// Reste à rembourser d'une dépense = |montant| − Σ remboursements déjà reçus.
const resteARembourser = (flux) => {
  const total = Math.abs(Number(flux?.montant || 0))
  const deja = Number(flux?.montant_rembourse || 0)
  return Math.max(0, total - deja)
}

/**
 * Mini-modal de remboursement d'une dépense : crée un contre-flux recette lié.
 * Pré-remplie (montant = reste à rembourser, date = aujourd'hui), ajustable →
 * gère nativement les remboursements partiels et la vraie date du crédit bancaire.
 */
export default function RemboursementModal({ flux, onClose, onDone }) {
  const [montant, setMontant] = useState('')
  const [date, setDate] = useState(aujourdhui())
  const [libelle, setLibelle] = useState('')
  const [error, setError] = useState('')

  const rembourser = useRembourserFlux()

  useEffect(() => {
    if (flux) {
      setMontant(String(resteARembourser(flux).toFixed(2)))
      setDate(aujourdhui())
      setLibelle('')
      setError('')
    }
  }, [flux])

  if (!flux) return null

  const reste = resteARembourser(flux)

  const handleSubmit = () => {
    setError('')
    const val = Number(montant)
    if (!val || val <= 0) {
      setError('Saisissez un montant positif.')
      return
    }
    if (val > reste + 0.001) {
      setError(`Le montant dépasse le reste à rembourser (${formatEuro(reste)}).`)
      return
    }
    if (!date) {
      setError('Choisissez la date du remboursement.')
      return
    }
    rembourser.mutate(
      { fluxId: flux.id, montant: val.toFixed(2), date, libelle: libelle || undefined },
      {
        onSuccess: () => onDone?.(),
        onError: (err) =>
          setError(err.response?.data?.detail || 'Remboursement impossible.'),
      }
    )
  }

  return (
    <Modal
      isOpen={!!flux}
      onClose={onClose}
      title="Enregistrer un remboursement"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Annuler</Button>
          <Button variant="primary" onClick={handleSubmit} disabled={rembourser.isPending}>
            {rembourser.isPending ? 'Enregistrement…' : 'Enregistrer le remboursement'}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {/* Récap de la dépense d'origine */}
        <div className="rounded-lg bg-surface-3 px-4 py-3">
          <div className="text-sm font-medium text-content">{flux.libelle || '—'}</div>
          <div className="flex justify-between mt-1 text-xs text-content-2">
            <span>{flux.compte_nom} · {formatDate(flux.date_flux)}</span>
            <span className="text-red-600">{formatEuro(flux.montant)}</span>
          </div>
          {Number(flux.montant_rembourse || 0) > 0 && (
            <div className="mt-1 text-xs text-content-2">
              Déjà remboursé : {formatEuro(flux.montant_rembourse)} · reste{' '}
              <strong>{formatEuro(reste)}</strong>
            </div>
          )}
        </div>

        <Input
          label="Montant reçu" type="number" step="0.01" min="0"
          value={montant} onChange={setMontant} required
        />
        <Input
          label="Date du remboursement" type="date"
          value={date} onChange={setDate} required
        />
        <Input
          label="Libellé (optionnel)" value={libelle} onChange={setLibelle}
          placeholder={`Remboursement — ${flux.libelle || 'dépense'}`}
        />
        {error && <span className="text-xs text-red-600">{error}</span>}

        <p className="text-xs text-content-2 leading-relaxed">
          Une <strong>recette</strong> sera créée sur <strong>{flux.compte_nom}</strong>,
          dans la même catégorie, en statut validé. Le solde du compte est recalculé,
          et les deux lignes se rapprocheront naturellement de votre relevé bancaire.
        </p>
      </div>
    </Modal>
  )
}

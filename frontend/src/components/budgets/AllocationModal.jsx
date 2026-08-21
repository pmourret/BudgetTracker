import { useState, useEffect } from 'react'
import { Minus, Plus, Coins } from 'lucide-react'
import { useResourceAction } from '../../hooks/useResource'
import { formatEuro } from '../../utils/format'
import Modal from '../ui/Modal'
import Button from '../ui/Button'

// Distribution manuelle de points (mécanique B, 12-B-2). Gonfle le prévu
// effectif d'une enveloppe en jeu et se déduit de la réserve. Plafonné au
// disponible (le backend re-valide de toute façon).
export default function AllocationModal({
  isOpen,
  onClose,
  budget,
  soldeDisponible = 0,
  valeurPoint = 10,
}) {
  const allouer = useResourceAction('budgets')
  const [points, setPoints] = useState(0)
  const [error, setError] = useState(null)

  const dejaAlloue = Number(budget?.points_alloues ?? 0)
  const maxAllouable = Math.max(0, soldeDisponible + dejaAlloue)

  useEffect(() => {
    if (isOpen) {
      setPoints(dejaAlloue)
      setError(null)
    }
  }, [isOpen, dejaAlloue])

  if (!budget) return null

  const libelle = budget.libelle ?? budget.categorie_nom
  const base = Number(budget.montant_prevu)
  const prevuEffectif = base + points * valeurPoint
  const reserveApres = soldeDisponible + dejaAlloue - points

  const clamp = (v) => Math.max(0, Math.min(maxAllouable, v))
  const setClamped = (v) => {
    setError(null)
    setPoints(clamp(v))
  }

  const handleSave = () => {
    setError(null)
    allouer.mutate(
      { id: budget.id, action: 'allouer', payload: { points } },
      {
        onSuccess: () => onClose(),
        onError: (err) => {
          const data = err.response?.data || {}
          setError(Array.isArray(data.points) ? data.points[0] : data.points || 'Échec de l’allocation.')
        },
      }
    )
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <span className="inline-flex items-center gap-1.5">
          <Coins size={16} className="text-teal-texte" />
          Distribuer des points
        </span>
      }
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Annuler</Button>
          <Button variant="primary" onClick={handleSave} disabled={allouer.isPending || points === dejaAlloue}>
            {allouer.isPending ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div>
          <div className="text-sm font-medium text-content">{libelle}</div>
          <div className="text-xs text-content-3 mt-0.5">
            Réserve disponible : <strong>{soldeDisponible} pt{Math.abs(soldeDisponible) > 1 ? 's' : ''}</strong>
            {' '}· 1 point = {formatEuro(valeurPoint)}
          </div>
        </div>

        {/* Stepper */}
        <div className="flex items-center justify-center gap-3">
          <button
            type="button"
            onClick={() => setClamped(points - 1)}
            disabled={points <= 0}
            className="w-10 h-10 rounded-lg border border-border-app bg-surface text-content-2 cursor-pointer hover:bg-surface-3 flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed"
            aria-label="Retirer un point"
          >
            <Minus size={16} />
          </button>
          <div className="flex flex-col items-center min-w-[80px]">
            <input
              type="number"
              min={0}
              max={maxAllouable}
              value={points}
              onChange={(e) => setClamped(parseInt(e.target.value, 10) || 0)}
              className="w-20 text-center text-2xl font-semibold bg-transparent text-content outline-none"
            />
            <span className="text-xs text-content-3">/ {maxAllouable} max</span>
          </div>
          <button
            type="button"
            onClick={() => setClamped(points + 1)}
            disabled={points >= maxAllouable}
            className="w-10 h-10 rounded-lg border border-border-app bg-surface text-content-2 cursor-pointer hover:bg-surface-3 flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed"
            aria-label="Ajouter un point"
          >
            <Plus size={16} />
          </button>
        </div>

        {/* Aperçu */}
        <div className="rounded-lg bg-surface-2 border border-border-app px-3 py-2.5 flex flex-col gap-1.5 text-sm">
          <div className="flex justify-between">
            <span className="text-content-2">Prévu de base</span>
            <span className="text-content">{formatEuro(base)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-content-2">Bonus ({points} pt{Math.abs(points) > 1 ? 's' : ''})</span>
            <span className="text-teal-texte">+ {formatEuro(points * valeurPoint)}</span>
          </div>
          <div className="flex justify-between border-t border-border-app pt-1.5 font-medium">
            <span className="text-content">Prévu effectif</span>
            <span className="text-content">{formatEuro(prevuEffectif)}</span>
          </div>
          <div className="flex justify-between text-xs text-content-3">
            <span>Réserve après distribution</span>
            <span>{reserveApres} pt{Math.abs(reserveApres) > 1 ? 's' : ''}</span>
          </div>
        </div>

        {error && <p className="text-xs text-red-texte">{error}</p>}
      </div>
    </Modal>
  )
}

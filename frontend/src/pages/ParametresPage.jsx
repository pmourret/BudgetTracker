import { useEffect, useState } from 'react'
import { CalendarRange, Check, AlertTriangle } from 'lucide-react'
import Card from '../components/ui/Card'
import Select from '../components/ui/Select'
import Button from '../components/ui/Button'
import Tooltip from '../components/ui/Tooltip'
import { Loading, ErrorState } from '../components/ui/States'
import { DEFINITIONS } from '../constants/definitions'
import { useParametres, useUpdateParametres } from '../hooks/useParametres'

// Jour de bascule : 1 à 28 (borné à 28 côté backend pour rester valide
// tous les mois, février compris).
const JOURS = Array.from({ length: 28 }, (_, i) => {
  const j = i + 1
  return {
    value: String(j),
    label: j === 1 ? '1 — mois calendaire (par défaut)' : String(j),
  }
})

function exemplePeriode(jour) {
  if (jour <= 1) {
    return 'Mois calendaire : chaque mois va du 1ᵉʳ au dernier jour.'
  }
  const fin = jour - 1
  return (
    `La période du ${jour} d'un mois au ${fin} du mois suivant est ` +
    `comptabilisée sur le mois suivant. Exemple : un mouvement daté du ` +
    `${jour} juin appartient au mois de juillet.`
  )
}

export default function ParametresPage() {
  const { data, isLoading, isError, refetch } = useParametres()
  const update = useUpdateParametres()

  const [jour, setJour] = useState(null)
  const [feedback, setFeedback] = useState(null)

  useEffect(() => {
    if (data) setJour(data.jour_debut_mois_comptable)
  }, [data])

  const jourNum = Number(jour)
  const initial = data?.jour_debut_mois_comptable
  const dirty = jour != null && jourNum !== initial

  function handleSave() {
    setFeedback(null)
    update.mutate(
      { jour_debut_mois_comptable: jourNum },
      {
        onSuccess: () =>
          setFeedback({
            type: 'success',
            msg: 'Mois comptable mis à jour. Tous les flux ont été recalculés.',
          }),
        onError: () =>
          setFeedback({
            type: 'error',
            msg: "La mise à jour a échoué. Vérifiez la valeur (1 à 28).",
          }),
      }
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-lg font-medium text-content">Paramètres</h1>
        <p className="text-sm text-content-2 mt-0.5">
          Réglages du foyer appliqués à toute l'application
        </p>
      </div>

      {isLoading && <Loading message="Chargement des paramètres…" />}
      {isError && (
        <ErrorState message="Impossible de charger les paramètres." onRetry={refetch} />
      )}

      {!isLoading && !isError && (
        <Card
          title={
            <span className="inline-flex items-center gap-1.5">
              <CalendarRange size={16} className="text-content-2" />
              Mois comptable
              <Tooltip {...DEFINITIONS.mois_comptable} align="left" />
            </span>
          }
        >
          <div className="flex flex-col gap-4 max-w-md">
            <p className="text-sm text-content-2 leading-relaxed">
              Choisissez le jour où débute votre mois budgétaire. Si vous
              percevez votre salaire en fin de mois, réglez-le sur ce jour pour
              que le salaire et les dépenses qu'il finance restent dans le même
              mois.
            </p>

            <Select
              label="Jour de début du mois comptable"
              value={jour != null ? String(jour) : ''}
              onChange={(v) => {
                setJour(Number(v))
                setFeedback(null)
              }}
              options={JOURS}
              placeholder="Sélectionner un jour…"
            />

            <div className="rounded-lg bg-surface-2 border border-border-app px-3 py-2.5">
              <span className="text-xs text-content-2 leading-relaxed">
                {exemplePeriode(jourNum)}
              </span>
            </div>

            {dirty && (
              <div className="flex items-start gap-2 text-xs text-amber-600">
                <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                <span>
                  Changer ce réglage recalcule le mois de tout l'historique des
                  flux (soldes et budgets compris). L'opération est immédiate.
                </span>
              </div>
            )}

            <div className="flex items-center gap-3">
              <Button
                onClick={handleSave}
                disabled={!dirty || update.isPending}
              >
                {update.isPending ? 'Enregistrement…' : 'Enregistrer'}
              </Button>
              {feedback && (
                <span
                  className={[
                    'inline-flex items-center gap-1.5 text-xs',
                    feedback.type === 'success'
                      ? 'text-green-600'
                      : 'text-red-600',
                  ].join(' ')}
                >
                  {feedback.type === 'success' && <Check size={14} />}
                  {feedback.msg}
                </span>
              )}
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}

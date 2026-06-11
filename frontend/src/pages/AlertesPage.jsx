import { useState } from 'react'
import { useResourceList, useResourceAction } from '../hooks/useResource'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import { Loading, ErrorState, EmptyState } from '../components/ui/States'

const NIVEAU_CONFIG = {
  CRITIQUE:      { label: 'Critique',      variant: 'critique',      bar: 'bg-red-600' },
  AVERTISSEMENT: { label: 'Avertissement', variant: 'avertissement', bar: 'bg-amber-600' },
  INFO:          { label: 'Information',   variant: 'info',          bar: 'bg-blue-600' },
}

const FILTRES = [
  { key: 'toutes',        label: 'Toutes' },
  { key: 'non_acquittee', label: 'Non acquittées' },
  { key: 'critiques',     label: 'Critiques' },
]

export default function AlertesPage() {
  const [filtre, setFiltre] = useState('non_acquittee')

  const params = {}
  if (filtre === 'non_acquittee') params.acquittee = false
  if (filtre === 'critiques') params.niveau = 'CRITIQUE'

  const { data, isLoading, isError, refetch } = useResourceList('alertes', params)
  const acquitterAction = useResourceAction('alertes')

  const alertes = data?.results ?? []
  const nbNonAcquittees = alertes.filter((a) => !a.acquittee).length

  const handleAcquitter = (id) => acquitterAction.mutate({ id, action: 'acquitter' })
  const handleAcquitterTout = () => acquitterAction.mutate({ action: 'acquitter-tout' })

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-lg font-medium text-content">Alertes</h1>
          <p className="text-sm text-content-2 mt-0.5">
            {nbNonAcquittees} alerte{nbNonAcquittees > 1 ? 's' : ''} non acquittée{nbNonAcquittees > 1 ? 's' : ''}
          </p>
        </div>
        {nbNonAcquittees > 0 && (
          <Button variant="secondary" onClick={handleAcquitterTout}>
            Tout acquitter
          </Button>
        )}
      </div>

      <div className="flex gap-2 flex-wrap">
        {FILTRES.map((f) => (
          <button
            key={f.key}
            onClick={() => setFiltre(f.key)}
            className={[
              'h-[30px] px-3 rounded-full border text-xs cursor-pointer',
              filtre === f.key
                ? 'bg-purple-50 border-purple-600 text-purple-800 font-medium'
                : 'bg-surface border-border-app text-content-2 font-normal',
            ].join(' ')}
          >
            {f.label}
          </button>
        ))}
      </div>

      {isLoading && <Loading message="Chargement des alertes..." />}
      {isError && <ErrorState message="Impossible de charger les alertes." onRetry={refetch} />}

      {!isLoading && !isError && alertes.length === 0 && (
        <EmptyState
          icon="🔔"
          message={
            filtre === 'non_acquittee'
              ? 'Aucune alerte en attente. Tout est sous contrôle.'
              : 'Aucune alerte à afficher.'
          }
        />
      )}

      {!isLoading && !isError && alertes.length > 0 && (
        <div className="flex flex-col gap-2">
          {alertes.map((alerte) => (
            <AlerteCard
              key={alerte.id}
              alerte={alerte}
              onAcquitter={() => handleAcquitter(alerte.id)}
              isPending={acquitterAction.isPending}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function AlerteCard({ alerte, onAcquitter, isPending }) {
  const config = NIVEAU_CONFIG[alerte.niveau] || NIVEAU_CONFIG.INFO

  return (
    <Card bodyClassName="p-0">
      <div className="flex gap-3 items-stretch">
        <div className={`w-[3px] shrink-0 rounded-l-xl ${config.bar}`} />
        <div
          className={[
            'flex-1 py-4 pr-5 pl-0 flex justify-between items-start gap-3',
            alerte.acquittee ? 'opacity-55' : '',
          ].join(' ')}
        >
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm font-medium text-content">
                {alerte.type_alerte_display}
              </span>
              <Badge variant={config.variant}>{config.label}</Badge>
            </div>
            <div className="text-sm text-content-2 leading-normal">
              {alerte.explication}
            </div>
            <div className="text-[11px] text-content-3 mt-1.5">
              {new Date(alerte.created_at).toLocaleDateString('fr-FR', {
                day: '2-digit', month: 'long', year: 'numeric',
                hour: '2-digit', minute: '2-digit',
              })}
            </div>
          </div>
          <div className="shrink-0">
            {alerte.acquittee ? (
              <span className="text-xs text-teal-600 flex items-center gap-1">
                ✓ Acquittée
              </span>
            ) : (
              <button
                onClick={onAcquitter}
                disabled={isPending}
                className="h-8 px-3 rounded-lg bg-surface border border-border-app text-xs font-medium text-purple-600 dark:text-purple-400 cursor-pointer hover:bg-surface-3 disabled:cursor-not-allowed"
              >
                Acquitter
              </button>
            )}
          </div>
        </div>
      </div>
    </Card>
  )
}
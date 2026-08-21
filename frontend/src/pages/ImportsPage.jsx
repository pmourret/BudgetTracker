import { useState } from 'react'
import {
  Upload, RefreshCw, ChevronDown, ChevronRight, Check, X,
  AlertTriangle, CheckCircle2, FileText, Trash2, FilePlus, FileUp
} from 'lucide-react'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Tooltip from '../components/ui/Tooltip'
import { DEFINITIONS } from '../constants/definitions'
import { Loading, ErrorState, EmptyState } from '../components/ui/States'
import { formatEuro, formatDate } from '../utils/format'
import {
  useImportsList, useRapport, useValiderLigne, useRejeterLigne,
  useRelancerRapprochement, useDeleteImport,
} from '../hooks/useImports'
import ImportUploadModal from '../components/imports/ImportUploadModal'
import CreerMouvementModal from '../components/imports/CreerMouvementModal'

const MONTANT_CLASS = (m) => (Number(m) < 0 ? 'text-red-texte' : 'text-teal-texte')

export default function ImportsPage() {
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedLot, setSelectedLot] = useState(null)

  const { data: lotsData, isLoading, isError, refetch } = useImportsList()
  const lots = lotsData?.results ?? []

  const handleImported = (data) => {
    setModalOpen(false)
    if (data?.lot?.id) setSelectedLot(data.lot.id)
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-lg font-medium text-content">Rapprochement bancaire</h1>
          <p className="text-sm text-content-2 mt-0.5">
            Comparez un relevé à vos flux pour repérer oublis et erreurs de saisie
          </p>
        </div>
        <Button variant="primary" onClick={() => setModalOpen(true)}>
          <span className="inline-flex items-center gap-1.5"><Upload size={15} /> Importer</span>
        </Button>
      </div>

      <div className="rounded-lg bg-blue-600/15 text-content text-xs px-4 py-2.5 leading-relaxed">
        Le relevé sert de <strong>contrôle</strong> : il ne modifie jamais un flux
        existant. Ce qui lui manque se crée d'ici — dépense, recette ou{' '}
        <strong>virement interne</strong> — et l'application reste la seule vérité
        comptable.
      </div>

      {isLoading && <Loading message="Chargement des imports…" />}
      {isError && <ErrorState message="Impossible de charger les imports." onRetry={refetch} />}

      {!isLoading && !isError && (
        lots.length === 0 ? (
          <EmptyState
            Icon={FileUp}
            message="Aucun relevé importé pour l'instant."
            action={<Button variant="primary" onClick={() => setModalOpen(true)}>Importer un relevé</Button>}
          />
        ) : (
          <>
            <div className="flex flex-col gap-2">
              {lots.map((lot) => (
                <LotCard
                  key={lot.id}
                  lot={lot}
                  selected={selectedLot === lot.id}
                  onSelect={() => setSelectedLot(selectedLot === lot.id ? null : lot.id)}
                  onDeleted={() => setSelectedLot((cur) => (cur === lot.id ? null : cur))}
                />
              ))}
            </div>

            {selectedLot && <RapportView lotId={selectedLot} />}
          </>
        )
      )}

      <ImportUploadModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onImported={handleImported}
      />
    </div>
  )
}

function LotCard({ lot, selected, onSelect, onDeleted }) {
  const deleteImport = useDeleteImport()

  const handleDelete = (e) => {
    e.stopPropagation()
    if (!window.confirm(
      `Supprimer cet import (${lot.compte_nom} · ${lot.nom_fichier || lot.banque}) ? ` +
      `Le rapprochement est perdu, mais aucun flux n'est touché.`
    )) return
    deleteImport.mutate(lot.id, { onSuccess: () => onDeleted?.() })
  }

  return (
    <div
      onClick={onSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect() } }}
      className={[
        'w-full text-left bg-surface border rounded-xl px-4 py-3 flex items-center gap-3 cursor-pointer transition-colors',
        selected ? 'border-purple-600' : 'border-border-app hover:bg-surface-3',
      ].join(' ')}
    >
      <FileText size={18} className="text-content-2 shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-content truncate">
          {lot.compte_nom} · {lot.nom_fichier || lot.banque}
        </div>
        <div className="text-xs text-content-2">
          {formatDate(lot.created_at)} · {lot.nb_lignes} ligne{lot.nb_lignes > 1 ? 's' : ''}
          {lot.nb_doublons_ignores > 0 && ` · ${lot.nb_doublons_ignores} doublon(s) ignoré(s)`}
        </div>
      </div>
      <div className="flex items-center gap-1.5 shrink-0">
        {lot.nb_ambigus > 0 && <Badge variant="info">{lot.nb_ambigus} à valider</Badge>}
        {lot.nb_manquants_app > 0 && <Badge variant="avertissement">{lot.nb_manquants_app} écart(s)</Badge>}
        {lot.nb_rapproches > 0 && <Badge variant="success">{lot.nb_rapproches} ✓</Badge>}
        <button
          onClick={handleDelete}
          disabled={deleteImport.isPending}
          title="Supprimer l'import"
          className="p-1.5 rounded-md text-content-2 hover:text-red-texte hover:bg-red-50 cursor-pointer disabled:opacity-50"
        >
          <Trash2 size={14} />
        </button>
        {selected ? <ChevronDown size={16} className="text-content-3" /> : <ChevronRight size={16} className="text-content-3" />}
      </div>
    </div>
  )
}

function RapportView({ lotId }) {
  const { data, isLoading, isError, refetch } = useRapport(lotId)
  const relancer = useRelancerRapprochement()
  const [creerFor, setCreerFor] = useState(null)
  // Un virement créé ici peut solder une ligne d'un AUTRE lot (le relevé du
  // compte d'en face). Sans un mot, cette écriture à distance serait invisible.
  const [miroirRapproche, setMiroirRapproche] = useState(null)

  if (isLoading) return <Loading message="Analyse du relevé…" />
  if (isError) return <ErrorState message="Impossible de charger le rapport." onRetry={refetch} />

  const lignes = data.lignes ?? []
  const orphelins = data.flux_sans_ligne ?? []

  const ambigus = lignes.filter((l) => l.statut === 'ambigu')
  const rapproches = lignes.filter((l) => l.statut === 'rapproche')
  const manquants = lignes.filter((l) => l.statut === 'manquant_app')
  const orphelinsErreur = orphelins.filter((f) => f.motif === 'erreur_saisie_probable')
  const orphelinsPrev = orphelins.filter((f) => f.motif === 'previsionnel_non_passe')

  const rienACorriger = ambigus.length === 0 && manquants.length === 0 && orphelinsErreur.length === 0

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-content-2">
          Tolérance de rapprochement : ± {data.tolerance_jours} jour(s)
        </span>
        <Button variant="ghost" onClick={() => relancer.mutate({ lotId })} disabled={relancer.isPending}>
          <span className="inline-flex items-center gap-1.5">
            <RefreshCw size={14} /> Relancer
          </span>
        </Button>
      </div>

      {data.controle_solde && <ControleSolde ctrl={data.controle_solde} />}

      {miroirRapproche && (
        <div className="rounded-lg bg-teal-600/15 text-content text-xs px-4 py-2.5 flex items-start gap-2 leading-relaxed">
          <CheckCircle2 size={15} className="shrink-0 mt-0.5 text-teal-texte" />
          <span>
            Virement créé. La ligne correspondante du relevé de{' '}
            <strong>{miroirRapproche}</strong> a été rapprochée dans la foulée.
          </span>
        </div>
      )}

      {rienACorriger && (
        <div className="rounded-lg bg-teal-50 text-teal-800 text-sm px-4 py-3 flex items-center gap-2">
          <CheckCircle2 size={18} /> Tout est rapproché : aucun écart à corriger.
        </div>
      )}

      {ambigus.length > 0 && (
        <Section title="À valider" count={ambigus.length} tone="info"
          hint="Plusieurs flux pourraient correspondre. Choisissez le bon, ou écartez-les.">
          <div className="flex flex-col gap-3">
            {ambigus.map((ligne) => <AmbiguRow key={ligne.id} ligne={ligne} />)}
          </div>
        </Section>
      )}

      {(manquants.length > 0 || orphelinsErreur.length > 0) && (
        <Section title="Écarts à corriger" count={manquants.length + orphelinsErreur.length} tone="warn"
          hint="Différences entre le relevé et l'application.">
          <div className="flex flex-col gap-4">
            {manquants.length > 0 && (
              <EcartGroupe titre="Sur le relevé, absent de l'application" sousTitre="Oubli de saisie probable — créez le mouvement (dépense, recette ou virement) en un clic.">
                {manquants.map((l) => (
                  <BankLine
                    key={l.id} ligne={l}
                    badge={<Badge variant="avertissement">Absent de l'app</Badge>}
                    onCreer={() => setCreerFor(l)}
                  />
                ))}
              </EcartGroupe>
            )}
            {orphelinsErreur.length > 0 && (
              <EcartGroupe titre="Dans l'application, absent du relevé" sousTitre="Erreur de saisie, ou opération pas encore passée en banque.">
                {orphelinsErreur.map((f) => (
                  <FluxLine key={f.id} flux={f} badge={<Badge variant="critique">Absent du relevé</Badge>} />
                ))}
              </EcartGroupe>
            )}
          </div>
        </Section>
      )}

      {orphelinsPrev.length > 0 && (
        <Section title="En attente (normal)" count={orphelinsPrev.length} tone="neutre"
          hint="Flux prévisionnels pas encore passés au relevé — rien à corriger.">
          <div className="flex flex-col gap-1.5">
            {orphelinsPrev.map((f) => (
              <FluxLine key={f.id} flux={f} badge={<Badge variant="neutre">Prévu</Badge>} />
            ))}
          </div>
        </Section>
      )}

      {rapproches.length > 0 && <Rapproches lignes={rapproches} />}

      <CreerMouvementModal
        ligne={creerFor}
        compteId={data.lot.compte}
        compteNom={data.lot.compte_nom}
        onClose={() => setCreerFor(null)}
        onCreated={(resultat) => {
          setCreerFor(null)
          setMiroirRapproche(
            resultat?.ligne_miroir ? resultat.contrepartie_nom : null
          )
        }}
      />
    </div>
  )
}

function ControleSolde({ ctrl }) {
  const coherent = ctrl.coherent
  const cls = coherent
    ? 'bg-teal-50 text-teal-800'
    : 'bg-amber-50 text-amber-800'
  return (
    <div className={`rounded-lg px-4 py-3 ${cls}`}>
      <div className="flex items-center gap-1.5 text-sm font-medium">
        {coherent ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
        Solde de contrôle
        <Tooltip {...DEFINITIONS.controle_solde_import} align="left" size={13} />
      </div>
      <div className="flex flex-wrap gap-x-6 gap-y-1 mt-1.5 text-xs">
        <span>Application (actuel) : <strong>{formatEuro(ctrl.solde_app)}</strong></span>
        <span>Relevé (au {formatDate(ctrl.date_reference)}) : <strong>{formatEuro(ctrl.solde_banque)}</strong></span>
        <span>Écart : <strong>{formatEuro(ctrl.ecart)}</strong></span>
      </div>
      {!coherent && (
        <div className="text-[11px] mt-1.5 leading-relaxed">
          Le solde actuel de l'app diffère du dernier solde du relevé : soit une
          opération est non saisie ou mal saisie (voir les écarts ci-dessous),
          soit le relevé n'est pas à jour (mouvements survenus depuis le {formatDate(ctrl.date_reference)}).
        </div>
      )}
    </div>
  )
}

function Section({ title, count, hint, tone = 'neutre', children }) {
  const dot = {
    info: 'bg-blue-500', warn: 'bg-amber-500', neutre: 'bg-slate-400', ok: 'bg-teal-500',
  }[tone] || 'bg-slate-400'
  return (
    <Card>
      <div className="mb-3">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${dot}`} />
          <span className="text-sm font-medium text-content">{title}</span>
          <span className="text-xs text-content-3">({count})</span>
        </div>
        {hint && <p className="text-xs text-content-2 mt-1 ml-4">{hint}</p>}
      </div>
      {children}
    </Card>
  )
}

function EcartGroupe({ titre, sousTitre, children }) {
  return (
    <div>
      <div className="text-xs font-medium text-content mb-0.5">{titre}</div>
      <div className="text-[11px] text-content-2 mb-2">{sousTitre}</div>
      <div className="flex flex-col gap-1.5">{children}</div>
    </div>
  )
}

// Ligne de relevé bancaire (source = banque)
function BankLine({ ligne, badge, onCreer }) {
  return (
    <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-surface-3">
      <div className="flex-1 min-w-0">
        <div className="text-sm text-content truncate">{ligne.libelle}</div>
        <div className="text-xs text-content-2">{formatDate(ligne.date_operation)}</div>
      </div>
      <div className={`text-sm font-medium shrink-0 ${MONTANT_CLASS(ligne.montant)}`}>
        {formatEuro(ligne.montant)}
      </div>
      {badge}
      {onCreer && (
        <button
          onClick={onCreer}
          title="Créer le mouvement manquant"
          className="inline-flex items-center gap-1 text-xs font-medium text-purple-texte hover:underline cursor-pointer bg-transparent border-none shrink-0"
        >
          <FilePlus size={14} /> Créer
        </button>
      )}
    </div>
  )
}

// Ligne de flux applicatif (source = app)
function FluxLine({ flux, badge }) {
  return (
    <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-surface-3">
      <div className="flex-1 min-w-0">
        <div className="text-sm text-content truncate">
          {flux.libelle || flux.categorie_nom || 'Sans libellé'}
          {flux.est_transfert && <span className="ml-1.5 text-xs text-content-3">(transfert)</span>}
        </div>
        <div className="text-xs text-content-2">{formatDate(flux.date_flux)}</div>
      </div>
      <div className={`text-sm font-medium shrink-0 ${MONTANT_CLASS(flux.montant)}`}>
        {formatEuro(flux.montant)}
      </div>
      {badge}
    </div>
  )
}

function AmbiguRow({ ligne }) {
  const valider = useValiderLigne()
  const rejeter = useRejeterLigne()
  const busy = valider.isPending || rejeter.isPending

  return (
    <div className="rounded-lg border border-border-app p-3">
      <div className="flex items-center gap-3 mb-2">
        <AlertTriangle size={16} className="text-amber-500 shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-content truncate">{ligne.libelle}</div>
          <div className="text-xs text-content-2">{formatDate(ligne.date_operation)}</div>
        </div>
        <div className={`text-sm font-medium shrink-0 ${MONTANT_CLASS(ligne.montant)}`}>
          {formatEuro(ligne.montant)}
        </div>
      </div>

      <div className="text-xs text-content-2 mb-1.5 ml-7">Flux candidats :</div>
      <div className="flex flex-col gap-1.5 ml-7">
        {ligne.candidats.map((c) => (
          <div key={c.id} className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-surface-3">
            <div className="flex-1 min-w-0">
              <div className="text-sm text-content truncate">
                {c.libelle || c.categorie_nom || 'Sans libellé'}
              </div>
              <div className="text-xs text-content-2">
                {formatDate(c.date_flux)}
                {!c.est_definitif && ' · prévisionnel'}
              </div>
            </div>
            <span className={`text-sm shrink-0 ${MONTANT_CLASS(c.montant)}`}>{formatEuro(c.montant)}</span>
            <button
              onClick={() => valider.mutate({ ligneId: ligne.id, fluxId: c.id })}
              disabled={busy}
              title="C'est celui-ci"
              className="p-1.5 rounded-md text-teal-texte hover:bg-teal-50 cursor-pointer disabled:opacity-50"
            >
              <Check size={15} />
            </button>
          </div>
        ))}
        <button
          onClick={() => rejeter.mutate({ ligneId: ligne.id })}
          disabled={busy}
          className="self-start inline-flex items-center gap-1.5 text-xs text-content-2 hover:text-red-texte cursor-pointer bg-transparent border-none px-0 py-1 disabled:opacity-50"
        >
          <X size={13} /> Aucun ne correspond (marquer absent de l'app)
        </button>
      </div>
    </div>
  )
}

function Rapproches({ lignes }) {
  const [open, setOpen] = useState(false)
  return (
    <Card>
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 cursor-pointer bg-transparent border-none px-0"
      >
        <span className="w-2 h-2 rounded-full bg-teal-500" />
        <span className="text-sm font-medium text-content">Rapprochés</span>
        <span className="text-xs text-content-3">({lignes.length})</span>
        {open ? <ChevronDown size={16} className="ml-auto text-content-3" />
              : <ChevronRight size={16} className="ml-auto text-content-3" />}
      </button>
      {open && (
        <div className="flex flex-col gap-1.5 mt-3">
          {lignes.map((l) => (
            <BankLine key={l.id} ligne={l} badge={<Badge variant="success">Rapproché</Badge>} />
          ))}
        </div>
      )}
    </Card>
  )
}

import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useResourceList, useDeleteResource, useUpdateResource } from '../hooks/useResource'
import { formatEuro } from '../utils/format'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Tooltip from '../components/ui/Tooltip'
import { DEFINITIONS } from '../constants/definitions'
import { Loading, ErrorState, EmptyState } from '../components/ui/States'
import IconBadge from '../components/ui/IconBadge'
import Badge from '../components/ui/Badge'
import { Landmark, Pencil, Trash2, Users, BarChart3, PiggyBank, CreditCard } from 'lucide-react'
import CompteFormModal from '../components/comptes/CompteFormModal'
import Metric, { MetricRow } from '../components/ui/Metric'

export default function ComptesPage() {
  const { data, isLoading, isError, refetch } = useResourceList('comptes')
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedCompte, setSelectedCompte] = useState(null)

  const comptes = data?.results ?? []
  const totalTheorique = comptes.reduce((sum, c) => sum + Number(c.solde_theorique || 0), 0)
  const totalReel = comptes.reduce((sum, c) => sum + Number(c.solde_reel || 0), 0)
  const ecartTotal = totalReel - totalTheorique

  const openCreate = () => { setSelectedCompte(null); setModalOpen(true) }
  const openEdit = (compte) => { setSelectedCompte(compte); setModalOpen(true) }
  const closeModal = () => { setModalOpen(false); setSelectedCompte(null) }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-lg font-medium text-content">Comptes</h1>
          <p className="text-sm text-content-2 mt-0.5">
            {comptes.length} compte{comptes.length > 1 ? 's' : ''} actif{comptes.length > 1 ? 's' : ''}
          </p>
        </div>
        <Button variant="primary" onClick={openCreate}>+ Nouveau compte</Button>
      </div>

      {isLoading && <Loading message="Chargement des comptes..." />}
      {isError && <ErrorState message="Impossible de charger les comptes." onRetry={refetch} />}

      {!isLoading && !isError && (comptes.length === 0 ? (
        <EmptyState
          Icon={CreditCard}
          message="Aucun compte pour le moment."
          action={<Button variant="primary" onClick={openCreate}>Créer mon premier compte</Button>}
        />
      ) : (
        <>
          <MetricRow colonnes={3}>
            <Metric label="Solde théorique" value={formatEuro(totalTheorique)} def={DEFINITIONS.solde_theorique} />
            <Metric label="Solde confirmé" value={formatEuro(totalReel)} def={DEFINITIONS.solde_reel} />
            <Metric
              label="En attente"
              value={formatEuro(ecartTotal)}
              valueClass={ecartTotal === 0 ? 'text-teal-texte' : ecartTotal > 0 ? 'text-amber-texte' : 'text-teal-texte'}
              def={DEFINITIONS.ecart_solde}
              defAlign="right"
            />
          </MetricRow>

          {/* ⚠️ Tableau sur bureau, cartes sur mobile — même idiome
              qu'Abonnements. Trois comptes qu'on compare sur les mêmes cinq
              chiffres se lisent en colonnes alignées : en cartes juxtaposées,
              l'œil doit sauter horizontalement pour comparer deux valeurs qui
              devraient s'aligner verticalement.
              (D14 de la revue UI/UX du 2026-08-20.) */}
          {/* Le `hidden lg:block` porte sur la Card elle-même : posé à
              l'intérieur, elle se rendait quand même sur mobile — une boîte
              bordée vide au-dessus des cartes. */}
          <div className="hidden lg:block">
            <Card bodyClassName="p-0">
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-border-app">
                    <th className="text-left px-4 py-3 text-xs font-medium text-content-2">Compte</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-content-2">Établissement</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-content-2">Titulaire</th>
                    <th className="text-right px-4 py-3 text-xs font-medium text-content-2">
                      <span className="inline-flex items-center gap-1">
                        Solde théorique
                        <Tooltip {...DEFINITIONS.solde_theorique} align="right" size={12} />
                      </span>
                    </th>
                    <th className="text-right px-4 py-3 text-xs font-medium text-content-2">
                      <span className="inline-flex items-center gap-1">
                        Confirmé
                        <Tooltip {...DEFINITIONS.solde_reel} align="right" size={12} />
                      </span>
                    </th>
                    <th className="text-right px-4 py-3 text-xs font-medium text-content-2">
                      <span className="inline-flex items-center gap-1">
                        En attente
                        <Tooltip {...DEFINITIONS.ecart_solde} align="right" size={12} />
                      </span>
                    </th>
                    <th className="px-4 py-3 w-28"></th>
                  </tr>
                </thead>
                <tbody>
                  {comptes.map((compte) => (
                    <CompteLigne
                      key={compte.id}
                      compte={compte}
                      onEdit={() => openEdit(compte)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
            </Card>
          </div>

          <div className="lg:hidden grid grid-cols-1 sm:grid-cols-2 gap-3">
            {comptes.map((compte) => (
              <CompteCard
                key={compte.id}
                compte={compte}
                onEdit={() => openEdit(compte)}
              />
            ))}
          </div>
        </>
      ))}

      <CompteFormModal
        isOpen={modalOpen}
        onClose={closeModal}
        compte={selectedCompte}
      />
    </div>
  )
}


/**
 * Suppression et désactivation d'un compte — partagées par la ligne de tableau
 * et la carte mobile. Les dupliquer, c'est se préparer à ne les corriger qu'à
 * moitié.
 */
function useActionsCompte(compte) {
  const deleteCompte = useDeleteResource('comptes')
  const updateCompte = useUpdateResource('comptes')
  const [deleteError, setDeleteError] = useState(null)

  const handleDelete = () => {
    setDeleteError(null)
    if (!window.confirm(`Supprimer le compte « ${compte.nom} » ?`)) return
    deleteCompte.mutate(compte.id, {
      onError: (err) => {
        const msg = err.response?.data?.detail || 'Erreur lors de la suppression.'
        setDeleteError(msg)
      },
    })
  }

  const handleToggleActif = () => {
    const action = compte.actif ? 'désactiver' : 'réactiver'
    if (!window.confirm(`${action.charAt(0).toUpperCase() + action.slice(1)} le compte « ${compte.nom} » ?`)) return
    updateCompte.mutate({ id: compte.id, payload: { actif: !compte.actif } })
  }

  return { handleDelete, handleToggleActif, deleteError, deleteCompte }
}

/**
 * Badges d'un compte — commun, épargne. Identiques dans les deux rendus.
 */
function BadgesCompte({ compte }) {
  return (
    <>
      {compte.est_commun && (
        <Badge variant="purple">
          <span className="flex items-center gap-1">
            <Users size={11} /> Commun
          </span>
        </Badge>
      )}
      {compte.est_epargne && (
        <Badge variant="info">
          <span className="flex items-center gap-1">
            <PiggyBank size={11} /> Épargne
            {compte.taux_annuel != null && ` · ${String(compte.taux_annuel).replace('.', ',')} %`}
          </span>
        </Badge>
      )}
    </>
  )
}

/**
 * Une ligne du tableau des comptes (bureau).
 *
 * Porte exactement les mêmes chiffres que la carte mobile — et dans le même
 * ordre : théorique, confirmé, en attente. Deux ordres différents selon la
 * largeur obligeraient à relire l'étiquette à chaque comparaison.
 */
function CompteLigne({ compte, onEdit }) {
  const ecart = Number(compte.ecart_solde || 0)
  const { handleDelete, handleToggleActif, deleteError, deleteCompte } =
    useActionsCompte(compte)

  const tonEcart =
    ecart === 0 ? 'text-teal-texte' : ecart > 0 ? 'text-amber-texte' : 'text-teal-texte'

  return (
    <>
      <tr className="border-b border-border-app last:border-b-0 group">
        <td className="px-4 py-3">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="font-medium text-content">{compte.nom}</span>
            <BadgesCompte compte={compte} />
          </div>
          <div className="text-xs text-content-2">{compte.type_compte_libelle}</div>
        </td>
        <td className="px-4 py-3 text-content-2">{compte.etablissement_libelle || '—'}</td>
        <td className="px-4 py-3 text-content-2">{compte.titulaire_libelle || '—'}</td>
        <td className="px-4 py-3 text-right font-medium text-content">
          {formatEuro(compte.solde_theorique)}
        </td>
        <td className="px-4 py-3 text-right text-content">
          {formatEuro(compte.solde_reel)}
        </td>
        <td className={`px-4 py-3 text-right font-medium ${tonEcart}`}>
          {ecart !== 0
            ? ecart > 0
              ? `−${formatEuro(Math.abs(ecart))}`
              : `+${formatEuro(Math.abs(ecart))}`
            : formatEuro(0)}
        </td>
        <td className="px-4 py-3">
          <div className="actions-ligne flex gap-1 justify-end">
            <Link
              to={`/comptes/${compte.id}`}
              title="Voir les transactions"
              className="p-1.5 rounded-md text-content-2 hover:text-content hover:bg-surface-3 cursor-pointer"
            >
              <BarChart3 size={14} />
            </Link>
            <button
              onClick={onEdit}
              title="Modifier"
              className="p-1.5 rounded-md text-content-2 hover:text-content hover:bg-surface-3 cursor-pointer"
            >
              <Pencil size={14} />
            </button>
            <button
              onClick={handleDelete}
              title="Supprimer"
              disabled={deleteCompte.isPending}
              className="p-1.5 rounded-md text-content-2 hover:text-red-texte hover:bg-red-50 cursor-pointer disabled:opacity-50"
            >
              <Trash2 size={14} />
            </button>
          </div>
        </td>
      </tr>
      {deleteError && (
        <tr>
          <td colSpan={7} className="px-4 pb-3">
            <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
              {deleteError}
              <button
                onClick={handleToggleActif}
                className="ml-2 underline font-medium cursor-pointer"
              >
                Désactiver à la place
              </button>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

function CompteCard({ compte, onEdit }) {
  const ecart = Number(compte.ecart_solde || 0)
  const { handleDelete, handleToggleActif, deleteError, deleteCompte } =
    useActionsCompte(compte)

  return (
    <Card>
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <IconBadge Icon={Landmark} size={18} className="w-10 h-10" />
          <div>
            {/* ⚠️ Le **compte** est l'objet, la banque un attribut. Le titre
                portait `etablissement_libelle || nom` : trois comptes d'une même
                banque s'intitulaient tous « BoursoBank », et leur nom
                n'apparaissait nulle part. Le §7 du CLAUDE.md porte déjà la
                règle pour les selects — « toujours `nom — établissement`,
                jamais `établissement || nom` ».
                (D14 de la revue UI/UX du 2026-08-20.) */}
            <div className="text-sm font-medium text-content flex items-center gap-1.5">
              {compte.nom}
              <BadgesCompte compte={compte} />
            </div>
            <div className="text-xs text-content-2">
              {[compte.etablissement_libelle, compte.titulaire_libelle, compte.type_compte_libelle]
                .filter(Boolean)
                .join(' · ')}
            </div>
          </div>
        </div>
        <div className="flex gap-1 shrink-0">
          <Link
            to={`/comptes/${compte.id}`}
            title="Voir les transactions"
            className="p-1.5 rounded-md text-content-2 hover:text-content hover:bg-surface-3 cursor-pointer"
          >
            <BarChart3 size={14} />
          </Link>
          <button
            onClick={onEdit}
            title="Modifier"
            className="p-1.5 rounded-md text-content-2 hover:text-content hover:bg-surface-3 cursor-pointer"
          >
            <Pencil size={14} />
          </button>
          <button
            onClick={handleDelete}
            title="Supprimer"
            disabled={deleteCompte.isPending}
            className="p-1.5 rounded-md text-content-2 hover:text-red-texte hover:bg-red-50 cursor-pointer disabled:opacity-50"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      {deleteError && (
        <div className="mb-3 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          {deleteError}
          <button
            onClick={handleToggleActif}
            className="ml-2 underline font-medium cursor-pointer"
          >
            Désactiver à la place
          </button>
        </div>
      )}

      <div className="text-2xl font-medium text-content">
        {formatEuro(compte.solde_theorique)}
      </div>
      <div className="text-[11px] text-content-2 flex items-center gap-1">
        Solde théorique (avec prévisionnels)
        <Tooltip {...DEFINITIONS.solde_theorique} align="left" size={12} />
      </div>

      <div className="flex justify-between mt-4 pt-3.5 border-t border-border-app">
        <div>
          <div className="text-[11px] text-content-2 flex items-center gap-1">
            Solde confirmé
            <Tooltip {...DEFINITIONS.solde_reel} align="left" size={12} />
          </div>
          <div className="text-sm font-medium text-content">{formatEuro(compte.solde_reel)}</div>
        </div>
        <div className="text-right">
          <div className="text-[11px] text-content-2 flex items-center gap-1 justify-end">
            En attente
            <Tooltip {...DEFINITIONS.ecart_solde} align="right" size={12} />
          </div>
          <div className={`text-sm font-medium ${
            ecart === 0 ? 'text-teal-texte' : ecart > 0 ? 'text-amber-texte' : 'text-teal-texte'
          }`}>
            {ecart !== 0 ? (ecart > 0 ? `−${formatEuro(Math.abs(ecart))}` : `+${formatEuro(Math.abs(ecart))}`) : formatEuro(0)}
          </div>
        </div>
      </div>

      {!compte.actif && (
        <div className="mt-3 text-[11px] text-content-3 bg-surface-3 rounded px-2 py-1">
          Compte désactivé
        </div>
      )}
    </Card>
  )
}

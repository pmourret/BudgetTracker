import { useEffect, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import Modal from '../ui/Modal'
import Button from '../ui/Button'
import Input from '../ui/Input'
import Select from '../ui/Select'
import { useCategories } from '../../hooks/useResource'
import { useCreerFluxDepuisLigne } from '../../hooks/useImports'
import { formatEuro, formatDate } from '../../utils/format'

// Une ligne dont le libellé commence par « VIR » est très probablement un
// virement interne : le créer en flux simple ne toucherait qu'un compte.
const ressembleAVirement = (libelle) =>
  /^\s*vir\b/i.test(libelle || '')

export default function CreerFluxModal({ ligne, compteNom, onClose, onCreated }) {
  const [categorie, setCategorie] = useState('')
  const [libelle, setLibelle] = useState('')
  const [error, setError] = useState('')

  const { data: categoriesData } = useCategories()
  const creer = useCreerFluxDepuisLigne()

  useEffect(() => {
    if (ligne) {
      setCategorie('')
      setLibelle(ligne.libelle || '')
      setError('')
    }
  }, [ligne])

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

  const handleSubmit = () => {
    setError('')
    if (!categorie) { setError('Choisissez une catégorie.'); return }
    creer.mutate(
      { ligneId: ligne.id, categorie, libelle: libelle || undefined },
      {
        onSuccess: () => onCreated?.(),
        onError: (err) =>
          setError(err.response?.data?.detail || 'Création impossible.'),
      }
    )
  }

  if (!ligne) return null
  const estVirement = ressembleAVirement(ligne.libelle)

  return (
    <Modal
      isOpen={!!ligne}
      onClose={onClose}
      title="Créer le flux manquant"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Annuler</Button>
          <Button variant="primary" onClick={handleSubmit} disabled={creer.isPending}>
            {creer.isPending ? 'Création…' : 'Créer et rapprocher'}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="rounded-lg bg-surface-3 px-4 py-3">
          <div className="text-sm font-medium text-content">{ligne.libelle}</div>
          <div className="flex justify-between mt-1 text-xs text-content-2">
            <span>{compteNom} · {formatDate(ligne.date_operation)}</span>
            <span className={Number(ligne.montant) < 0 ? 'text-red-600' : 'text-teal-600'}>
              {formatEuro(ligne.montant)}
            </span>
          </div>
        </div>

        {estVirement && (
          <div className="rounded-md bg-amber-50 text-amber-800 text-xs px-3 py-2 flex gap-2 leading-relaxed">
            <AlertTriangle size={15} className="shrink-0 mt-0.5" />
            <span>
              Ce libellé ressemble à un <strong>virement interne</strong>. Un flux
              simple ne touche qu'un compte — pour un transfert entre vos comptes,
              passez plutôt par la page <strong>Transferts</strong>.
            </span>
          </div>
        )}

        <Input
          label="Libellé" value={libelle} onChange={setLibelle}
          placeholder="Libellé du flux"
        />
        <Select
          label="Catégorie" value={categorie} onChange={setCategorie}
          options={categoriesOpts} groups={categoriesGroups}
          placeholder="Choisir une catégorie…" required error={error}
        />

        <p className="text-xs text-content-2 leading-relaxed">
          Le flux sera créé sur <strong>{compteNom}</strong> avec le montant et la
          date de l'opération, en statut <strong>validé</strong>, puis rapproché à
          cette ligne.
        </p>
      </div>
    </Modal>
  )
}

import { useState } from 'react'
import { Upload } from 'lucide-react'
import Modal from '../ui/Modal'
import Button from '../ui/Button'
import Select from '../ui/Select'
import { useResourceList } from '../../hooks/useResource'
import { useUploadImport } from '../../hooks/useImports'

const BANQUES = [{ value: 'boursobank', label: 'BoursoBank' }]

export default function ImportUploadModal({ isOpen, onClose, onImported }) {
  const [compte, setCompte] = useState('')
  const [banque, setBanque] = useState('boursobank')
  const [fichier, setFichier] = useState(null)
  const [error, setError] = useState('')

  const { data: comptesData } = useResourceList('comptes')
  const upload = useUploadImport()
  const comptes = comptesData?.results ?? []

  const compteOptions = comptes.map((c) => ({
    value: c.id,
    label: c.etablissement_libelle
      ? `${c.nom} — ${c.etablissement_libelle}${c.est_commun ? ' · Commun' : ''}`
      : c.nom,
  }))

  const reset = () => {
    setCompte(''); setBanque('boursobank'); setFichier(null); setError('')
  }
  const close = () => { reset(); onClose() }

  const handleSubmit = () => {
    setError('')
    if (!fichier) { setError('Sélectionnez un fichier CSV.'); return }

    upload.mutate(
      { compte, banque, fichier },
      {
        onSuccess: (data) => {
          reset()
          onImported?.(data)
        },
        onError: (err) => {
          const d = err.response?.data
          if (d?.comptes) {
            setError(
              `Le fichier contient plusieurs comptes (${d.comptes.join(', ')}). ` +
              `Exportez un relevé par compte.`
            )
          } else if (d?.compte_num) {
            setError(
              `Aucun compte ne porte le numéro « ${d.compte_num} ». ` +
              `Renseignez ce N° Compte sur le compte concerné, ou choisissez-le ci-dessus.`
            )
          } else {
            setError(d?.detail || 'Import impossible. Vérifiez le fichier.')
          }
        },
      }
    )
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={close}
      title="Importer un relevé bancaire"
      footer={
        <>
          <Button variant="secondary" onClick={close}>Annuler</Button>
          <Button variant="primary" onClick={handleSubmit} disabled={upload.isPending}>
            {upload.isPending ? 'Analyse…' : 'Importer et rapprocher'}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <p className="text-xs text-content-2 leading-relaxed">
          Le relevé est comparé aux flux déjà saisis pour repérer les écarts.
          Aucun flux n'est créé ni modifié : l'application reste la seule vérité.
        </p>

        <div className="flex flex-col gap-1">
          <Select
            label="Compte" value={compte} onChange={setCompte}
            options={compteOptions} placeholder="Détecté automatiquement"
          />
          <span className="text-xs text-content-2">
            Laissé vide, le compte est détecté via le numéro de compte du fichier
            (= le N° Compte saisi sur vos comptes).
          </span>
        </div>
        <Select
          label="Banque" value={banque} onChange={setBanque} options={BANQUES}
        />

        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-content-2">
            Fichier CSV <span className="text-red-texte">*</span>
          </label>
          <label className="flex items-center gap-2.5 h-11 lg:h-10 px-3 rounded-lg border border-border-app bg-surface cursor-pointer hover:bg-surface-3 text-sm text-content-2">
            <Upload size={16} />
            <span className="truncate">
              {fichier ? fichier.name : 'Sélectionner un fichier…'}
            </span>
            <input
              type="file" accept=".csv,text/csv" className="hidden"
              onChange={(e) => setFichier(e.target.files?.[0] ?? null)}
            />
          </label>
        </div>

        {error && (
          <div className="rounded-md bg-red-50 text-red-800 text-xs px-3 py-2 leading-relaxed">
            {error}
          </div>
        )}
      </div>
    </Modal>
  )
}

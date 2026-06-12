import Badge from '../ui/Badge'

// Mappe la valeur de fiabilité renvoyée par l'API (jamais recalculée côté front).
const FIABILITES = {
  elevee:  { variant: 'success',       label: 'Fiabilité élevée' },
  moyenne: { variant: 'avertissement', label: 'Fiabilité moyenne' },
  faible:  { variant: 'neutre',        label: 'Fiabilité faible' },
}

export default function FiabiliteBadge({ fiabilite }) {
  const f = FIABILITES[fiabilite] || { variant: 'neutre', label: 'Fiabilité inconnue' }
  return <Badge variant={f.variant}>{f.label}</Badge>
}

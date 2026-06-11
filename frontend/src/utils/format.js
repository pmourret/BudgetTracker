const eurFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

export function formatEuro(value) {
  const n = Number(value)
  if (Number.isNaN(n)) return '—'
  return eurFormatter.format(n)
}

export function formatDate(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

export function formatMonth(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' })
}

export function formatPercent(value) {
  const n = Number(value)
  if (Number.isNaN(n)) return '—'
  return `${n.toFixed(1).replace('.', ',')} %`
}
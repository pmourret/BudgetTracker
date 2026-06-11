const variants = {
  critique:      'bg-red-50 text-red-800',
  avertissement: 'bg-amber-50 text-amber-800',
  info:          'bg-blue-50 text-blue-800',
  success:       'bg-teal-50 text-teal-800',
  neutre:        'bg-slate-100 text-slate-600',
  purple:        'bg-purple-50 text-purple-800',
}

export default function Badge({ children, variant = 'neutre' }) {
  const variantClass = variants[variant] || variants.neutre
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full whitespace-nowrap ${variantClass}`}>
      {children}
    </span>
  )
}
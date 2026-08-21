const variants = {
  primary: 'bg-purple-600 text-white hover:bg-purple-800 border-transparent',
  secondary: 'bg-surface text-content border-border-app hover:bg-surface-3',
  danger: 'bg-surface text-red-texte border-red-600 hover:bg-red-50',
  ghost: 'bg-transparent text-content-2 border-transparent hover:bg-surface-3',
}

export default function Button({
  children,
  variant = 'primary',
  onClick,
  disabled = false,
  type = 'button',
  fullWidth = false,
  className = '',
}) {
  const variantClass = variants[variant] || variants.primary

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={[
        // `inline-flex` : sans lui, un bouton portant une icône ET un
        // libellé les empile sur deux lignes. Même base que le Button de
        // FoyerOS — le vocabulaire de la suite converge (ADR-0066).
        'inline-flex items-center justify-center gap-1.5',
        'h-11 lg:h-10 px-4 rounded-lg border text-sm font-medium',
        'cursor-pointer transition-all active:scale-[0.98]',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        fullWidth ? 'w-full' : '',
        variantClass,
        className,
      ].join(' ')}
    >
      {children}
    </button>
  )
}
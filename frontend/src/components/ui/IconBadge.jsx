export default function IconBadge({ Icon, size = 16, className = '' }) {
  return (
    <div
      className={[
        'rounded-lg flex items-center justify-center shrink-0',
        // Couleurs gérées via variables sémantiques (voir index.css)
        'bg-[var(--icon-badge-bg)] text-[var(--icon-badge-fg)]',
        className,
      ].join(' ')}
    >
      <Icon size={size} />
    </div>
  )
}
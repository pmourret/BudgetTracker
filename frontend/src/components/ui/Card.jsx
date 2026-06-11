export default function Card({
  children,
  title,
  action,
  className = '',
  bodyClassName = '',
}) {
  return (
    <div className={`bg-surface border border-border-app rounded-xl ${className}`}>
      {(title || action) && (
        <div className="flex justify-between items-center px-5 pt-4 pb-0">
          {title && (
            <span className="text-sm font-medium text-content">{title}</span>
          )}
          {action && <div>{action}</div>}
        </div>
      )}
      <div className={bodyClassName || 'p-5'}>{children}</div>
    </div>
  )
}
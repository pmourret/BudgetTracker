export default function Input({
  label,
  value,
  onChange,
  type = 'text',
  placeholder = '',
  error = '',
  required = false,
  disabled = false,
  className = '',
  ...rest
}) {
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label className="text-sm font-medium text-content-2">
          {label}
          {required && <span className="text-red-600"> *</span>}
        </label>
      )}
      <input
        type={type}
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className={[
          'h-11 sm:h-10 px-3 rounded-lg border text-sm text-content bg-surface',
          'outline-none transition-colors',
          'focus:border-purple-600',
          'disabled:bg-surface-3 disabled:cursor-not-allowed',
          error ? 'border-red-600' : 'border-border-app',
          className,
        ].join(' ')}
        {...rest}
      />
      {error && <span className="text-xs text-red-600">{error}</span>}
    </div>
  )
}
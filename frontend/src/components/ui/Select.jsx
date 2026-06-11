export default function Select({
  label,
  value,
  onChange,
  options = [],
  groups = [],
  placeholder = 'Sélectionner...',
  error = '',
  required = false,
  disabled = false,
  className = '',
}) {
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label className="text-sm font-medium text-content-2">
          {label}
          {required && <span className="text-red-600"> *</span>}
        </label>
      )}
      <select
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className={[
          'h-11 sm:h-10 px-3 rounded-lg border text-sm',
          'outline-none transition-colors appearance-none',
          'bg-surface bg-no-repeat cursor-pointer',
          'focus:border-purple-600',
          'disabled:bg-surface-3 disabled:cursor-not-allowed',
          value ? 'text-content' : 'text-content-3',
          error ? 'border-red-600' : 'border-border-app',
          className,
        ].join(' ')}
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E")`,
          backgroundPosition: 'right 0.75rem center',
        }}
      >
        <option value="" disabled>{placeholder}</option>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
        {groups.map((group) => (
          <optgroup key={group.label} label={group.label}>
            {group.options.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </optgroup>
        ))}
      </select>
      {error && <span className="text-xs text-red-600">{error}</span>}
    </div>
  )
}

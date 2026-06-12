export default function PeriodSelector({ value, onChange, options = [3, 6, 12] }) {
  return (
    <div className="flex gap-1">
      {options.map((n) => (
        <button
          key={n}
          onClick={() => onChange(n)}
          className={[
            'h-7 px-2.5 rounded-md text-xs cursor-pointer',
            value === n
              ? 'bg-purple-50 text-purple-800 font-medium'
              : 'bg-transparent text-content-2 hover:bg-surface-3',
          ].join(' ')}
        >
          {n}M
        </button>
      ))}
    </div>
  )
}

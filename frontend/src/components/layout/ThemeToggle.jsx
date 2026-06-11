import { Sun, Moon, Monitor } from 'lucide-react'
import { useThemeStore } from '../../stores/themeStore'

const MODES = [
  { key: 'light',  label: 'Clair',   Icon: Sun },
  { key: 'system', label: 'Système', Icon: Monitor },
  { key: 'dark',   label: 'Sombre',  Icon: Moon },
]

export default function ThemeToggle({ variant = 'dark' }) {
  const mode = useThemeStore((s) => s.mode)
  const setMode = useThemeStore((s) => s.setMode)

  // variant 'dark' = sidebar sombre, variant 'light' = sur fond de page clair/sombre
  const containerClass =
    variant === 'dark'
      ? 'bg-ink-light/40'
      : 'bg-surface-3'

  const activeClass =
    variant === 'dark'
      ? 'bg-ink-light text-purple-50'
      : 'bg-surface text-content shadow-sm'

  const inactiveClass =
    variant === 'dark'
      ? 'text-purple-200 hover:text-purple-50'
      : 'text-content-2 hover:text-content'

  return (
    <div className={`inline-flex gap-0.5 rounded-lg p-0.5 ${containerClass}`}>
      {MODES.map(({ key, label, Icon }) => (
        <button
          key={key}
          onClick={() => setMode(key)}
          title={label}
          aria-label={label}
          className={[
            'flex items-center justify-center w-9 h-9 rounded-md cursor-pointer transition-colors',
            mode === key ? activeClass : inactiveClass,
          ].join(' ')}
        >
          <Icon size={16} />
        </button>
      ))}
    </div>
  )
}
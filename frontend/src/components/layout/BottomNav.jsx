import { NavLink } from 'react-router-dom'
import { LayoutDashboard, ArrowLeftRight, Target, Bell, MoreHorizontal } from 'lucide-react'

const navItems = [
  { to: '/dashboard', label: 'Accueil', Icon: LayoutDashboard },
  { to: '/flux',      label: 'Flux',    Icon: ArrowLeftRight },
  { to: '/budgets',   label: 'Budgets', Icon: Target },
  { to: '/alertes',   label: 'Alertes', Icon: Bell },
  { to: '/plus',      label: 'Plus',    Icon: MoreHorizontal },
]

export default function BottomNav() {
  return (
    <nav
      className="fixed bottom-0 left-0 right-0 h-[60px] bg-surface border-t border-border-app flex justify-around items-center z-50"
      style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
    >
      {navItems.map(({ to, label, Icon }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            [
              'flex flex-col items-center gap-0.5 no-underline flex-1 h-full justify-center text-[10px]',
              isActive ? 'text-purple-600 font-medium' : 'text-content-3 font-normal',
            ].join(' ')
          }
        >
          <Icon size={20} />
          {label}
        </NavLink>
      ))}
    </nav>
  )
}
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, CreditCard, ArrowLeftRight, Target,
  RefreshCw, Bell, Landmark, Wallet, Tag,
} from 'lucide-react'
import ThemeToggle from './ThemeToggle'

const navItems = [
  { to: '/dashboard',   label: 'Dashboard',   Icon: LayoutDashboard },
  { to: '/comptes',     label: 'Comptes',     Icon: CreditCard },
  { to: '/flux',        label: 'Flux',        Icon: ArrowLeftRight },
  { to: '/budgets',     label: 'Budgets',     Icon: Target },
  { to: '/abonnements', label: 'Abonnements', Icon: RefreshCw },
  { to: '/alertes',     label: 'Alertes',     Icon: Bell },
  { to: '/patrimoine',  label: 'Patrimoine',  Icon: Landmark },
  { to: '/categories',  label: 'Catégories',  Icon: Tag },
]

export default function Sidebar() {
  return (
    <nav className="w-[220px] bg-ink px-4 py-6 flex flex-col gap-0.5 shrink-0 h-screen sticky top-0">
      <div className="text-purple-50 font-medium text-[15px] mb-8 px-2 flex items-center gap-2">
        <Wallet size={18} />
        BudgetFamilial
      </div>
      {navItems.map(({ to, label, Icon }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            [
              'flex items-center gap-2.5 px-3 py-2.5 rounded-md text-sm no-underline',
              isActive
                ? 'bg-ink-light text-purple-50 font-medium'
                : 'text-purple-200 font-normal hover:bg-ink-light/50',
            ].join(' ')
          }
        >
          <Icon size={17} />
          {label}
        </NavLink>
      ))}
      <div className="inline-flex gap-0.5 rounded-lg self-center mt-auto">
        <ThemeToggle />
      </div>
    </nav>
  )
}
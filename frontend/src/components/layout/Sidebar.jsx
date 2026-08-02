import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, CreditCard, ArrowLeftRight, Repeat, Target,
  TrendingUp, RefreshCw, Bell, Landmark, Wallet, Tag, Settings, ChartColumn,
  FileUp, LogOut,
} from 'lucide-react'
import { useDeconnexion, useMoi } from '../../hooks/useAuth'
import ThemeToggle from './ThemeToggle'

const navItems = [
  { to: '/dashboard',   label: 'Dashboard',   Icon: LayoutDashboard },
  { to: '/comptes',     label: 'Comptes',     Icon: CreditCard },
  { to: '/flux',        label: 'Flux',        Icon: ArrowLeftRight },
  { to: '/transferts',  label: 'Transferts',  Icon: Repeat },
  { to: '/budgets',     label: 'Budgets',     Icon: Target },
  { to: '/analyse',     label: 'Analyse',     Icon: ChartColumn },
  { to: '/previsionnel', label: 'Prévisionnel', Icon: TrendingUp },
  { to: '/abonnements', label: 'Abonnements', Icon: RefreshCw },
  { to: '/alertes',     label: 'Alertes',     Icon: Bell },
  { to: '/patrimoine',  label: 'Patrimoine',  Icon: Landmark },
  { to: '/imports',     label: 'Rapprochement', Icon: FileUp },
  { to: '/categories',  label: 'Catégories',  Icon: Tag },
  { to: '/parametres',  label: 'Paramètres',  Icon: Settings },
]

export default function Sidebar() {
  const { data: moi } = useMoi()
  const deconnecter = useDeconnexion()

  return (
    <nav className="w-[220px] bg-ink px-4 py-6 flex flex-col gap-0.5 shrink-0 h-screen sticky top-0">
      <div className="text-purple-50 font-medium text-[15px] mb-8 px-2 flex items-center gap-2">
        <Wallet size={18} />
        BudgetTracker - V.α
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
      <div className="mt-auto flex flex-col gap-3">
        <div className="inline-flex gap-0.5 rounded-lg self-center">
          <ThemeToggle />
        </div>

        {/* Qui est connecté, et la porte pour en sortir. En bas, hors de la
            liste de navigation : ce n'est pas une destination. */}
        <button
          onClick={deconnecter}
          title="Se déconnecter"
          className="flex items-center gap-2.5 px-3 py-2.5 rounded-md text-sm text-purple-200 hover:bg-ink-light/50 border-t border-ink-light pt-3"
        >
          <LogOut size={17} className="shrink-0" />
          <span className="truncate">{moi?.nom_affiche ?? 'Se déconnecter'}</span>
        </button>
      </div>
    </nav>
  )
}
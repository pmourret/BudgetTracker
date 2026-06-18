import { Link } from 'react-router-dom'
import { CreditCard, Repeat, TrendingUp, RefreshCw, Landmark, Tag, ChevronRight } from 'lucide-react'
import Card from '../components/ui/Card'
import IconBadge from '../components/ui/IconBadge'
import ThemeToggle from '../components/layout/ThemeToggle'

const liens = [
  { to: '/previsionnel', label: 'Prévisionnel', desc: 'Solde projeté et trajectoire d\'épargne', Icon: TrendingUp },
  { to: '/comptes',     label: 'Comptes',     desc: 'Soldes et écarts',         Icon: CreditCard },
  { to: '/transferts',  label: 'Transferts',  desc: 'Virements entre comptes (ex. épargne)', Icon: Repeat },
  { to: '/abonnements', label: 'Abonnements', desc: 'Récurrences et échéances', Icon: RefreshCw },
  { to: '/patrimoine',  label: 'Patrimoine',  desc: 'Actifs et valorisation',   Icon: Landmark },
  { to: '/categories',  label: 'Catégories',  desc: 'Majeures et sous-catégories', Icon: Tag },
]

export default function PlusPage() {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-lg font-medium text-content">Plus</h1>
        <p className="text-sm text-content-2 mt-0.5">Accès et préférences</p>
      </div>

      <Card bodyClassName="p-0">
        <div className="flex flex-col">
          {liens.map(({ to, label, desc, Icon }, i) => (
            <Link
              key={to}
              to={to}
              className={[
                'flex items-center gap-3 px-4 py-3.5 no-underline',
                i < liens.length - 1 ? 'border-b border-border-app' : '',
              ].join(' ')}
            >
              <IconBadge Icon={Icon} size={18} className="w-10 h-10" />
              <div className="flex-1">
                <div className="text-sm font-medium text-content">{label}</div>
                <div className="text-xs text-content-2">{desc}</div>
              </div>
              <ChevronRight size={18} className="text-content-3" />
            </Link>
          ))}
        </div>
      </Card>

      <Card title="Apparence">
        <div className="flex items-center justify-between">
          <span className="text-sm text-content-2">Thème</span>
          <ThemeToggle variant="light" />
        </div>
      </Card>
    </div>
  )
}
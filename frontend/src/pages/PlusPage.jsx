import { Link } from 'react-router-dom'
import { CreditCard, Repeat, TrendingUp, RefreshCw, Landmark, Tag, Settings, ChartColumn, FileUp, ChevronRight, LogOut } from 'lucide-react'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import IconBadge from '../components/ui/IconBadge'
import ThemeToggle from '../components/layout/ThemeToggle'
import { useDeconnexion, useMoi } from '../hooks/useAuth'

const liens = [
  { to: '/analyse',     label: 'Analyse',     desc: 'Où part l\'argent, quand et comment', Icon: ChartColumn },
  { to: '/previsionnel', label: 'Prévisionnel', desc: 'Solde projeté et trajectoire d\'épargne', Icon: TrendingUp },
  { to: '/comptes',     label: 'Comptes',     desc: 'Soldes et écarts',         Icon: CreditCard },
  { to: '/transferts',  label: 'Transferts',  desc: 'Virements entre comptes (ex. épargne)', Icon: Repeat },
  { to: '/abonnements', label: 'Abonnements', desc: 'Récurrences et échéances', Icon: RefreshCw },
  { to: '/patrimoine',  label: 'Patrimoine',  desc: 'Actifs et valorisation',   Icon: Landmark },
  { to: '/imports',     label: 'Rapprochement', desc: 'Comparer un relevé bancaire à vos flux', Icon: FileUp },
  { to: '/categories',  label: 'Catégories',  desc: 'Majeures et sous-catégories', Icon: Tag },
  { to: '/parametres',  label: 'Paramètres',  desc: 'Mois comptable et réglages du foyer', Icon: Settings },
]

export default function PlusPage() {
  const { data: moi } = useMoi()
  const deconnecter = useDeconnexion()

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

      {/* En mobile, la sidebar n'existe pas : sans cette carte, la déconnexion
          serait tout simplement inatteignable au téléphone. */}
      <Card title="Compte">
        <div className="flex items-center justify-between gap-3">
          <span className="text-sm text-content-2 truncate">
            {moi?.nom_affiche ?? '—'}
          </span>
          <Button variant="secondary" onClick={deconnecter}>
            <span className="inline-flex items-center gap-1.5">
              <LogOut size={16} /> Se déconnecter
            </span>
          </Button>
        </div>
        {/* BudgetTracker n'a pas d'écran de mot de passe, et n'en aura pas :
            il ne détient plus le mot de passe. Le dire, plutôt que de laisser
            chercher un réglage qui n'existe pas ici. */}
        {moi?.identite_partagee && (
          <p className="mt-3 border-t border-border-app pt-3 text-xs text-content-3">
            Votre mot de passe est commun à toutes les applications du foyer. Il
            se modifie depuis <strong>FoyerOS</strong>, écran « Mon compte ».
          </p>
        )}
      </Card>
    </div>
  )
}
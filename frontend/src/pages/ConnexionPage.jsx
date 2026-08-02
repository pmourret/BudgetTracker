import { useState } from 'react'
import { Eye, EyeOff, Wallet } from 'lucide-react'

import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import { useConnexion } from '../hooks/useAuth'

/**
 * Écran de connexion — la seule surface accessible sans jeton.
 *
 * **Aucune inscription.** Un compte naît de `manage.py creer_utilisateur`, côté
 * serveur : BudgetTracker est l'application d'un foyer sur son propre homelab,
 * pas un service ouvert. Même parti que FoyerOS, où la création de compte est
 * réservée aux administrateurs et où l'accueil n'offre que la connexion.
 */
export default function ConnexionPage() {
  const [identifiant, setIdentifiant] = useState('')
  const [motDePasse, setMotDePasse] = useState('')
  const [visible, setVisible] = useState(false)
  const connexion = useConnexion()

  const soumettre = (e) => {
    e.preventDefault()
    if (!identifiant.trim() || !motDePasse) return
    connexion.mutate({ identifiant: identifiant.trim(), motDePasse })
  }

  // Trois refus, trois gestes différents : retaper, s'adresser ailleurs, ou
  // attendre. Les confondre sous « une erreur est survenue » ferait rejouer le
  // mauvais. Quand le serveur explique lui-même (403 : compte d'un autre
  // foyer), on rend **son** message plutôt qu'un texte générique.
  const statut = connexion.error?.response?.status
  const detail = connexion.error?.response?.data?.detail
  const message =
    statut === 401
      ? 'Identifiant ou mot de passe incorrect.'
      : statut === 403
        ? detail || "Ce compte n'a pas accès à cette instance."
        : connexion.isError
          ? 'Serveur injoignable. Réessayez dans un instant.'
          : ''

  return (
    <div className="min-h-screen bg-surface-2 flex items-center justify-center p-5">
      <form
        onSubmit={soumettre}
        className="w-full max-w-sm bg-surface border border-border-app rounded-xl p-6 flex flex-col gap-5"
      >
        <div className="flex items-center gap-2.5">
          <span className="grid place-items-center w-10 h-10 rounded-lg bg-ink text-purple-50 shrink-0">
            <Wallet size={20} />
          </span>
          <div>
            <h1 className="text-base font-medium text-content">BudgetTracker</h1>
            <p className="text-xs text-content-2">Connectez-vous pour continuer</p>
          </div>
        </div>

        {/* Les deux marchent (`ConnexionSerializer`). Le dire évite d'avoir à
            se souvenir lequel a été choisi à la création du compte — c'est
            exactement ce qui a bloqué la première mise en service. */}
        <Input
          label="Email ou identifiant"
          value={identifiant}
          onChange={setIdentifiant}
          autoComplete="username"
          autoFocus
          required
        />

        <div className="relative">
          <Input
            label="Mot de passe"
            type={visible ? 'text' : 'password'}
            value={motDePasse}
            onChange={setMotDePasse}
            autoComplete="current-password"
            className="pr-10"
            required
          />
          {/* `type="button"` : sans lui, relire son mot de passe soumettrait
              le formulaire à sa place. */}
          <button
            type="button"
            onClick={() => setVisible((v) => !v)}
            aria-label={visible ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
            className="absolute right-0 bottom-0 h-11 sm:h-10 w-10 grid place-items-center text-content-3 hover:text-content"
          >
            {visible ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </div>

        {message && (
          <p role="alert" className="text-xs text-red-600">
            {message}
          </p>
        )}

        <Button
          type="submit"
          fullWidth
          disabled={connexion.isPending || !identifiant.trim() || !motDePasse}
        >
          {connexion.isPending ? 'Connexion…' : 'Se connecter'}
        </Button>
      </form>
    </div>
  )
}

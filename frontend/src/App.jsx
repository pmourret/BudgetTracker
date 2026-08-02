import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/layout/Layout'
import ConnexionPage from './pages/ConnexionPage'
import { estConnecte, useAuthStore } from './stores/authStore'
import ComptesPage from './pages/ComptesPage'
import CompteDetailPage from './pages/CompteDetailPage'
import FluxPage from './pages/FluxPage'
import TransfertsPage from './pages/TransfertsPage'
import BudgetsPage from './pages/BudgetsPage'
import AbonnementsPage from './pages/AbonnementsPage'
import AlertesPage from './pages/AlertesPage'
import PatrimoinePage from './pages/PatrimoinePage'
import DashboardPage from './pages/DashboardPage'
import PrevisionnelPage from './pages/PrevisionnelPage'
import AnalysePage from './pages/AnalysePage'
import CategoriesPage from './pages/CategoriesPage'
import ParametresPage from './pages/ParametresPage'
import ImportsPage from './pages/ImportsPage'
import PlusPage from './pages/PlusPage'

export default function App() {
  const connecte = useAuthStore(estConnecte)

  // Pas de route `/connexion` : tant qu'il n'y a pas de session, **rien d'autre
  // n'existe**. Une route de plus laisserait les URL profondes atteignables au
  // rendu — un écran monté, ses requêtes parties, et dix 401 avant la
  // redirection. Ici, l'arbre des pages n'est simplement pas construit.
  //
  // Le test porte sur le jeton de **rafraîchissement**, jamais sur l'accès :
  // celui-ci expire en 30 minutes, et le client sait le renouveler seul. S'y
  // fier renverrait sur cet écran une session parfaitement valide.
  if (!connecte) return <ConnexionPage />

  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="comptes" element={<ComptesPage />} />
        <Route path="comptes/:id" element={<CompteDetailPage />} />
        <Route path="flux" element={<FluxPage />} />
        <Route path="transferts" element={<TransfertsPage />} />
        <Route path="budgets" element={<BudgetsPage />} />
        <Route path="previsionnel" element={<PrevisionnelPage />} />
        <Route path="analyse" element={<AnalysePage />} />
        <Route path="abonnements" element={<AbonnementsPage />} />
        <Route path="alertes" element={<AlertesPage />} />
        <Route path="patrimoine" element={<PatrimoinePage />} />
        <Route path="categories" element={<CategoriesPage />} />
        <Route path="imports" element={<ImportsPage />} />
        <Route path="parametres" element={<ParametresPage />} />
        <Route path="plus" element={<PlusPage />} />
      </Route>
    </Routes>
  )
}
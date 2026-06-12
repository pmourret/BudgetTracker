import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/layout/Layout'
import ComptesPage from './pages/ComptesPage'
import FluxPage from './pages/FluxPage'
import BudgetsPage from './pages/BudgetsPage'
import AbonnementsPage from './pages/AbonnementsPage'
import AlertesPage from './pages/AlertesPage'
import PatrimoinePage from './pages/PatrimoinePage'
import DashboardPage from './pages/DashboardPage'
import PrevisionnelPage from './pages/PrevisionnelPage'
import CategoriesPage from './pages/CategoriesPage'
import PlusPage from './pages/PlusPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="comptes" element={<ComptesPage />} />
        <Route path="flux" element={<FluxPage />} />
        <Route path="budgets" element={<BudgetsPage />} />
        <Route path="previsionnel" element={<PrevisionnelPage />} />
        <Route path="abonnements" element={<AbonnementsPage />} />
        <Route path="alertes" element={<AlertesPage />} />
        <Route path="patrimoine" element={<PatrimoinePage />} />
        <Route path="categories" element={<CategoriesPage />} />
        <Route path="plus" element={<PlusPage />} />
      </Route>
    </Routes>
  )
}
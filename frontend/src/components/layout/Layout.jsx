import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import BottomNav from './BottomNav'

export default function Layout() {
  return (
    <div className="min-h-screen lg:flex bg-surface-2">
      <div className="hidden lg:block">
        <Sidebar />
      </div>

      <main className="flex-1 p-5 lg:p-8 pb-[calc(60px+1.25rem+env(safe-area-inset-bottom))] lg:pb-8">
        <Outlet />
      </main>

      <div className="lg:hidden">
        <BottomNav />
      </div>
    </div>
  )
}
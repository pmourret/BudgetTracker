import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import BottomNav from './BottomNav'

export default function Layout() {
  return (
    <div className="min-h-screen sm:flex bg-surface-2">
      <div className="hidden sm:block">
        <Sidebar />
      </div>

      <main className="flex-1 p-5 sm:p-8 pb-[calc(60px+1.25rem+env(safe-area-inset-bottom))] sm:pb-8 overflow-y-auto">
        <Outlet />
      </main>

      <div className="sm:hidden">
        <BottomNav />
      </div>
    </div>
  )
}
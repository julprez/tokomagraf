import { useState } from 'react'
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Repeat, History, BarChart3, Bell, Settings, LogOut, Bitcoin, BrainCircuit, Activity, Menu, X, ChevronRight, Calculator, FileText, HeartPulse } from 'lucide-react'
import clsx from 'clsx'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import { PageTransition } from './PageTransition'

const navItems = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/operations', label: 'Operaciones', icon: Repeat },
  { path: '/history', label: 'Historial', icon: History },
  { path: '/analytics', label: 'Análisis', icon: BarChart3 },
  { path: '/predictions', label: 'Predicción', icon: BrainCircuit },
  { path: '/dca', label: 'DCA', icon: Activity },
  { path: '/alerts', label: 'Alertas', icon: Bell },
  { path: '/settings', label: 'Config', icon: Settings },
  { path: '/scenario', label: 'Simulador', icon: Calculator },
  { path: '/tax', label: 'Fiscal', icon: FileText },
  { path: '/health', label: 'Estado', icon: HeartPulse },
]

export default function Layout() {
  const location = useLocation()
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const closeSidebar = () => setSidebarOpen(false)

  const { data: notifCount } = useQuery({
    queryKey: ['notifCount'],
    queryFn: () => api.get('/notifications/unread-count').then(r => r.data),
    refetchInterval: 30000,
  })

  const unread = notifCount?.count || 0

  const handleLogout = () => {
    localStorage.removeItem('token')
    navigate('/login')
  }

  const currentPage = navItems.find((item) => item.path === location.pathname)
  const breadcrumbs = location.pathname.split('/').filter(Boolean)

  const sidebarContent = (
    <>
      {/* Logo */}
      <div className="p-6 border-b border-surface-light flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-btc-orange to-btc-dark rounded-xl flex items-center justify-center shadow-lg shadow-btc-orange/20">
            <Bitcoin className="w-6 h-6 text-[#0f172a]" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-gray-100">tokomagraf</h1>
            <p className="text-xs text-gray-500">Gestor de Cartera</p>
          </div>
        </div>
        <button onClick={closeSidebar} className="lg:hidden p-1 text-gray-400 hover:text-gray-200">
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path
          return (
            <Link
              key={item.path}
              to={item.path}
              onClick={closeSidebar}
              className={clsx(
                'flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200',
                isActive
                  ? 'bg-btc-orange/10 text-btc-orange border border-btc-orange/20'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-surface-light'
              )}
            >
              <div className="relative">
                <item.icon className="w-5 h-5" />
                {item.path === '/alerts' && unread > 0 && (
                  <span className="absolute -top-1.5 -right-1.5 w-4 h-4 bg-red-500 text-white text-[9px] font-bold rounded-full flex items-center justify-center shadow-lg shadow-red-500/30">
                    {unread > 9 ? '9+' : unread}
                  </span>
                )}
              </div>
              {item.label}
            </Link>
          )
        })}
      </nav>

      {/* Logout */}
      <div className="p-4 border-t border-surface-light">
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 px-4 py-3 rounded-lg text-sm text-gray-500 hover:text-red-400 hover:bg-red-500/5 transition-all duration-200 w-full"
        >
          <LogOut className="w-5 h-5" />
          Cerrar Sesión
        </button>
      </div>
    </>
  )

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex w-64 bg-surface border-r border-surface-light flex-col shrink-0">
        {sidebarContent}
      </aside>

      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={closeSidebar} />
          <aside className="absolute left-0 top-0 bottom-0 w-72 bg-surface border-r border-surface-light flex flex-col z-50 animate-slide-in">
            {sidebarContent}
          </aside>
        </div>
      )}

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-[#0b1121]">
        {/* Mobile header */}
        <div className="lg:hidden flex items-center gap-3 p-4 border-b border-surface-light bg-surface">
          <button onClick={() => setSidebarOpen(true)} className="p-1.5 text-gray-400 hover:text-gray-200">
            <Menu className="w-6 h-6" />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-gradient-to-br from-btc-orange to-btc-dark rounded-lg flex items-center justify-center">
              <Bitcoin className="w-4 h-4 text-[#0f172a]" />
            </div>
            <span className="text-sm font-bold text-gray-100">tokomagraf</span>
          </div>
        </div>
        <div className="max-w-7xl mx-auto p-3 md:p-6">
          {/* Breadcrumbs */}
          {breadcrumbs.length > 0 && (
            <nav className="flex items-center gap-1 mb-4 text-xs text-gray-500">
              <Link to="/dashboard" className="hover:text-gray-300 transition-colors">Home</Link>
              {breadcrumbs.map((crumb, i) => {
                const path = '/' + breadcrumbs.slice(0, i + 1).join('/')
                const isLast = i === breadcrumbs.length - 1
                return (
                  <span key={path} className="flex items-center gap-1">
                    <ChevronRight className="w-3 h-3" />
                    {isLast ? (
                      <span className="text-gray-300 font-medium capitalize">{crumb}</span>
                    ) : (
                      <Link to={path} className="hover:text-gray-300 transition-colors capitalize">{crumb}</Link>
                    )}
                  </span>
                )
              })}
            </nav>
          )}
          <PageTransition>
            <Outlet />
          </PageTransition>
        </div>
      </main>
    </div>
  )
}

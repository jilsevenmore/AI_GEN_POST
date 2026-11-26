import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { 
  LayoutDashboard, 
  PlusCircle, 
  FileText,
  Image, 
  Palette, 
  Settings, 
  LogOut,
  Menu,
  X,
  ChevronDown,
  Info
} from 'lucide-react'
import { useState } from 'react'
import clsx from 'clsx'
import { ToastProvider } from './Toast'

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Create Post', href: '/create/post', icon: PlusCircle },
  { name: 'Write Blog', href: '/create/blog', icon: FileText },
  { name: 'Image Library', href: '/library', icon: Image },
  { name: 'Brand Kit', href: '/brand', icon: Palette },
  { name: 'Settings', href: '/settings', icon: Settings },
]

export function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [noticeDismissed, setNoticeDismissed] = useState(() =>
    sessionStorage.getItem('freeModelNoticeDismissed') === 'true'
  )

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const dismissNotice = () => {
    sessionStorage.setItem('freeModelNoticeDismissed', 'true')
    setNoticeDismissed(true)
  }

  return (
    <ToastProvider>
      <div className="min-h-screen bg-gray-50">
        {/* Mobile sidebar backdrop */}
        {sidebarOpen && (
          <div 
            className="fixed inset-0 z-40 bg-black/50 lg:hidden"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
        )}

        {/* Sidebar */}
        <aside
          className={clsx(
            'fixed inset-y-0 left-0 z-50 w-64 flex flex-col bg-gradient-to-b from-gray-900 via-gray-900 to-gray-800 transform transition-transform duration-200 lg:translate-x-0',
            sidebarOpen ? 'translate-x-0' : '-translate-x-full'
          )}
          aria-label="Main navigation"
        >
          {/* Brand header */}
          <div className="flex h-16 items-center justify-between px-5 border-b border-white/10 flex-shrink-0">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-500 to-purple-600 flex items-center justify-center shadow-lg">
                <span className="text-white text-xs font-bold">AG</span>
              </div>
              <h1 className="text-base font-bold text-white tracking-tight">AI Gen Post</h1>
            </div>
            <button
              className="lg:hidden p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10"
              onClick={() => setSidebarOpen(false)}
              aria-label="Close sidebar"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Nav links */}
          <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto scrollbar-thin" aria-label="Navigation">
            {navigation.map((item) => (
              <NavLink
                key={item.name}
                to={item.href}
                className={({ isActive }) => clsx(
                  'flex items-center gap-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 group',
                  isActive
                    ? 'bg-white/15 text-white pl-[10px] border-l-2 border-primary-400'
                    : 'text-gray-400 hover:bg-white/8 hover:text-white px-3'
                )}
                onClick={() => setSidebarOpen(false)}
              >
                {({ isActive }) => (
                  <>
                    <div className={clsx(
                      'w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0 transition-colors',
                      isActive ? 'bg-primary-500/30 text-primary-300' : 'text-gray-400 group-hover:text-white'
                    )}>
                      <item.icon className="h-4 w-4" aria-hidden="true" />
                    </div>
                    <span>{item.name}</span>
                    {isActive && <div className="ml-auto w-1.5 h-1.5 rounded-full bg-primary-400 mr-1" />}
                  </>
                )}
              </NavLink>
            ))}
          </nav>

          {/* User card */}
          <div className="p-3 border-t border-white/10 flex-shrink-0">
            <div className="flex items-center gap-3 px-3 py-2.5 bg-white/8 rounded-xl">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-400 to-purple-500 flex items-center justify-center flex-shrink-0 shadow">
                <span className="text-xs font-bold text-white">
                  {user?.email?.charAt(0).toUpperCase()}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate" title={user?.email}>{user?.email}</p>
                <p className="text-xs text-gray-500 truncate">
                  {user?.company_id ? `${user.company_id.slice(0, 10)}…` : 'Default workspace'}
                </p>
              </div>
            </div>
          </div>
        </aside>

        {/* Main content */}
        <div className="lg:pl-64">
          {/* Top bar */}
          <header className="sticky top-0 z-30 bg-white/95 backdrop-blur-sm border-b border-gray-200 shadow-sm">
            <div className="flex h-16 items-center justify-between px-4 sm:px-6 lg:px-10">
              <button
                className="lg:hidden p-2 rounded-lg text-gray-500 hover:bg-gray-100"
                onClick={() => setSidebarOpen(true)}
                aria-label="Open sidebar"
              >
                <Menu className="h-6 w-6" />
              </button>

              <div className="flex-1 lg:flex-none" />

              <div className="flex items-center gap-4">
                {/* User menu */}
                <div className="relative">
                  <button
                    className="flex items-center gap-2 p-2 rounded-lg text-gray-500 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
                    onClick={() => setUserMenuOpen(!userMenuOpen)}
                    aria-expanded={userMenuOpen}
                    aria-haspopup="true"
                  >
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-400 to-purple-500 flex items-center justify-center">
                      <span className="text-sm font-medium text-white">
                        {user?.email?.charAt(0).toUpperCase()}
                      </span>
                    </div>
                    <span className="hidden sm:block text-sm font-medium text-gray-700">
                      {user?.email}
                    </span>
                    <ChevronDown className="h-4 w-4 text-gray-400" />
                  </button>

                  {userMenuOpen && (
                    <>
                      <div className="fixed inset-0 z-40" onClick={() => setUserMenuOpen(false)} />
                      <div className="absolute right-0 mt-2 w-52 bg-white rounded-xl shadow-lg border border-gray-100 py-1.5 z-50">
                        <div className="px-4 py-2.5 border-b border-gray-100">
                          <p className="text-xs text-gray-400">Signed in as</p>
                          <p className="text-sm font-medium text-gray-900 truncate">{user?.email}</p>
                        </div>
                        <NavLink
                          to="/settings"
                          onClick={() => setUserMenuOpen(false)}
                          className="w-full flex items-center gap-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                        >
                          <Settings className="h-4 w-4 text-gray-400" />
                          Settings
                        </NavLink>
                        <button
                          onClick={handleLogout}
                          className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                        >
                          <LogOut className="h-4 w-4" />
                          Sign out
                        </button>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Free model notice — sticky sub-banner */}
            {!noticeDismissed && (
              <div className="bg-amber-50 border-t border-amber-100 px-4 sm:px-6 lg:px-10 py-2 flex items-center gap-2">
                <Info className="h-4 w-4 text-amber-500 flex-shrink-0" />
                <p className="text-xs text-amber-700 flex-1">
                  <span className="font-semibold">Free AI models active.</span> Quality may vary.{' '}
                  <a href="/settings" className="underline font-medium hover:text-amber-900">Upgrade to OpenAI</a> for consistent results.
                </p>
                <button onClick={dismissNotice} className="text-amber-400 hover:text-amber-600 ml-2 flex-shrink-0" aria-label="Dismiss">
                  <X className="h-4 w-4" />
                </button>
              </div>
            )}
          </header>

          {/* Page content — fade in on route change */}
          <main
            key={location.pathname}
            className="px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-8 animate-fade-in-up"
          >
            <Outlet />
          </main>
        </div>
      </div>
    </ToastProvider>
  )
}

import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { Layout } from './components/Layout'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { DashboardPage } from './pages/DashboardPage'
import { JobFormPage } from './pages/JobFormPage'
import { ReviewPage } from './pages/ReviewPage'
import { LibraryPage } from './pages/LibraryPage'
import { BrandKitPage } from './pages/BrandKitPage'
import { PublishPage } from './pages/PublishPage'
import { SettingsPage } from './pages/SettingsPage'
import { LegalPage } from './pages/LegalPage'
import { OnboardingPage } from './pages/OnboardingPage'
import { BetaDashboardPage } from './pages/BetaDashboardPage'
import { LandingPage } from './pages/LandingPage'
import { LeadDashboardPage } from './pages/LeadDashboardPage'
import { BufferCallbackPage } from './pages/BufferCallbackPage'
import { PixelTracker, trackPageView } from './components/PixelTracker'
import { useAuth } from './hooks/useAuth'
import { useEffect } from 'react'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()
  
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary-600 border-t-transparent"></div>
      </div>
    )
  }
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  
  return <>{children}</>
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()
  
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary-600 border-t-transparent"></div>
      </div>
    )
  }
  
  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }
  
  return <>{children}</>
}

// Track page views for advertising pixels (Step 5)
function PageTracking() {
  const location = useLocation()
  useEffect(() => {
    trackPageView(location.pathname, document.title)
  }, [location.pathname])
  return null
}

export default function App() {
  return (
    <>
      <PixelTracker />
      <PageTracking />
      <Routes>
        {/* Public landing page (Step 2) — no auth required */}
        <Route path="/" element={<LandingPage />} />

        {/* Public auth routes */}
        <Route path="/login" element={
          <PublicRoute>
            <LoginPage />
          </PublicRoute>
        } />
        <Route path="/register" element={
          <PublicRoute>
            <RegisterPage />
          </PublicRoute>
        } />

        {/* OAuth callbacks */}
        <Route path="/auth/buffer/callback" element={<BufferCallbackPage />} />

        {/* Protected app routes */}
        <Route path="/" element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }>
          <Route index element={<DashboardPage />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="leads/dashboard" element={<LeadDashboardPage />} />
          <Route path="create/:type" element={<JobFormPage />} />
          <Route path="review/:jobId" element={<ReviewPage />} />
          <Route path="library" element={<LibraryPage />} />
          <Route path="brand" element={<BrandKitPage />} />
          <Route path="publish/:contentId" element={<PublishPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="legal/:page" element={<LegalPage />} />
          <Route path="beta/onboarding/:userId" element={<OnboardingPage />} />
          <Route path="beta/dashboard" element={<BetaDashboardPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}

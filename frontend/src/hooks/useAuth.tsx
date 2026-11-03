import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react'
import { authApi } from '../api/services'
import { getAccessToken, getRefreshToken, setTokens, clearTokens } from '../api/utils/tokens'
import type { UserResponse } from '../api/types'

interface AuthContextType {
  user: UserResponse | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, companyName: string) => Promise<void>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const refreshUser = useCallback(async () => {
    const token = getAccessToken()
    if (!token) {
      setUser(null)
      setIsLoading(false)
      return
    }

    try {
      const response = await authApi.me()
      setUser(response.data)
    } catch {
      // Try refresh token
      const refreshToken = getRefreshToken()
      if (refreshToken) {
        try {
          const tokenResponse = await authApi.refresh(refreshToken)
          setTokens(tokenResponse.data.access_token, tokenResponse.data.refresh_token)
          const userResponse = await authApi.me()
          setUser(userResponse.data)
        } catch {
          clearTokens()
          setUser(null)
        }
      } else {
        setUser(null)
      }
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    refreshUser()
  }, [refreshUser])

  const login = async (email: string, password: string) => {
    const response = await authApi.login({ email, password })
    setTokens(response.data.access_token, response.data.refresh_token)
    const userResponse = await authApi.me()
    setUser(userResponse.data)
  }

  const register = async (email: string, password: string, companyName: string) => {
    const response = await authApi.register({ email, password, company_name: companyName })
    setUser(response.data)
    // Auto-login after registration
    const tokenResponse = await authApi.login({ email, password })
    setTokens(tokenResponse.data.access_token, tokenResponse.data.refresh_token)
  }

  const logout = async () => {
    await authApi.logout()
    clearTokens()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{
      user,
      isAuthenticated: !!user,
      isLoading,
      login,
      register,
      logout,
      refreshUser,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Lock, ArrowLeft, AlertCircle, CheckCircle, Eye, EyeOff } from 'lucide-react'
import { useToast } from '../components/Toast'
import { SEO } from '../components/SEO'
import { authApi } from '../api/services'

const resetSchema = z.object({
  code: z.string().length(6, 'Reset code must be 6 digits'),
  newPassword: z.string().min(8, 'Password must be at least 8 characters'),
  confirmPassword: z.string(),
}).refine((data) => data.newPassword === data.confirmPassword, {
  message: 'Passwords do not match',
  path: ['confirmPassword'],
})

type ResetForm = z.infer<typeof resetSchema>

export function ResetPasswordPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { toast } = useToast()
  const [isLoading, setIsLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)

  // Pre-fill code from URL query param if provided (?code=123456)
  const initialCode = searchParams.get('code') ?? ''

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ResetForm>({
    resolver: zodResolver(resetSchema),
    defaultValues: {
      code: initialCode,
      newPassword: '',
      confirmPassword: '',
    },
  })

  const onSubmit = async (data: ResetForm) => {
    setIsLoading(true)
    try {
      await authApi.resetPassword({
        code: data.code,
        new_password: data.newPassword,
      })
      toast({
        message: 'Your password has been reset successfully.',
        type: 'success',
      })
      navigate('/login')
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: string } } }
      toast({
        message: axiosError.response?.data?.detail || 'Failed to reset password. Please try again.',
        type: 'error',
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex bg-gray-50">
      <SEO title="Reset Password" description="Reset your AI Gen Post password." path="/reset-password" />

      {/* Left brand panel */}
      <div className="hidden lg:flex lg:w-1/2 xl:w-5/12 flex-col justify-between bg-gradient-to-br from-gray-900 via-gray-900 to-gray-800 p-12 relative overflow-hidden">
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-20 left-20 w-72 h-72 rounded-full bg-primary-500 blur-3xl" />
          <div className="absolute bottom-20 right-10 w-56 h-56 rounded-full bg-purple-500 blur-3xl" />
        </div>

        <div className="relative flex items-center gap-3 mb-8">
          <button
            onClick={() => navigate('/login')}
            className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center hover:bg-white/20 transition-colors"
          >
            <ArrowLeft className="h-4 w-4 text-white" />
          </button>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-purple-600 flex items-center justify-center shadow-lg">
              <span className="text-white text-sm font-bold">AG</span>
            </div>
            <span className="text-white text-xl font-bold tracking-tight">AI Gen Post</span>
          </div>
        </div>

        <div className="relative space-y-8 flex-1">
          <div>
            <h2 className="text-4xl font-bold text-white leading-tight">
              Reset your<br />
              <span className="bg-gradient-to-r from-primary-400 to-purple-400 bg-clip-text text-transparent">
                password
              </span>
            </h2>
            <p className="mt-4 text-gray-400 text-lg leading-relaxed">
              Enter the 6-digit code sent to your email and choose a new password.
            </p>
          </div>
        </div>

        <p className="relative text-gray-600 text-xs">© 2026 EVENMORE INFOTECH</p>
      </div>

      {/* Right form panel */}
      <div className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <div className="card p-6 sm:p-8 shadow-sm">
            <div className="mb-8">
              <h1 className="text-2xl font-bold text-gray-900">Reset password</h1>
              <p className="mt-1.5 text-gray-500 text-sm">
                Enter your reset code and create a new password.
              </p>
            </div>

            <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
              <div>
                <label htmlFor="code" className="label">Reset code</label>
                <div className="relative">
                  <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4.5 w-4.5 text-gray-400" />
                  <input
                    {...register('code')}
                    id="code"
                    type="text"
                    maxLength={6}
                    autoComplete="one-time-code"
                    className="input pl-10 text-center letter-spacing-wide font-mono"
                    placeholder="123456"
                    disabled={isLoading}
                    aria-invalid={!!errors.code}
                  />
                </div>
                {errors.code && (
                  <p className="mt-1.5 text-xs text-red-600">{errors.code.message}</p>
                )}
              </div>

              <div>
                <label htmlFor="newPassword" className="label">New password</label>
                <div className="relative">
                  <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4.5 w-4.5 text-gray-400" />
                  <input
                    {...register('newPassword')}
                    id="newPassword"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    className="input pl-10 pr-10"
                    placeholder="••••••••"
                    disabled={isLoading}
                    aria-invalid={!!errors.newPassword}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {errors.newPassword && (
                  <p className="mt-1.5 text-xs text-red-600">{errors.newPassword.message}</p>
                )}
              </div>

              <div>
                <label htmlFor="confirmPassword" className="label">Confirm password</label>
                <div className="relative">
                  <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4.5 w-4.5 text-gray-400" />
                  <input
                    {...register('confirmPassword')}
                    id="confirmPassword"
                    type={showConfirmPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    className="input pl-10 pr-10"
                    placeholder="••••••••"
                    disabled={isLoading}
                    aria-invalid={!!errors.confirmPassword}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
                  >
                    {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {errors.confirmPassword && (
                  <p className="mt-1.5 text-xs text-red-600">{errors.confirmPassword.message}</p>
                )}
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="btn-primary w-full py-2.5 mt-2"
              >
                {isLoading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Resetting…
                  </span>
                ) : 'Reset password'}
              </button>
            </form>

            <p className="mt-6 text-center text-sm text-gray-500">
              Didn't receive a code?{' '}
              <Link to="/forgot-password" className="text-primary-600 hover:text-primary-700 font-medium">
                Request again
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
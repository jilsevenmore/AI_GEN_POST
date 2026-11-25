import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Mail, ArrowLeft, CheckCircle } from 'lucide-react'
import { useToast } from '../components/Toast'
import { SEO } from '../components/SEO'
import { authApi } from '../api/services'

const forgotSchema = z.object({
  email: z.string().email('Invalid email address'),
})

type ForgotForm = z.infer<typeof forgotSchema>

export function ForgotPasswordPage() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const [isLoading, setIsLoading] = useState(false)
  const [step, setStep] = useState<'request' | 'sent'>('request')

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ForgotForm>({
    resolver: zodResolver(forgotSchema),
  })

  const onSubmit = async (data: ForgotForm) => {
    setIsLoading(true)
    try {
      await authApi.forgotPassword({ email: data.email })
      setStep('sent')
      toast({
        message: 'If an account exists for that email, a reset code has been sent.',
        type: 'info',
      })
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: string } } }
      toast({
        message: axiosError.response?.data?.detail || 'Failed to send reset code. Please try again.',
        type: 'error',
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex bg-gray-50">
      <SEO title="Forgot Password" description="Reset your AI Gen Post password." path="/forgot-password" />

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
              Enter your email and we'll send you a 6-digit reset code.
            </p>
          </div>
        </div>

        <p className="relative text-gray-600 text-xs">© 2026 EVENMORE INFOTECH</p>
      </div>

      {/* Right form panel */}
      <div className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <div className="card p-6 sm:p-8 shadow-sm">
            {step === 'request' ? (
              <div className="space-y-5">
                <div className="mb-8">
                  <h1 className="text-2xl font-bold text-gray-900">Forgot password</h1>
                  <p className="mt-1.5 text-gray-500 text-sm">
                    No worries, it happens. Enter your email below and we'll send you a reset code.
                  </p>
                </div>

                <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
                  <div>
                    <label htmlFor="email" className="label">Email address</label>
                    <div className="relative">
                      <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4.5 w-4.5 text-gray-400" />
                      <input
                        {...register('email')}
                        id="email"
                        type="email"
                        autoComplete="email"
                        className="input pl-10"
                        placeholder="you@example.com"
                        disabled={isLoading}
                        aria-invalid={!!errors.email}
                      />
                    </div>
                    {errors.email && (
                      <p className="mt-1.5 text-xs text-red-600">{errors.email.message}</p>
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
                        Sending…
                      </span>
                    ) : 'Send reset code'}
                  </button>
                </form>

                <p className="mt-6 text-center text-sm text-gray-500">
                  Remember your password?{' '}
                  <Link to="/login" className="text-primary-600 hover:text-primary-700 font-medium">
                    Sign in
                  </Link>
                </p>
              </div>
            ) : (
              <div className="text-center py-8 space-y-4">
                <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4">
                  <CheckCircle className="h-8 w-8 text-green-600" />
                </div>
                <h2 className="text-2xl font-bold text-gray-900">Code sent!</h2>
                <p className="mt-2 text-gray-500 text-sm">
                  Check your inbox for the 6-digit reset code.
                </p>

                <div className="mt-8 text-center">
                  <Link
                    to="/login"
                    className="btn-primary w-full py-2.5"
                  >
                    Back to sign in
                  </Link>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
'use client'

import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '@/lib/AuthContext'

type Mode = 'signin' | 'signup' | 'confirm'

// Custom-styled auth screen (sign in / sign up / email-confirmation code)
// against Cognito's SRP flow via useAuth() -- no Hosted UI redirect, so this
// stays visually consistent with the rest of the app instead of bouncing
// through an AWS-hosted page.
export default function LoginForm() {
  const { signIn, signUp, confirmSignUp, resendCode } = useAuth()
  const [mode, setMode] = useState<Mode>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      await signIn(email, password)
    } catch (err: any) {
      // Cognito's own error for "signed up but never entered the emailed
      // code" -- route straight to the confirmation step instead of just
      // showing a raw SDK error message.
      if (err?.code === 'UserNotConfirmedException') {
        setMode('confirm')
        setNotice('Your account needs email verification -- enter the code we sent you.')
      } else {
        setError(err?.message || 'Sign in failed.')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      await signUp(email, password)
      setMode('confirm')
      setNotice(`We sent a verification code to ${email}.`)
    } catch (err: any) {
      setError(err?.message || 'Sign up failed.')
    } finally {
      setLoading(false)
    }
  }

  const handleConfirm = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      await confirmSignUp(email, code)
      setNotice('Verified! Sign in below.')
      setMode('signin')
      setCode('')
    } catch (err: any) {
      setError(err?.message || 'Verification failed.')
    } finally {
      setLoading(false)
    }
  }

  const handleResend = async () => {
    setError(null)
    try {
      await resendCode(email)
      setNotice('Sent a new code.')
    } catch (err: any) {
      setError(err?.message || 'Could not resend code.')
    }
  }

  return (
    <div className="max-w-md mx-auto mt-8">
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        className="glass-card p-8"
      >
        <div className="text-center mb-6">
          <div className="w-12 h-12 mx-auto rounded-xl bg-gradient-to-br from-indigo-600 via-violet-600 to-fuchsia-600 flex items-center justify-center shadow-lg shadow-indigo-500/30 mb-3">
            <svg viewBox="0 0 24 24" fill="none" className="w-6 h-6 text-white" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </div>
          <h2 className="text-2xl font-extrabold font-display tracking-tight text-slate-900">
            {mode === 'signin' && 'Welcome back'}
            {mode === 'signup' && 'Create your account'}
            {mode === 'confirm' && 'Verify your email'}
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            {mode === 'signin' && 'Sign in to plan and negotiate your next trip.'}
            {mode === 'signup' && 'Takes a few seconds -- just an email and password.'}
            {mode === 'confirm' && 'Enter the code we emailed you.'}
          </p>
        </div>

        {error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl"
          >
            <p className="text-red-800 text-sm font-medium">{error}</p>
          </motion.div>
        )}
        {notice && !error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="mb-4 p-3 bg-emerald-50 border border-emerald-200 rounded-xl"
          >
            <p className="text-emerald-800 text-sm font-medium">{notice}</p>
          </motion.div>
        )}

        <AnimatePresence mode="wait">
          {mode !== 'confirm' && (
            <motion.form
              key="credentials"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onSubmit={mode === 'signin' ? handleSignIn : handleSignUp}
              className="space-y-4"
            >
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">Email</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="glass-input w-full px-4 py-2.5 text-sm"
                  autoComplete="email"
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">Password</label>
                <input
                  type="password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={mode === 'signup' ? 'At least 8 characters' : '••••••••'}
                  className="glass-input w-full px-4 py-2.5 text-sm"
                  autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                />
              </div>

              <motion.button
                type="submit"
                disabled={loading}
                whileHover={{ scale: loading ? 1 : 1.01 }}
                whileTap={{ scale: loading ? 1 : 0.98 }}
                className="btn-gradient w-full px-6 py-3 rounded-2xl text-sm"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="w-4 h-4 rounded-full border-2 border-white/40 border-t-white animate-spin" />
                    {mode === 'signin' ? 'Signing in...' : 'Creating account...'}
                  </span>
                ) : mode === 'signin' ? (
                  'Sign In'
                ) : (
                  'Create Account'
                )}
              </motion.button>
            </motion.form>
          )}

          {mode === 'confirm' && (
            <motion.form
              key="confirm"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onSubmit={handleConfirm}
              className="space-y-4"
            >
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">Verification code</label>
                <input
                  type="text"
                  required
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="123456"
                  className="glass-input w-full px-4 py-2.5 text-sm tracking-widest text-center font-mono"
                  autoComplete="one-time-code"
                />
              </div>
              <motion.button
                type="submit"
                disabled={loading}
                whileHover={{ scale: loading ? 1 : 1.01 }}
                whileTap={{ scale: loading ? 1 : 0.98 }}
                className="btn-gradient w-full px-6 py-3 rounded-2xl text-sm"
              >
                {loading ? 'Verifying...' : 'Verify Email'}
              </motion.button>
              <button
                type="button"
                onClick={handleResend}
                className="w-full text-center text-xs font-semibold text-indigo-600 hover:text-indigo-800"
              >
                Resend code
              </button>
            </motion.form>
          )}
        </AnimatePresence>

        {mode !== 'confirm' && (
          <p className="text-sm text-slate-500 mt-6 text-center">
            {mode === 'signin' ? (
              <>
                Don&apos;t have an account?{' '}
                <button
                  type="button"
                  onClick={() => {
                    setMode('signup')
                    setError(null)
                    setNotice(null)
                  }}
                  className="font-semibold text-indigo-600 hover:text-indigo-800"
                >
                  Create one
                </button>
              </>
            ) : (
              <>
                Already have an account?{' '}
                <button
                  type="button"
                  onClick={() => {
                    setMode('signin')
                    setError(null)
                    setNotice(null)
                  }}
                  className="font-semibold text-indigo-600 hover:text-indigo-800"
                >
                  Sign in
                </button>
              </>
            )}
          </p>
        )}
      </motion.div>
    </div>
  )
}

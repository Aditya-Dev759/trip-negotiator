'use client'

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import {
  AUTH_ENABLED,
  AuthUser,
  confirmSignUp as cognitoConfirmSignUp,
  getCurrentSession,
  resendConfirmationCode as cognitoResendCode,
  signIn as cognitoSignIn,
  signOut as cognitoSignOut,
  signUp as cognitoSignUp,
} from './auth'

interface AuthContextValue {
  authEnabled: boolean
  user: AuthUser | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string) => Promise<void>
  confirmSignUp: (email: string, code: string) => Promise<void>
  resendCode: (email: string) => Promise<void>
  signOut: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

// Wraps the whole app. On mount, checks whether a valid Cognito session is
// already cached (so a page refresh doesn't force a re-login) before
// rendering children -- see the `loading` flag, which callers use to avoid
// flashing the login screen for users who are actually already signed in.
//
// If Cognito isn't configured at all (AUTH_ENABLED false -- e.g. running
// against local_api_server.py with no NEXT_PUBLIC_COGNITO_* env vars set),
// this resolves immediately with no user and no login gate is shown
// anywhere in the app; see page.tsx.
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    getCurrentSession().then((session) => {
      if (cancelled) return
      if (session) {
        const email = session.getIdToken().payload?.email as string | undefined
        setUser({ email: email || '' })
      }
      setLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [])

  const signIn = useCallback(async (email: string, password: string) => {
    const authUser = await cognitoSignIn(email, password)
    setUser(authUser)
  }, [])

  const signUp = useCallback(async (email: string, password: string) => {
    await cognitoSignUp(email, password)
  }, [])

  const confirmSignUp = useCallback(async (email: string, code: string) => {
    await cognitoConfirmSignUp(email, code)
  }, [])

  const resendCode = useCallback(async (email: string) => {
    await cognitoResendCode(email)
  }, [])

  const signOut = useCallback(() => {
    cognitoSignOut()
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider
      value={{ authEnabled: AUTH_ENABLED, user, loading, signIn, signUp, confirmSignUp, resendCode, signOut }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}

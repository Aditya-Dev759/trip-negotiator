'use client'

import React, { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import TripForm from '@/components/TripForm'
import NegotiationProgress from '@/components/NegotiationProgress'
import TripHistory from '@/components/TripHistory'
import LoginForm from '@/components/LoginForm'
import { AuthProvider, useAuth } from '@/lib/AuthContext'

type View = 'form' | 'progress' | 'history'

function HomeInner() {
  const { authEnabled, user, loading, signOut } = useAuth()
  const [tripId, setTripId] = useState<string | null>(null)
  const [showHistory, setShowHistory] = useState(false)

  const view: View = showHistory ? 'history' : tripId ? 'progress' : 'form'

  // Auth is configured (real Cognito user pool + client IDs present) but
  // we haven't finished checking for an already-cached session yet -- avoid
  // flashing the login screen for someone who's actually already signed in.
  if (authEnabled && loading) {
    return (
      <div className="relative min-h-screen overflow-x-hidden flex items-center justify-center">
        <div className="fixed inset-0 -z-10 bg-gradient-to-br from-slate-50 via-indigo-50 to-violet-50" />
        <span className="w-8 h-8 rounded-full border-2 border-indigo-200 border-t-indigo-600 animate-spin" />
      </div>
    )
  }

  const showLoginGate = authEnabled && !user

  return (
    <div className="relative min-h-screen overflow-x-hidden">
      {/* Animated gradient-mesh background */}
      <div className="fixed inset-0 -z-10 bg-gradient-to-br from-slate-50 via-indigo-50 to-violet-50">
        <div className="bg-blob top-[-10%] left-[-5%] w-[32rem] h-[32rem] bg-indigo-300" />
        <div
          className="bg-blob top-[20%] right-[-10%] w-[36rem] h-[36rem] bg-fuchsia-200"
          style={{ animationDelay: '3s' }}
        />
        <div
          className="bg-blob bottom-[-15%] left-[20%] w-[30rem] h-[30rem] bg-sky-200"
          style={{ animationDelay: '6s' }}
        />
        <div className="absolute inset-0 bg-white/30 backdrop-blur-3xl" />
      </div>

      {/* Header */}
      <header className="sticky top-0 z-30 px-4 pt-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto glass-card !rounded-2xl px-5 py-3.5 flex items-center justify-between">
          <motion.button
            onClick={() => {
              setTripId(null)
              setShowHistory(false)
            }}
            className="flex items-center gap-3 group"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 via-violet-600 to-fuchsia-600 flex items-center justify-center shadow-lg shadow-indigo-500/30 group-hover:shadow-glow transition-shadow">
              <svg viewBox="0 0 24 24" fill="none" className="w-5 h-5 text-white" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l7-7 3 3-7 7-3-3z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M2 2l7.586 7.586" />
                <circle cx="11" cy="11" r="2" />
              </svg>
            </div>
            <div className="text-left">
              <h1 className="text-lg sm:text-xl font-extrabold font-display tracking-tight bg-gradient-to-r from-indigo-700 to-fuchsia-600 bg-clip-text text-transparent">
                TripNegotiator
              </h1>
              <p className="hidden sm:block text-[11px] font-medium text-slate-500 -mt-0.5">
                Multi-Agent Trip Planning
              </p>
            </div>
          </motion.button>

          {!showLoginGate && (
            <div className="flex items-center gap-3">
              {/* Pill nav toggle */}
              <div className="relative flex items-center bg-slate-100/80 rounded-full p-1 gap-1">
                {(
                  [
                    { key: 'form', label: 'Plan a Trip' },
                    { key: 'history', label: 'History' },
                  ] as const
                ).map((item) => {
                  const active = view === item.key || (item.key === 'form' && view === 'progress')
                  return (
                    <button
                      key={item.key}
                      onClick={() => {
                        if (item.key === 'history') {
                          setShowHistory(true)
                        } else {
                          setShowHistory(false)
                          if (view === 'progress') setTripId(null)
                        }
                      }}
                      className="relative px-4 py-1.5 text-sm font-semibold rounded-full transition-colors"
                    >
                      {active && (
                        <motion.span
                          layoutId="nav-pill"
                          className="absolute inset-0 bg-white rounded-full shadow-sm"
                          transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                        />
                      )}
                      <span className={`relative z-10 ${active ? 'text-indigo-700' : 'text-slate-500 hover:text-slate-700'}`}>
                        {item.label}
                      </span>
                    </button>
                  )
                })}
              </div>

              {authEnabled && user && (
                <div className="hidden sm:flex items-center gap-2 pl-2 border-l border-slate-200">
                  <span className="text-xs font-medium text-slate-500 max-w-[140px] truncate" title={user.email}>
                    {user.email}
                  </span>
                  <button
                    onClick={signOut}
                    className="text-xs font-semibold text-slate-500 hover:text-rose-600 px-2 py-1 rounded-lg hover:bg-rose-50 transition"
                  >
                    Sign Out
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-10 sm:px-6 lg:px-8 relative z-10">
        <AnimatePresence mode="wait">
          {showLoginGate ? (
            <motion.div
              key="login"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -16 }}
              transition={{ duration: 0.3, ease: 'easeOut' }}
            >
              <LoginForm />
            </motion.div>
          ) : view === 'history' ? (
            <motion.div
              key="history"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -16 }}
              transition={{ duration: 0.3, ease: 'easeOut' }}
            >
              <TripHistory
                onSelectTrip={(id) => {
                  setTripId(id)
                  setShowHistory(false)
                }}
              />
            </motion.div>
          ) : view === 'progress' && tripId ? (
            <motion.div
              key="progress"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -16 }}
              transition={{ duration: 0.3, ease: 'easeOut' }}
            >
              <NegotiationProgress tripId={tripId} onBack={() => setTripId(null)} />
            </motion.div>
          ) : (
            <motion.div
              key="form"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -16 }}
              transition={{ duration: 0.3, ease: 'easeOut' }}
            >
              <TripForm onTripSubmitted={setTripId} />
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* Footer */}
      <footer className="relative z-10 mt-12 px-4 pb-8 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto glass-card !rounded-2xl px-6 py-4 text-center">
          <p className="text-slate-500 text-xs sm:text-sm font-medium">
            TripNegotiator &copy; 2026 &middot; Powered by Multi-Agent AI on AWS
          </p>
        </div>
      </footer>
    </div>
  )
}

export default function Home() {
  return (
    <AuthProvider>
      <HomeInner />
    </AuthProvider>
  )
}

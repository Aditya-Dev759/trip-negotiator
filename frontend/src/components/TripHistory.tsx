'use client'

import React, { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { getUserTrips, TripDetails } from '@/lib/api'

interface TripHistoryProps {
  onSelectTrip?: (tripId: string) => void
}

export default function TripHistory({ onSelectTrip }: TripHistoryProps) {
  const [trips, setTrips] = useState<TripDetails[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchTrips = async () => {
      try {
        const data = await getUserTrips()
        setTrips(data)
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to fetch trip history'
        )
      } finally {
        setLoading(false)
      }
    }

    fetchTrips()
  }, [])

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-center glass-card px-8 py-6">
          <div className="relative w-12 h-12 mx-auto mb-4">
            <div className="absolute inset-0 rounded-full border-4 border-indigo-100"></div>
            <div className="absolute inset-0 rounded-full border-4 border-indigo-600 border-t-transparent animate-spin"></div>
          </div>
          <p className="text-slate-500 text-sm font-medium">Loading trip history...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto">
      <h2 className="text-2xl sm:text-3xl font-extrabold font-display tracking-tight text-slate-900 mb-6">
        Trip History
      </h2>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl">
          <p className="text-red-800 text-sm font-medium">{error}</p>
        </div>
      )}

      {trips.length === 0 ? (
        <div className="glass-card text-center py-16 px-6">
          <div className="text-5xl mb-4">🧭</div>
          <p className="text-slate-600 text-lg font-semibold">No trips yet</p>
          <p className="text-slate-400 text-sm mt-1">Start planning your first adventure!</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {trips.map((trip, i) => (
            <motion.div
              key={trip.trip_id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05, duration: 0.35 }}
              whileHover={{ y: -2 }}
              onClick={() => onSelectTrip && onSelectTrip(trip.trip_id)}
              className="glass-card p-6 hover:shadow-glass-lg transition-shadow cursor-pointer hover:border-indigo-200"
            >
              <div className="flex justify-between items-start gap-4">
                <div>
                  <h3 className="text-lg font-bold font-display text-slate-900">
                    {trip.goal.destination}
                  </h3>
                  <p className="text-slate-600 text-sm mt-1">
                    {trip.goal.length_days} days &middot; ${trip.goal.budget} &middot;{' '}
                    <span className="capitalize">{trip.goal.budget_tier}</span>
                  </p>
                  <p className="text-slate-400 text-xs mt-2">
                    Created: {new Date(trip.created_at).toLocaleDateString()}
                  </p>
                </div>
                <span
                  className={`shrink-0 px-3 py-1 rounded-full text-xs font-bold ${
                    trip.status === 'finalized'
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      : 'bg-amber-50 text-amber-700 border border-amber-200'
                  }`}
                >
                  {trip.status === 'finalized' ? '✓ Finalized' : 'In Progress'}
                </span>
              </div>

              {trip.rounds && (
                <p className="text-sm text-slate-500 mt-4 pt-3 border-t border-slate-100">
                  {trip.rounds.length} round{trip.rounds.length !== 1 ? 's' : ''} of negotiation
                </p>
              )}
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}

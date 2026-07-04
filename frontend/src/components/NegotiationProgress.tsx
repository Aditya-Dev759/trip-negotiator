'use client'

import React, { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { getTripDetails, pollTripStatus, TripDetails, getExchangeRate, ExchangeRateInfo } from '@/lib/api'

interface NegotiationProgressProps {
  tripId: string
  onBack: () => void
}

interface Activity {
  day: number
  activities: string[]
  meals?: string
}

interface SourceRef {
  title: string
  url: string
}

interface ImageResult {
  title: string
  image: string
  thumbnail: string
  source_url: string
}

interface ItineraryProposal {
  destination: string
  summary: string
  days: Activity[]
  tier: string
  revision_note?: string | null
  sources?: SourceRef[]
  images?: ImageResult[]
}

interface CostBreakdown {
  flights?: number
  accommodation?: number
  food?: number
  activities?: number
  local_transport?: number
  [key: string]: number | undefined
}

interface BudgetVerdict {
  status: 'approved' | 'rejected'
  estimated_cost: number
  user_budget: number
  cost_breakdown?: CostBreakdown | null
  objection?: string | null
  sources?: SourceRef[]
}

interface LogisticsVerdict {
  status: 'approved' | 'rejected'
  warnings: string[]
  objection?: string | null
  sources?: SourceRef[]
}

interface BookingVerdict {
  status: 'approved' | 'rejected'
  visa_requirement: string
  objection?: string | null
  sources?: SourceRef[]
}

interface UnresolvedObjection {
  agent: string
  objection: string
}

type AnyVerdict = BudgetVerdict | LogisticsVerdict | BookingVerdict

// Formats a cost_breakdown key like "local_transport" -> "Local transport".
function formatCategoryLabel(key: string): string {
  const spaced = key.replace(/_/g, ' ')
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

function costBreakdownEntries(breakdown: CostBreakdown): [string, number][] {
  return Object.entries(breakdown).filter(
    (entry): entry is [string, number] => typeof entry[1] === 'number' && entry[1] > 0
  )
}

// Compact list used inside per-round audit cards and live-negotiation cards.
function CostBreakdownCompact({ breakdown }: { breakdown: CostBreakdown }) {
  const entries = costBreakdownEntries(breakdown)
  if (entries.length === 0) return null
  return (
    <div className="mt-2 space-y-1 border-t border-slate-100 pt-2">
      {entries.map(([key, value]) => (
        <div key={key} className="flex items-center justify-between text-[11px] text-slate-500">
          <span>{formatCategoryLabel(key)}</span>
          <span className="font-semibold text-slate-600">${Math.round(value)}</span>
        </div>
      ))}
    </div>
  )
}

// Bigger bar-chart style summary used for the "Where Your Budget Goes" card.
function CostBreakdownBars({ breakdown, total }: { breakdown: CostBreakdown; total: number }) {
  const entries = costBreakdownEntries(breakdown).sort((a, b) => b[1] - a[1])
  if (entries.length === 0) return null
  return (
    <div className="space-y-4">
      {entries.map(([key, value], idx) => {
        const pct = total > 0 ? Math.round((value / total) * 100) : 0
        return (
          <div key={key}>
            <div className="flex items-center justify-between text-sm mb-1.5">
              <span className="font-semibold text-slate-700">{formatCategoryLabel(key)}</span>
              <span className="text-slate-500">
                ${Math.round(value)} <span className="text-slate-400">({pct}%)</span>
              </span>
            </div>
            <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${pct}%` }}
                transition={{ duration: 0.8, delay: idx * 0.08, ease: 'easeOut' }}
                className="h-full bg-gradient-to-r from-indigo-500 to-fuchsia-500 rounded-full"
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}

// Small clickable link list, reused wherever a verdict/proposal carries a
// short "sources" list (per-round audit cards, live negotiation stream).
function SourcesCompact({ sources }: { sources?: SourceRef[] }) {
  if (!sources || sources.length === 0) return null
  return (
    <div className="mt-2 space-y-1 border-t border-slate-100 pt-2">
      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">Sources</p>
      <ul className="space-y-0.5">
        {sources.map((s, i) => (
          <li key={i}>
            <a
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[11px] text-indigo-600 hover:text-indigo-800 hover:underline truncate block"
              title={s.url}
            >
              {s.title || s.url}
            </a>
          </li>
        ))}
      </ul>
    </div>
  )
}

// Larger "Sources" panel used at the bottom of the finalized Itinerary tab.
function SourcesSection({ sources }: { sources: SourceRef[] }) {
  if (sources.length === 0) return null
  return (
    <div className="glass-card p-6">
      <h3 className="text-lg font-bold font-display text-slate-800 mb-1">Sources</h3>
      <p className="text-xs text-slate-400 mb-4">
        Live web results this itinerary was grounded in.
      </p>
      <ul className="space-y-2">
        {sources.map((s, i) => (
          <li key={i} className="flex items-start gap-2 text-sm">
            <span className="text-indigo-400 mt-0.5">&bull;</span>
            <a
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-indigo-600 hover:text-indigo-800 hover:underline break-all"
            >
              {s.title || s.url}
            </a>
          </li>
        ))}
      </ul>
    </div>
  )
}

// Photo gallery for the destination. Hotlinked third-party images can
// occasionally 404 or block hotlinking -- onError just hides that one tile
// instead of showing a broken-image icon.
function DestinationGallery({ images, destination }: { images: ImageResult[]; destination: string }) {
  if (images.length === 0) return null
  return (
    <div className="glass-card p-6">
      <h3 className="text-lg font-bold font-display text-slate-800 mb-4">Photos of {destination}</h3>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {images.map((img, i) => (
          <motion.a
            key={i}
            href={img.source_url || img.image}
            target="_blank"
            rel="noopener noreferrer"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.05, duration: 0.35 }}
            whileHover={{ scale: 1.03 }}
            className="group relative block aspect-square rounded-2xl overflow-hidden bg-slate-100 shadow-sm"
          >
            <img
              src={img.thumbnail || img.image}
              alt={img.title || destination}
              loading="lazy"
              className="w-full h-full object-cover group-hover:scale-110 transition duration-500"
              onError={(e) => {
                const tile = (e.target as HTMLImageElement).closest('a')
                if (tile) (tile as HTMLElement).style.display = 'none'
              }}
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition duration-300" />
          </motion.a>
        ))}
      </div>
    </div>
  )
}

export default function NegotiationProgress({
  tripId,
  onBack,
}: NegotiationProgressProps) {
  const [trip, setTrip] = useState<TripDetails | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'itinerary' | 'reviews'>('itinerary')
  const [exchangeRate, setExchangeRate] = useState<ExchangeRateInfo | null>(null)

  // Fetch the live exchange rate once we know both country codes (only
  // available if the traveler picked suggestions from the location
  // autocomplete rather than free-typing origin/destination). Best-effort:
  // silently shows nothing if codes are missing, same currency, or the
  // lookup fails.
  useEffect(() => {
    const originCode = trip?.goal?.origin_country_code
    const destCode = trip?.goal?.destination_country_code
    if (!originCode || !destCode) {
      setExchangeRate(null)
      return
    }
    let cancelled = false
    getExchangeRate(originCode, destCode).then((rate) => {
      if (!cancelled) setExchangeRate(rate)
    })
    return () => {
      cancelled = true
    }
  }, [trip?.goal?.origin_country_code, trip?.goal?.destination_country_code])

  useEffect(() => {
    const fetchTrip = async () => {
      try {
        const data = await getTripDetails(tripId)
        setTrip(data)
        setLoading(false)

        // If not finalized, poll for updates
        if (data.status !== 'finalized' && data.status !== 'error') {
          const finalTrip = await pollTripStatus(tripId, 2000, 300)
          setTrip(finalTrip)
        }
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to fetch trip details'
        )
        setLoading(false)
      }
    }

    fetchTrip()
  }, [tripId])

  if (loading) {
    return (
      <div className="flex flex-col justify-center items-center h-96">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center glass-card p-8 max-w-sm"
        >
          <div className="relative w-16 h-16 mx-auto mb-6">
            <div className="absolute inset-0 rounded-full border-4 border-indigo-100"></div>
            <div className="absolute inset-0 rounded-full border-4 border-indigo-600 border-t-transparent animate-spin"></div>
          </div>
          <h3 className="text-lg font-bold font-display text-slate-800">Initializing Agents</h3>
          <p className="text-slate-500 text-sm mt-2">Setting up travel goals, visa regulations, and lodging costs...</p>
        </motion.div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto">
        <div className="bg-rose-50 border border-rose-200 rounded-2xl p-6 shadow-sm">
          <p className="text-rose-800 font-medium">{error}</p>
          <button
            onClick={onBack}
            className="mt-4 px-6 py-2 bg-rose-600 text-white font-medium rounded-xl hover:bg-rose-700 transition"
          >
            Back
          </button>
        </div>
      </div>
    )
  }

  if (!trip) return null

  // Extract final itinerary and verdicts
  const isFinalized = trip.status === 'finalized'
  const finalItinerary = (trip.final_plan as any)?.final_itinerary as ItineraryProposal | undefined
  const unresolvedObjections = ((trip.final_plan as any)?.unresolved_objections || []) as UnresolvedObjection[]
  const lastRound = trip.rounds && trip.rounds.length > 0 ? trip.rounds[trip.rounds.length - 1] : null
  const finalBudgetVerdict = (lastRound?.budget_verdict ?? null) as BudgetVerdict | null

  return (
    <div className="max-w-4xl mx-auto space-y-8 pb-12">
      {/* Back & Status Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <motion.button
          onClick={onBack}
          whileHover={{ x: -2 }}
          className="self-start inline-flex items-center text-sm font-semibold text-indigo-600 hover:text-indigo-800 transition"
        >
          <svg className="w-4 h-4 mr-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Planner
        </motion.button>

        {/* Live Status Badge */}
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-slate-500">Status:</span>
          {trip.status === 'initializing' && (
            <span className="inline-flex items-center px-3.5 py-1.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-600 mr-1.5 animate-pulse"></span>
              Initializing
            </span>
          )}
          {trip.status === 'negotiating' && (
            <span className="inline-flex items-center px-3.5 py-1.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mr-1.5 animate-pulse"></span>
              Negotiating (Round {trip.rounds?.length || 1})
            </span>
          )}
          {trip.status === 'finalized' && (
            <motion.span
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="inline-flex items-center px-3.5 py-1.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 mr-1.5"></span>
              Finalized Plan
            </motion.span>
          )}
          {trip.status === 'error' && (
            <span className="inline-flex items-center px-3.5 py-1.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-600 mr-1.5"></span>
              Failed
            </span>
          )}
        </div>
      </div>

      {/* Hero Header Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="bg-gradient-to-br from-indigo-900 via-indigo-950 to-slate-900 rounded-3xl shadow-glass-lg border border-indigo-950 p-8 text-white relative overflow-hidden"
      >
        <div className="absolute right-0 top-0 translate-x-12 -translate-y-12 w-64 h-64 bg-indigo-500 rounded-full blur-[100px] opacity-20 animate-blob"></div>
        <div className="absolute left-0 bottom-0 -translate-x-12 translate-y-12 w-64 h-64 bg-fuchsia-500 rounded-full blur-[100px] opacity-10 animate-blob" style={{ animationDelay: '4s' }}></div>
        <div className="relative z-10 space-y-4">
          <div className="space-y-1">
            <span className="text-xs font-bold uppercase tracking-wider text-indigo-400">Destination Overview</span>
            <h2 className="text-3xl sm:text-4xl font-extrabold font-display tracking-tight flex flex-wrap items-center gap-x-3 gap-y-1">
              {trip.goal.origin && (
                <>
                  <span className="text-indigo-300 text-xl sm:text-2xl font-semibold">{trip.goal.origin}</span>
                  <span className="text-indigo-500 text-2xl">&rarr;</span>
                </>
              )}
              {trip.goal.destination}
            </h2>
            {exchangeRate?.available && !exchangeRate.same_currency && (
              <p className="text-xs text-indigo-300 pt-1">
                1 {exchangeRate.from_currency} &asymp; {exchangeRate.rate?.toFixed(2)} {exchangeRate.to_currency}
                {exchangeRate.date && <span className="text-indigo-400"> (as of {exchangeRate.date})</span>}
              </p>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-y-2 gap-x-6 text-sm text-indigo-200">
            <span className="flex items-center">
              <svg className="w-4 h-4 mr-1.5 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              {trip.goal.length_days} Days
            </span>
            <span className="flex items-center">
              <svg className="w-4 h-4 mr-1.5 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              ${trip.goal.budget} Total Budget
            </span>
            <span className="flex items-center">
              <svg className="w-4 h-4 mr-1.5 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" /></svg>
              <span className="capitalize">{trip.goal.budget_tier} Tier</span>
            </span>
          </div>

          <div className="flex flex-wrap gap-2 pt-2">
            {trip.goal.interests.map((interest, i) => (
              <motion.span
                key={interest}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.1 + i * 0.05 }}
                className="px-3 py-1 bg-indigo-500/20 text-indigo-300 rounded-full text-xs font-semibold border border-indigo-500/30 capitalize"
              >
                {interest}
              </motion.span>
            ))}
          </div>

          {isFinalized && finalItinerary?.summary && (
            <p className="text-slate-300 text-sm mt-4 leading-relaxed border-t border-slate-800 pt-4">
              {finalItinerary.summary}
            </p>
          )}
        </div>
      </motion.div>

      {/* Photo gallery */}
      {isFinalized && finalItinerary?.images && finalItinerary.images.length > 0 && (
        <DestinationGallery images={finalItinerary.images} destination={trip.goal.destination} />
      )}

      {/* Cost Breakdown summary -- "where your money goes" */}
      {isFinalized && finalBudgetVerdict?.cost_breakdown && (
        <div className="glass-card p-6">
          <h3 className="text-lg font-bold font-display text-slate-800 mb-1">Where Your Budget Goes</h3>
          <p className="text-xs text-slate-400 mb-4">
            Estimated cost breakdown for this trip &mdash; total &asymp; ${Math.round(finalBudgetVerdict.estimated_cost)}
            {trip.goal.origin && ` (flying from ${trip.goal.origin})`}
          </p>
          <CostBreakdownBars
            breakdown={finalBudgetVerdict.cost_breakdown}
            total={finalBudgetVerdict.estimated_cost}
          />
        </div>
      )}

      {/* Unresolved objections banner (force-finalized after round cap) */}
      {isFinalized && unresolvedObjections.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-5">
          <p className="text-amber-800 font-semibold text-sm mb-2">
            Finalized with {unresolvedObjections.length} unresolved objection{unresolvedObjections.length > 1 ? 's' : ''} (round cap reached)
          </p>
          <ul className="space-y-1.5">
            {unresolvedObjections.map((obj, i) => (
              <li key={i} className="text-xs text-amber-700">
                <span className="font-semibold capitalize">{obj.agent}:</span> {obj.objection}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Main Content Layout */}
      {isFinalized ? (
        <div className="space-y-6">
          {/* Navigation Tabs */}
          <div className="relative flex border-b border-slate-200">
            <button
              onClick={() => setActiveTab('itinerary')}
              className="relative pb-4 px-6 font-semibold text-sm transition"
            >
              <span className={activeTab === 'itinerary' ? 'text-indigo-600' : 'text-slate-500 hover:text-slate-800'}>
                Itinerary Details
              </span>
              {activeTab === 'itinerary' && (
                <motion.span layoutId="tab-underline" className="absolute left-0 right-0 -bottom-px h-0.5 bg-indigo-600" />
              )}
            </button>
            <button
              onClick={() => setActiveTab('reviews')}
              className="relative pb-4 px-6 font-semibold text-sm transition"
            >
              <span className={activeTab === 'reviews' ? 'text-indigo-600' : 'text-slate-500 hover:text-slate-800'}>
                Auditor Verdicts ({trip.rounds?.length || 1} Rounds)
              </span>
              {activeTab === 'reviews' && (
                <motion.span layoutId="tab-underline" className="absolute left-0 right-0 -bottom-px h-0.5 bg-indigo-600" />
              )}
            </button>
          </div>

          {/* ITINERARY TAB */}
          <AnimatePresence mode="wait">
            {activeTab === 'itinerary' && finalItinerary && (
              <motion.div
                key="itinerary"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.25 }}
                className="space-y-6"
              >
                <div className="grid gap-5">
                  {finalItinerary.days.map((dayItem, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, y: 16 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: idx * 0.06, duration: 0.4 }}
                      className="glass-card p-6 hover:shadow-glass-lg transition-shadow"
                    >
                      <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
                        <h3 className="text-lg font-bold font-display text-slate-800 flex items-center gap-2">
                          <span className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-600 to-fuchsia-600 text-white text-xs font-bold flex items-center justify-center">
                            {dayItem.day}
                          </span>
                          Day {dayItem.day}
                        </h3>
                        {dayItem.meals && (
                          <span className="text-xs text-slate-500 bg-slate-50 border border-slate-100 px-3 py-1 rounded-full font-medium">
                            🍴 {dayItem.meals}
                          </span>
                        )}
                      </div>
                      <ul className="space-y-3">
                        {dayItem.activities.map((activity, actIdx) => (
                          <li key={actIdx} className="flex items-start text-slate-700 text-sm">
                            <span className="text-indigo-500 font-bold mr-2 mt-0.5">•</span>
                            {activity}
                          </li>
                        ))}
                      </ul>
                    </motion.div>
                  ))}
                </div>

                {finalItinerary.sources && finalItinerary.sources.length > 0 && (
                  <SourcesSection sources={finalItinerary.sources} />
                )}
              </motion.div>
            )}

            {/* AUDITOR VERDICTS TAB */}
            {activeTab === 'reviews' && (
              <motion.div
                key="reviews"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.25 }}
                className="space-y-8"
              >
                {trip.rounds.map((roundItem, roundIdx) => {
                  const budgetVerdict = (roundItem.budget_verdict ?? null) as BudgetVerdict | null
                  const logisticsVerdict = (roundItem.logistics_verdict ?? null) as LogisticsVerdict | null
                  const bookingVerdict = (roundItem.booking_verdict ?? null) as BookingVerdict | null

                  return (
                    <motion.div
                      key={roundIdx}
                      initial={{ opacity: 0, y: 16 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: roundIdx * 0.08, duration: 0.4 }}
                      className="glass-card p-6 space-y-6"
                    >
                      <div className="flex items-center justify-between border-b border-slate-100 pb-4">
                        <div>
                          <h4 className="text-lg font-bold font-display text-slate-800">Round {roundItem.round} Audit</h4>
                          <p className="text-xs text-slate-400 mt-0.5">
                            State assessment before objections loop
                          </p>
                        </div>
                        <span
                          className={`px-3 py-1 rounded-full text-xs font-bold ${
                            roundItem.all_approved
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : 'bg-amber-50 text-amber-700 border border-amber-200'
                          }`}
                        >
                          {roundItem.all_approved ? 'Passed' : 'Needs Negotiation'}
                        </span>
                      </div>

                      {/* Individual Agents */}
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        {/* Budget Agent */}
                        {budgetVerdict && (
                          <div className="border border-slate-100 rounded-2xl p-4 bg-white/50 space-y-3">
                            <div className="flex items-center justify-between">
                              <span className="text-sm font-bold text-slate-800">Budget Agent</span>
                              <span
                                className={`text-xs font-bold uppercase tracking-wider ${
                                  budgetVerdict.status === 'approved'
                                    ? 'text-emerald-600'
                                    : 'text-rose-600'
                                }`}
                              >
                                {budgetVerdict.status}
                              </span>
                            </div>
                            <div className="text-xs space-y-1.5 text-slate-600">
                              <p>
                                Estimate:{' '}
                                <span className="font-bold">
                                  ${Math.round(budgetVerdict.estimated_cost)}
                                </span>
                              </p>
                              {budgetVerdict.cost_breakdown && (
                                <CostBreakdownCompact breakdown={budgetVerdict.cost_breakdown} />
                              )}
                              {budgetVerdict.objection && (
                                <p className="text-rose-700 bg-rose-50 p-2.5 rounded-lg border border-rose-100 mt-2 font-medium">
                                  {budgetVerdict.objection}
                                </p>
                              )}
                              <SourcesCompact sources={budgetVerdict.sources} />
                            </div>
                          </div>
                        )}

                        {/* Logistics Agent */}
                        {logisticsVerdict && (
                          <div className="border border-slate-100 rounded-2xl p-4 bg-white/50 space-y-3">
                            <div className="flex items-center justify-between">
                              <span className="text-sm font-bold text-slate-800">Logistics Agent</span>
                              <span
                                className={`text-xs font-bold uppercase tracking-wider ${
                                  logisticsVerdict.status === 'approved'
                                    ? 'text-emerald-600'
                                    : 'text-rose-600'
                                }`}
                              >
                                {logisticsVerdict.status}
                              </span>
                            </div>
                            <div className="text-xs space-y-1.5 text-slate-600">
                              {logisticsVerdict.warnings && logisticsVerdict.warnings.length > 0 && (
                                <div className="space-y-1">
                                  <p className="font-medium text-slate-700">Advisories:</p>
                                  <ul className="list-disc list-inside space-y-0.5 text-slate-500">
                                    {logisticsVerdict.warnings.map((w: string, i: number) => (
                                      <li key={i}>{w}</li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                              {logisticsVerdict.objection && (
                                <p className="text-rose-700 bg-rose-50 p-2.5 rounded-lg border border-rose-100 mt-2 font-medium">
                                  {logisticsVerdict.objection}
                                </p>
                              )}
                              <SourcesCompact sources={logisticsVerdict.sources} />
                            </div>
                          </div>
                        )}

                        {/* Booking Agent */}
                        {bookingVerdict && (
                          <div className="border border-slate-100 rounded-2xl p-4 bg-white/50 space-y-3">
                            <div className="flex items-center justify-between">
                              <span className="text-sm font-bold text-slate-800">Booking Agent</span>
                              <span
                                className={`text-xs font-bold uppercase tracking-wider ${
                                  bookingVerdict.status === 'approved'
                                    ? 'text-emerald-600'
                                    : 'text-rose-600'
                                }`}
                              >
                                {bookingVerdict.status}
                              </span>
                            </div>
                            <div className="text-xs space-y-1.5 text-slate-600">
                              <p>
                                Visa rules:{' '}
                                <span className="font-medium">
                                  {bookingVerdict.visa_requirement}
                                </span>
                              </p>
                              {bookingVerdict.objection && (
                                <p className="text-rose-700 bg-rose-50 p-2.5 rounded-lg border border-rose-100 mt-2 font-medium">
                                  {bookingVerdict.objection}
                                </p>
                              )}
                              <SourcesCompact sources={bookingVerdict.sources} />
                            </div>
                          </div>
                        )}
                      </div>
                    </motion.div>
                  )
                })}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      ) : (
        /* LIVE NEGOTIATION STREAM */
        <div className="space-y-6">
          <div className="glass-card p-8 text-center space-y-4">
            <div className="relative w-12 h-12 mx-auto">
              <div className="absolute inset-0 rounded-full border-4 border-indigo-100"></div>
              <div className="absolute inset-0 rounded-full border-4 border-indigo-600 border-t-transparent animate-spin"></div>
            </div>
            <div>
              <h3 className="text-xl font-bold font-display text-slate-800">Negotiation in Progress</h3>
              <p className="text-sm text-slate-500 mt-1.5 leading-relaxed">
                The planning agents are fetching live flight costs, weather trends, and entry rules to cross-examine and audit your itinerary.
              </p>
            </div>
          </div>

          <h3 className="text-xl font-bold font-display text-slate-900 pt-4">Live Activity Streams</h3>
          <div className="space-y-6">
            {trip.rounds && trip.rounds.length > 0 ? (
              trip.rounds.map((roundItem, idx) => {
                const liveItinerary = (roundItem.itinerary ?? null) as ItineraryProposal | null
                const agentCards: { label: string; verdict: AnyVerdict | null }[] = [
                  { label: 'Budget Auditor', verdict: (roundItem.budget_verdict ?? null) as AnyVerdict | null },
                  { label: 'Logistics Auditor', verdict: (roundItem.logistics_verdict ?? null) as AnyVerdict | null },
                  { label: 'Booking Compliance', verdict: (roundItem.booking_verdict ?? null) as AnyVerdict | null },
                ]

                return (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.08, duration: 0.4 }}
                    className="glass-card p-6 space-y-6"
                  >
                    <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                      <h4 className="font-bold font-display text-slate-800">Round {roundItem.round}</h4>
                      <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 border border-amber-100">
                        <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-500 mr-1.5 animate-pulse"></span>
                        Pending Audits
                      </span>
                    </div>

                    {liveItinerary && (
                      <div className="space-y-3 border border-indigo-100 bg-indigo-50/40 rounded-2xl p-4 text-sm">
                        <p className="font-bold text-indigo-950 flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full bg-indigo-600"></span>
                          Proposed Itinerary Plan:
                        </p>
                        <p className="text-slate-600 pl-3.5 italic">
                          &quot;{liveItinerary.summary || 'Created proposed travel segments...'}&quot;
                        </p>
                        {liveItinerary.images && liveItinerary.images.length > 0 && (
                          <div className="flex gap-2 pl-3.5 overflow-x-auto">
                            {liveItinerary.images.slice(0, 4).map((img, i) => (
                              <img
                                key={i}
                                src={img.thumbnail || img.image}
                                alt={img.title}
                                className="w-16 h-16 rounded-xl object-cover shrink-0 shadow-sm"
                                onError={(e) => {
                                  (e.target as HTMLImageElement).style.display = 'none'
                                }}
                              />
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {agentCards.map((agent, agentIdx) => {
                        const budgetCostBreakdown =
                          agent.label === 'Budget Auditor' && agent.verdict
                            ? (agent.verdict as BudgetVerdict).cost_breakdown
                            : null

                        return (
                          <div key={agentIdx} className="border border-slate-100 rounded-2xl p-4 bg-white/50">
                            <p className="text-xs font-bold text-slate-400 tracking-wide uppercase">
                              {agent.label}
                            </p>
                            {agent.verdict ? (
                              <div className="mt-2 space-y-1">
                                <span
                                  className={`text-xs font-bold uppercase ${
                                    agent.verdict.status === 'approved'
                                      ? 'text-emerald-600'
                                      : 'text-rose-600'
                                  }`}
                                >
                                  {agent.verdict.status}
                                </span>
                                {budgetCostBreakdown && (
                                  <CostBreakdownCompact breakdown={budgetCostBreakdown} />
                                )}
                                {agent.verdict.objection && (
                                  <p className="text-xs text-slate-600 leading-normal mt-1 italic border-l-2 border-rose-200 pl-2">
                                    {agent.verdict.objection}
                                  </p>
                                )}
                                <SourcesCompact sources={agent.verdict.sources} />
                              </div>
                            ) : (
                              <p className="text-xs text-slate-400 mt-2 italic flex items-center">
                                <span className="w-1.5 h-1.5 rounded-full bg-slate-300 animate-ping mr-1.5"></span>
                                Waiting...
                              </p>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </motion.div>
                )
              })
            ) : (
              <div className="text-center py-6 text-slate-400 text-sm italic">
                Awaiting proposals from itinerary agent...
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

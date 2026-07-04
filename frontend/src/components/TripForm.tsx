'use client'

import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { submitTrip, TripGoal } from '@/lib/api'
import LocationAutocomplete from './LocationAutocomplete'

interface TripFormProps {
  onTripSubmitted: (tripId: string) => void
}

const INTERESTS: { key: string; label: string; emoji: string }[] = [
  { key: 'beach', label: 'Beach', emoji: '🏖️' },
  { key: 'cultural', label: 'Cultural', emoji: '🏛️' },
  { key: 'food', label: 'Food', emoji: '🍜' },
  { key: 'shopping', label: 'Shopping', emoji: '🛍️' },
  { key: 'nightlife', label: 'Nightlife', emoji: '🌃' },
  { key: 'adventure', label: 'Adventure', emoji: '🧗' },
  { key: 'nature', label: 'Nature', emoji: '🌿' },
  { key: 'museums', label: 'Museums', emoji: '🖼️' },
]

const TIERS: { key: 'budget' | 'midrange' | 'luxury'; label: string; hint: string; emoji: string }[] = [
  { key: 'budget', label: 'Budget', hint: 'Hostels, street food', emoji: '🎒' },
  { key: 'midrange', label: 'Mid-Range', hint: 'Hotels, restaurants', emoji: '🏨' },
  { key: 'luxury', label: 'Luxury', hint: 'Resorts, fine dining', emoji: '✨' },
]

const sectionVariants = {
  hidden: { opacity: 0, y: 14 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.06, duration: 0.4, ease: 'easeOut' as const },
  }),
}

export default function TripForm({ onTripSubmitted }: TripFormProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [formData, setFormData] = useState<TripGoal>({
    origin: '',
    destination: 'Bali',
    origin_country_code: undefined,
    destination_country_code: undefined,
    budget: 2000,
    length_days: 7,
    interests: ['beach', 'culture'],
    budget_tier: 'midrange',
    passport_required: true,
    passport_valid_months: 12,
    age: 30,
  })

  const handleBudgetChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, budget: Number(e.target.value) })
  }

  const handleLengthChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, length_days: Number(e.target.value) })
  }

  const handleAgeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, age: Number(e.target.value) })
  }

  const handleTierChange = (tier: 'budget' | 'midrange' | 'luxury') => {
    setFormData({ ...formData, budget_tier: tier })
  }

  const handleInterestToggle = (interest: string) => {
    setFormData({
      ...formData,
      interests: formData.interests.includes(interest)
        ? formData.interests.filter((i) => i !== interest)
        : [...formData.interests, interest],
    })
  }

  const handlePassportRequiredToggle = () => {
    setFormData({ ...formData, passport_required: !formData.passport_required })
  }

  const handlePassportChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, passport_valid_months: Number(e.target.value) })
  }

  const handleOriginSelect = (display: string, countryCode: string) => {
    setFormData({ ...formData, origin: display, origin_country_code: countryCode })
  }

  const handleOriginText = (text: string) => {
    // Free-typed text without picking a suggestion still counts as the
    // origin, just without a country code (so the exchange-rate widget
    // simply won't have anything to show for this trip).
    setFormData((prev) => ({ ...prev, origin: text, origin_country_code: undefined }))
  }

  const handleDestinationSelect = (display: string, countryCode: string) => {
    setFormData({ ...formData, destination: display, destination_country_code: countryCode })
  }

  const handleDestinationText = (text: string) => {
    setFormData((prev) => ({ ...prev, destination: text, destination_country_code: undefined }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const response = await submitTrip(formData)
      onTripSubmitted(response.trip_id)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to submit trip request'
      )
      setLoading(false)
    }
  }

  const budgetPct = Math.round(((formData.budget - 500) / (100000 - 500)) * 100)
  const lengthPct = Math.round(((formData.length_days - 1) / (30 - 1)) * 100)
  const passportPct = Math.round((formData.passport_valid_months / 60) * 100)

  return (
    <div className="max-w-2xl mx-auto">
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        className="glass-card p-6 sm:p-8"
      >
        <motion.div custom={0} variants={sectionVariants} initial="hidden" animate="visible" className="mb-7">
          <h2 className="text-2xl sm:text-3xl font-extrabold font-display tracking-tight text-slate-900">
            Plan Your Trip
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Tell our AI agents what you&apos;re after &mdash; they&apos;ll negotiate the best possible plan.
          </p>
        </motion.div>

        {error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl"
          >
            <p className="text-red-800 text-sm font-medium">{error}</p>
          </motion.div>
        )}

        <form onSubmit={handleSubmit} className="space-y-7">
          {/* Origin & Destination */}
          <motion.div custom={1} variants={sectionVariants} initial="hidden" animate="visible" className="grid sm:grid-cols-2 gap-5">
            <LocationAutocomplete
              label="Traveling From"
              placeholder="Start typing a city, e.g. Toronto"
              helpText="Used to estimate flight costs, exchange rates, and build your budget breakdown."
              value={formData.origin}
              onSelect={handleOriginSelect}
              onTextChange={handleOriginText}
            />
            <LocationAutocomplete
              label="Destination"
              placeholder="Start typing a city, e.g. Kyoto"
              value={formData.destination}
              onSelect={handleDestinationSelect}
              onTextChange={handleDestinationText}
            />
          </motion.div>

          {/* Age */}
          <motion.div custom={2} variants={sectionVariants} initial="hidden" animate="visible">
            <label className="block text-sm font-semibold text-slate-700 mb-2">Your Age</label>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setFormData((p) => ({ ...p, age: Math.max(1, p.age - 1) }))}
                className="w-10 h-10 shrink-0 rounded-xl glass-input flex items-center justify-center text-slate-600 font-bold hover:text-indigo-600 active:scale-95 transition"
              >
                &minus;
              </button>
              <input
                type="number"
                min="1"
                max="120"
                value={formData.age}
                onChange={handleAgeChange}
                className="glass-input w-24 px-4 py-2.5 text-center font-semibold"
                required
              />
              <button
                type="button"
                onClick={() => setFormData((p) => ({ ...p, age: Math.min(120, p.age + 1) }))}
                className="w-10 h-10 shrink-0 rounded-xl glass-input flex items-center justify-center text-slate-600 font-bold hover:text-indigo-600 active:scale-95 transition"
              >
                +
              </button>
              <p className="text-xs text-slate-500">
                Used to tailor the pace and intensity of recommended activities.
              </p>
            </div>
          </motion.div>

          {/* Budget */}
          <motion.div custom={3} variants={sectionVariants} initial="hidden" animate="visible">
            <div className="flex items-baseline justify-between mb-2">
              <label className="text-sm font-semibold text-slate-700">Total Budget</label>
              <span className="text-lg font-extrabold text-indigo-600">
                ${formData.budget.toLocaleString()}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min="500"
                max="100000"
                step="500"
                value={formData.budget}
                onChange={handleBudgetChange}
                style={{ ['--range-progress' as any]: `${budgetPct}%` }}
                className="w-full"
              />
              <div className="relative shrink-0">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">$</span>
                <input
                  type="number"
                  min="1"
                  step="100"
                  value={formData.budget}
                  onChange={handleBudgetChange}
                  className="glass-input w-28 pl-6 pr-2 py-1.5 text-sm"
                />
              </div>
            </div>
            <p className="text-xs text-slate-500 mt-1.5">
              &asymp; ${Math.round(formData.budget / formData.length_days).toLocaleString()}/day
            </p>
          </motion.div>

          {/* Trip Length */}
          <motion.div custom={4} variants={sectionVariants} initial="hidden" animate="visible">
            <div className="flex items-baseline justify-between mb-2">
              <label className="text-sm font-semibold text-slate-700">Trip Length</label>
              <span className="text-lg font-extrabold text-indigo-600">{formData.length_days} days</span>
            </div>
            <input
              type="range"
              min="1"
              max="30"
              value={formData.length_days}
              onChange={handleLengthChange}
              style={{ ['--range-progress' as any]: `${lengthPct}%` }}
              className="w-full"
            />
          </motion.div>

          {/* Budget Tier */}
          <motion.div custom={5} variants={sectionVariants} initial="hidden" animate="visible">
            <label className="block text-sm font-semibold text-slate-700 mb-2">Budget Tier</label>
            <div className="grid grid-cols-3 gap-2.5">
              {TIERS.map((tier) => {
                const active = formData.budget_tier === tier.key
                return (
                  <motion.button
                    key={tier.key}
                    type="button"
                    onClick={() => handleTierChange(tier.key)}
                    whileTap={{ scale: 0.96 }}
                    className={`relative rounded-2xl p-3.5 text-center border transition-all ${
                      active
                        ? 'bg-gradient-to-br from-indigo-600 to-violet-600 border-indigo-600 text-white shadow-lg shadow-indigo-500/30'
                        : 'glass-pill border-slate-200/80 text-slate-600 hover:border-indigo-200 hover:bg-indigo-50/50'
                    }`}
                  >
                    <div className="text-xl mb-1">{tier.emoji}</div>
                    <div className="text-sm font-bold">{tier.label}</div>
                    <div className={`text-[10px] mt-0.5 ${active ? 'text-indigo-100' : 'text-slate-400'}`}>
                      {tier.hint}
                    </div>
                  </motion.button>
                )
              })}
            </div>
          </motion.div>

          {/* Interests */}
          <motion.div custom={6} variants={sectionVariants} initial="hidden" animate="visible">
            <label className="block text-sm font-semibold text-slate-700 mb-3">Interests</label>
            <div className="flex flex-wrap gap-2.5">
              {INTERESTS.map((interest) => {
                const active = formData.interests.includes(interest.key)
                return (
                  <motion.button
                    key={interest.key}
                    type="button"
                    onClick={() => handleInterestToggle(interest.key)}
                    whileTap={{ scale: 0.94 }}
                    whileHover={{ scale: 1.04 }}
                    className={`flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-semibold border transition-all ${
                      active
                        ? 'bg-gradient-to-r from-indigo-600 to-fuchsia-600 border-transparent text-white shadow-md shadow-indigo-500/30'
                        : 'glass-pill border-slate-200/80 text-slate-600 hover:border-indigo-200'
                    }`}
                  >
                    <span>{interest.emoji}</span>
                    {interest.label}
                  </motion.button>
                )
              })}
            </div>
          </motion.div>

          {/* Passport */}
          <motion.div custom={7} variants={sectionVariants} initial="hidden" animate="visible" className="border-t border-slate-200/70 pt-6">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm font-semibold text-slate-700">I need a passport for this trip</span>
                <p className="text-xs text-slate-500 mt-0.5">
                  Uncheck for domestic travel, or if you&apos;re a citizen of the destination country.
                </p>
              </div>
              <button
                type="button"
                onClick={handlePassportRequiredToggle}
                className={`relative shrink-0 w-12 h-7 rounded-full transition-colors ${
                  formData.passport_required ? 'bg-gradient-to-r from-indigo-600 to-violet-600' : 'bg-slate-300'
                }`}
              >
                <motion.span
                  layout
                  transition={{ type: 'spring', stiffness: 500, damping: 32 }}
                  className="absolute top-1 left-1 w-5 h-5 rounded-full bg-white shadow-md"
                  style={{ x: formData.passport_required ? 20 : 0 }}
                />
              </button>
            </div>

            {formData.passport_required && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                transition={{ duration: 0.25 }}
                className="mt-4 overflow-hidden"
              >
                <div className="flex items-baseline justify-between mb-2">
                  <label className="text-xs font-semibold text-slate-600">Passport Valid For</label>
                  <span className="text-sm font-bold text-indigo-600">{formData.passport_valid_months} months</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="60"
                  value={formData.passport_valid_months}
                  onChange={handlePassportChange}
                  style={{ ['--range-progress' as any]: `${passportPct}%` }}
                  className="w-full"
                />
              </motion.div>
            )}
          </motion.div>

          {/* Submit Button */}
          <motion.div custom={8} variants={sectionVariants} initial="hidden" animate="visible">
            <motion.button
              type="submit"
              disabled={loading}
              whileHover={{ scale: loading ? 1 : 1.01 }}
              whileTap={{ scale: loading ? 1 : 0.98 }}
              className="btn-gradient w-full px-6 py-3.5 rounded-2xl text-base"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 rounded-full border-2 border-white/40 border-t-white animate-spin" />
                  Submitting...
                </span>
              ) : (
                'Plan My Trip ✨'
              )}
            </motion.button>
          </motion.div>
        </form>

        <p className="text-sm text-slate-500 mt-6 text-center">
          Our AI agents will negotiate the best trip plan for you within{' '}
          <span className="font-semibold text-slate-700">{formData.length_days} days</span> and{' '}
          <span className="font-semibold text-slate-700">${formData.budget.toLocaleString()}</span> budget.
        </p>
      </motion.div>
    </div>
  )
}

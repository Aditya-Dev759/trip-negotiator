'use client'

import React, { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { searchLocations, LocationSuggestion } from '@/lib/api'

interface LocationAutocompleteProps {
  label: string
  placeholder?: string
  helpText?: string
  value: string
  onSelect: (display: string, countryCode: string) => void
  onTextChange?: (text: string) => void
}

// Debounced location search-and-select combobox. Backed by the backend's
// free/keyless Open-Meteo geocoding proxy. The underlying input stays a
// normal editable text field (typing still works, and free text is still
// accepted if the user never picks a suggestion -- some destinations,
// especially very small towns, may not resolve), but the intended flow is
// type-to-search then click a suggestion, which also captures the ISO
// country code needed for the exchange-rate lookup elsewhere.
export default function LocationAutocomplete({
  label,
  placeholder,
  helpText,
  value,
  onSelect,
  onTextChange,
}: LocationAutocompleteProps) {
  const [query, setQuery] = useState(value)
  const [suggestions, setSuggestions] = useState<LocationSuggestion[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [focused, setFocused] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    setQuery(value)
  }, [value])

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleChange = (text: string) => {
    setQuery(text)
    onTextChange?.(text)

    if (debounceRef.current) clearTimeout(debounceRef.current)

    if (text.trim().length < 2) {
      setSuggestions([])
      setIsOpen(false)
      return
    }

    debounceRef.current = setTimeout(async () => {
      setLoading(true)
      const results = await searchLocations(text)
      setSuggestions(results)
      setIsOpen(results.length > 0)
      setLoading(false)
    }, 300)
  }

  const handleSelect = (s: LocationSuggestion) => {
    const display = s.admin1 && s.admin1 !== s.name
      ? `${s.name}, ${s.admin1}, ${s.country}`
      : `${s.name}, ${s.country}`
    setQuery(display)
    setIsOpen(false)
    onSelect(display, s.country_code)
  }

  return (
    <div ref={containerRef} className="relative">
      <label className="block text-sm font-semibold text-slate-700 mb-2">{label}</label>
      <div className="relative">
        <span
          className={`pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 transition-colors ${
            focused ? 'text-indigo-500' : 'text-slate-400'
          }`}
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a2 2 0 01-2.828 0l-4.243-4.243a8 8 0 1111.314 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </span>
        <input
          type="text"
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          onFocus={() => {
            setFocused(true)
            suggestions.length > 0 && setIsOpen(true)
          }}
          onBlur={() => setFocused(false)}
          placeholder={placeholder}
          className="glass-input w-full pl-11 pr-4 py-2.5 text-sm text-slate-800 placeholder:text-slate-400"
          required
          autoComplete="off"
        />
        {loading && (
          <span className="absolute right-3.5 top-1/2 -translate-y-1/2">
            <span className="block w-4 h-4 rounded-full border-2 border-indigo-300 border-t-indigo-600 animate-spin" />
          </span>
        )}
      </div>
      {helpText && <p className="text-xs text-slate-500 mt-1.5">{helpText}</p>}

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.15 }}
            className="absolute z-30 mt-2 w-full bg-white/90 backdrop-blur-xl border border-white/60 rounded-2xl shadow-glass-lg max-h-64 overflow-y-auto p-1.5"
          >
            {!loading &&
              suggestions.map((s, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => handleSelect(s)}
                  className="w-full flex items-center gap-2.5 text-left px-3.5 py-2.5 rounded-xl hover:bg-indigo-50 transition text-sm group"
                >
                  <span className="text-indigo-400 group-hover:text-indigo-600 transition-colors">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a2 2 0 01-2.828 0l-4.243-4.243a8 8 0 1111.314 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                  </span>
                  <span>
                    <span className="font-semibold text-slate-800">{s.name}</span>
                    <span className="text-slate-500">
                      {s.admin1 && s.admin1 !== s.name ? `, ${s.admin1}` : ''}, {s.country}
                    </span>
                  </span>
                </button>
              ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

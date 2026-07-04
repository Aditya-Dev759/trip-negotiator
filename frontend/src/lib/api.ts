import axios, { AxiosInstance } from 'axios'
import { getCurrentSession } from './auth'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001'

const api: AxiosInstance = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Attaches the signed-in user's Cognito ID token as a Bearer header on
// every request when one is available. Only POST /trips is actually gated
// behind the JWT authorizer in API Gateway (infra/apigateway.tf) -- the
// read-only routes stay public -- but sending it everywhere is harmless and
// simpler than special-casing one endpoint. If there's no cached session
// (Cognito not configured, e.g. local dev, or the user isn't signed in)
// this is a no-op and the request goes out unauthenticated exactly as
// before this feature existed.
//
// This must go through getCurrentSession() (async, calls CognitoUser's own
// getSession()), not a synchronous read of some CognitoUser instance's
// .signInUserSession -- CognitoUserPool.getCurrentUser() constructs a brand
// new CognitoUser object on every call, and that field is only populated as
// a side effect of calling .getSession() on that specific instance. A
// previous synchronous getCachedIdToken() helper read .signInUserSession
// off a throwaway instance that had never had .getSession() called on it,
// so it silently returned null forever -- valid tokens sat in localStorage
// the whole time (confirmed via a real signed-in session's JWT: correct
// aud/iss, not expired) but were never attached, and every POST /trips came
// back 401 from the Cognito JWT authorizer with no way to tell why from the
// response alone.
api.interceptors.request.use(async (config) => {
  const session = await getCurrentSession()
  if (session) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${session.getIdToken().getJwtToken()}`
  }
  return config
})

export interface TripGoal {
  // Where the traveler is departing from -- used to ground flight-cost
  // estimates and the cost breakdown shown to the user.
  origin: string
  destination: string
  // ISO 3166-1 alpha-2 country codes, populated when the traveler picks a
  // suggestion from the location autocomplete (see LocationAutocomplete.tsx)
  // rather than free-typing. Used to look up the live exchange rate.
  origin_country_code?: string
  destination_country_code?: string
  budget: number
  length_days: number
  interests: string[]
  budget_tier: 'budget' | 'midrange' | 'luxury'
  // Whether the traveler needs a passport for this trip at all. False for
  // domestic travel, or travel to a country the user is a citizen of.
  passport_required: boolean
  // Only meaningful when passport_required is true.
  passport_valid_months: number
  // Traveler's age -- used to tailor the pace/intensity of recommended activities.
  age: number
}

export interface TripResponse {
  trip_id: string
  status: string
  message: string
}

export interface NegotiationRound {
  round: number
  itinerary: unknown
  budget_verdict: unknown
  logistics_verdict: unknown
  booking_verdict: unknown
  all_approved: boolean
}

export interface TripDetails {
  trip_id: string
  goal: TripGoal
  status: string
  rounds: NegotiationRound[]
  final_plan?: unknown
  created_at: string
  updated_at: string
}

export interface LocationSuggestion {
  name: string
  admin1: string
  country: string
  country_code: string
  latitude: number | null
  longitude: number | null
}

export interface ExchangeRateInfo {
  available: boolean
  from_currency?: string
  to_currency?: string
  rate?: number
  date?: string | null
  same_currency?: boolean
}

// Create a new trip
export const submitTrip = async (goal: TripGoal): Promise<TripResponse> => {
  const response = await api.post('/trips', { goal })
  return response.data
}

// Get trip details and negotiation history
export const getTripDetails = async (tripId: string): Promise<TripDetails> => {
  const response = await api.get(`/trips/${tripId}`)
  return response.data
}

// Get all trips for current user
export const getUserTrips = async (): Promise<TripDetails[]> => {
  const response = await api.get('/trips')
  return response.data
}

// Search for a place name (city/region/country) via the backend's
// Open-Meteo-backed geocoding proxy, used to power the location-picker
// autocomplete instead of free-text entry. Never throws -- returns []
// on any failure so the input can gracefully fall back to plain typing.
export const searchLocations = async (query: string): Promise<LocationSuggestion[]> => {
  if (!query || query.trim().length === 0) return []
  try {
    const response = await api.get('/locations/search', { params: { q: query } })
    return response.data.results || []
  } catch {
    return []
  }
}

// Latest exchange rate between two ISO country codes, via the backend's
// Frankfurter-backed proxy. Never throws -- returns {available: false} on
// any failure so the UI can just hide the widget.
export const getExchangeRate = async (
  fromCountry: string,
  toCountry: string
): Promise<ExchangeRateInfo> => {
  try {
    const response = await api.get('/exchange-rate', {
      params: { from_country: fromCountry, to_country: toCountry },
    })
    return response.data
  } catch {
    return { available: false }
  }
}

// Poll for trip updates (for real-time updates)
export const pollTripStatus = async (
  tripId: string,
  interval: number = 1000,
  maxAttempts: number = 180
): Promise<TripDetails> => {
  let attempts = 0

  return new Promise((resolve, reject) => {
    const timer = setInterval(async () => {
      attempts++

      try {
        const trip = await getTripDetails(tripId)

        // If finalized or max attempts reached, stop polling
        if (trip.status === 'finalized' || attempts >= maxAttempts) {
          clearInterval(timer)
          resolve(trip)
          return
        }
      } catch (error) {
        if (attempts >= maxAttempts) {
          clearInterval(timer)
          reject(error)
        }
      }
    }, interval)
  })
}

export default api

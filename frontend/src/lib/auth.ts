// Thin wrapper around amazon-cognito-identity-js.
//
// Uses SRP auth (authenticateUser's default flow) -- the password itself
// never goes over the wire, only a zero-knowledge proof derived from it.
// This needs no Cognito Hosted UI domain resource and no OAuth redirect
// dance, just the user pool + a no-secret app client (infra/cognito.tf's
// spa_client), which keeps the login screen fully custom-styled instead of
// bouncing through an AWS-hosted page.
//
// Gracefully degrades to "auth disabled" when NEXT_PUBLIC_COGNITO_USER_POOL_ID
// / NEXT_PUBLIC_COGNITO_CLIENT_ID aren't set (e.g. local dev against
// local_api_server.py, which never checks a JWT at all -- only the real
// API Gateway authorizer does) so local development never requires a real
// Cognito user pool to exist.
import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
  CognitoUserSession,
  CognitoUserAttribute,
  ICognitoUserPoolData,
} from 'amazon-cognito-identity-js'

const USER_POOL_ID = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID || ''
const CLIENT_ID = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID || ''

export const AUTH_ENABLED = Boolean(USER_POOL_ID && CLIENT_ID)

let pool: CognitoUserPool | null = null

function getPool(): CognitoUserPool {
  if (!AUTH_ENABLED) {
    throw new Error(
      'Cognito is not configured (NEXT_PUBLIC_COGNITO_USER_POOL_ID / NEXT_PUBLIC_COGNITO_CLIENT_ID missing). ' +
        'Set these in frontend/.env.local after deploying infra (see infra/cognito.tf outputs), or run against local_api_server.py which does not require login.'
    )
  }
  if (!pool) {
    const data: ICognitoUserPoolData = { UserPoolId: USER_POOL_ID, ClientId: CLIENT_ID }
    pool = new CognitoUserPool(data)
  }
  return pool
}

export interface AuthUser {
  email: string
}

// Wraps CognitoUser.getSession's callback API in a Promise. Resolves null
// (not an error) when there's simply no signed-in user yet -- that's the
// normal "not logged in" state, not a failure.
//
// This is the ONLY correct way to read the current session synchronously
// from the outside: CognitoUserPool.getCurrentUser() constructs a brand new
// CognitoUser object on every call, and that object's .signInUserSession
// field starts out null -- it's only populated as a side effect of calling
// .getSession() on that specific instance. A previous helper here
// (getCachedIdToken) read .signInUserSession directly off a throwaway
// getCurrentUser() instance without ever calling .getSession() on it, so it
// always returned null even when a fully valid session was sitting in
// localStorage -- every POST /trips silently went out unauthenticated and
// came back 401 from the Cognito JWT authorizer. api.ts's axios interceptor
// now calls this function (awaited) before every request instead.
export function getCurrentSession(): Promise<CognitoUserSession | null> {
  if (!AUTH_ENABLED) return Promise.resolve(null)
  const cognitoUser = getPool().getCurrentUser()
  if (!cognitoUser) return Promise.resolve(null)

  return new Promise((resolve) => {
    cognitoUser.getSession((err: Error | null, session: CognitoUserSession | null) => {
      if (err || !session || !session.isValid()) {
        resolve(null)
        return
      }
      resolve(session)
    })
  })
}

export function signUp(email: string, password: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const attributeList = [
      new CognitoUserAttribute({ Name: 'email', Value: email }),
    ]
    getPool().signUp(email, password, attributeList, [], (err) => {
      if (err) {
        reject(err)
        return
      }
      resolve()
    })
  })
}

export function confirmSignUp(email: string, code: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const cognitoUser = new CognitoUser({ Username: email, Pool: getPool() })
    cognitoUser.confirmRegistration(code, true, (err) => {
      if (err) {
        reject(err)
        return
      }
      resolve()
    })
  })
}

export function resendConfirmationCode(email: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const cognitoUser = new CognitoUser({ Username: email, Pool: getPool() })
    cognitoUser.resendConfirmationCode((err) => {
      if (err) {
        reject(err)
        return
      }
      resolve()
    })
  })
}

export function signIn(email: string, password: string): Promise<AuthUser> {
  return new Promise((resolve, reject) => {
    const cognitoUser = new CognitoUser({ Username: email, Pool: getPool() })
    const authDetails = new AuthenticationDetails({ Username: email, Password: password })

    cognitoUser.authenticateUser(authDetails, {
      onSuccess: () => {
        resolve({ email })
      },
      onFailure: (err) => {
        reject(err)
      },
    })
  })
}

export function signOut(): void {
  if (!AUTH_ENABLED) return
  const cognitoUser = getPool().getCurrentUser()
  if (cognitoUser) {
    cognitoUser.signOut()
  }
}

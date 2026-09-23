/**
 * frontend/src/services/authService.ts
 *
 * Authentication service for the Nimbus Zero Workbench.
 * Handles user registration, login, JWT token persistence, and profile verification.
 */

import { BACKEND_CONFIG, backendUrl } from "./backendConfig"

const TOKEN_KEY = "sovereign-jwt-token"
const USER_KEY = "sovereign-user-profile"

export interface UserProfile {
  id: string
  email: string
  name: string
  organization?: string | null
  role: string
  created_at?: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: UserProfile
}

export interface RegisterPayload {
  name: string
  email: string
  password: string
  organization?: string
}

export interface LoginPayload {
  email: string
  password: string
}

export const authService = {
  getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY)
  },

  setToken(token: string): void {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem("sovereign-auth", "true")
  },

  removeToken(): void {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    localStorage.removeItem("sovereign-auth")
    localStorage.removeItem("sovereign-user-email")
    localStorage.removeItem("sovereign-user-name")
    localStorage.removeItem("sovereign-user-organization")
  },

  getSavedUser(): UserProfile | null {
    const raw = localStorage.getItem(USER_KEY)
    if (!raw) return null
    try {
      return JSON.parse(raw) as UserProfile
    } catch {
      return null
    }
  },

  setSavedUser(user: UserProfile): void {
    localStorage.setItem(USER_KEY, JSON.stringify(user))
    localStorage.setItem("sovereign-user-email", user.email)
    localStorage.setItem("sovereign-user-name", user.name)
    if (user.organization) {
      localStorage.setItem("sovereign-user-organization", user.organization)
    }
  },

  isAuthenticated(): boolean {
    return Boolean(
      this.getToken() || localStorage.getItem("sovereign-auth") === "true",
    )
  },

  async register(payload: RegisterPayload): Promise<AuthResponse> {
    const response = await fetch(
      backendUrl(BACKEND_CONFIG.endpoints.auth.register),
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    )

    if (!response.ok) {
      const errorData = await response
        .json()
        .catch(() => ({ detail: "Registration failed." }))
      throw new Error(
        errorData.detail || `Registration failed (${response.status})`,
      )
    }

    const data: AuthResponse = await response.json()
    this.setToken(data.access_token)
    this.setSavedUser(data.user)
    return data
  },

  async login(payload: LoginPayload): Promise<AuthResponse> {
    const response = await fetch(
      backendUrl(BACKEND_CONFIG.endpoints.auth.login),
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    )

    if (!response.ok) {
      const errorData = await response
        .json()
        .catch(() => ({ detail: "Authentication failed." }))
      throw new Error(
        errorData.detail || `Authentication failed (${response.status})`,
      )
    }

    const data: AuthResponse = await response.json()
    this.setToken(data.access_token)
    this.setSavedUser(data.user)
    return data
  },

  async verifyToken(token?: string): Promise<{
    valid: boolean
    user?: UserProfile | null
  }> {
    const tokenToVerify = token || this.getToken()
    if (!tokenToVerify) return { valid: false }

    try {
      const response = await fetch(
        backendUrl(BACKEND_CONFIG.endpoints.auth.verify),
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${tokenToVerify}`,
          },
          body: JSON.stringify({ token: tokenToVerify }),
        },
      )

      if (!response.ok) return { valid: false }

      const data = await response.json()
      if (data.valid && data.user) {
        this.setSavedUser(data.user)
      }
      return data
    } catch {
      return { valid: false }
    }
  },

  async getCurrentUser(): Promise<UserProfile | null> {
    const token = this.getToken()
    if (!token) return null

    try {
      const response = await fetch(
        backendUrl(BACKEND_CONFIG.endpoints.auth.me),
        {
          headers: { Authorization: `Bearer ${token}` },
        },
      )

      if (!response.ok) {
        if (response.status === 401) this.removeToken()
        return null
      }

      const user: UserProfile = await response.json()
      this.setSavedUser(user)
      return user
    } catch {
      return this.getSavedUser()
    }
  },

  async logout(): Promise<void> {
    const token = this.getToken()
    if (token) {
      try {
        await fetch(backendUrl(BACKEND_CONFIG.endpoints.auth.logout), {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        })
      } catch {
        // Ignore network errors on logout
      }
    }
    this.removeToken()
  },
}

import { FormEvent, useEffect, useState } from "react"
import {
  ArrowRight,
  BarChart3,
  Eye,
  EyeOff,
  Infinity,
  LockKeyhole,
  Mail,
  Moon,
  Orbit,
  Settings2,
  ShieldCheck,
  Sun,
  UsersRound,
} from "lucide-react"
import { useNavigate } from "react-router-dom"
import { useToast } from "../components/ui/Toast"
import { authService } from "../services/authService"

type LoginProps = {
  onLogin: (email: string, name?: string, organization?: string) => void
}

function SovereignMark({ size = 48 }: { size?: number }) {
  return (
    <div
      className="sovereign-mark"
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      <svg
        viewBox="0 0 48 48"
        width={size * 0.72}
        height={size * 0.72}
        fill="none"
      >
        <path
          d="M24 4 39 12.5v17L24 38l-15-8.5v-17L24 4Z"
          stroke="currentColor"
          strokeWidth="3"
        />
        <path
          d="m24 11 9 5v10l-9 5-9-5V16l9-5Z"
          stroke="currentColor"
          strokeWidth="3"
        />
        <path
          d="m19 19 5-3 5 3-5 3-5-3Zm0 7 5-3 5 3-5 3-5-3Z"
          stroke="currentColor"
          strokeWidth="2.4"
        />
      </svg>
    </div>
  )
}

export function Login({ onLogin }: LoginProps) {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [remember, setRemember] = useState(true)
  const [loading, setLoading] = useState(false)
  const [mode, setMode] =
    useState<"login" | "verify" | "signup" | "forgot" | "access">("login")
  const [error, setError] = useState("")
  const [sent, setSent] = useState(false)
  const [light, setLight] = useState(
    () => localStorage.getItem("sovereign-login-theme") === "light",
  )

  useEffect(() => {
    document.documentElement.classList.toggle("light", light)
    localStorage.setItem("sovereign-login-theme", light ? "light" : "dark")
  }, [light])

  async function submitLogin(e: FormEvent) {
    e.preventDefault()
    setError("")
    if (!email.trim()) return setError("Work email is required.")
    if (!/^\S+@\S+\.\S+$/.test(email))
      return setError("Enter a valid work email.")
    if (!password) return setError("Password is required.")
    if (password.length < 4)
      return setError("Password must contain at least 4 characters.")

    setLoading(true)
    try {
      const res = await authService.login({ email: email.trim(), password })
      onLogin(res.user.email, res.user.name, res.user.organization || undefined)
      showToast("Authentication successful. Welcome to Sovereign AI.")
      navigate("/")
    } catch (err: any) {
      setError(err.message || "Invalid email or password.")
    } finally {
      setLoading(false)
    }
  }

  async function submitVerification(e: FormEvent) {
    e.preventDefault()
    setError("")
    if (!/^\S+@\S+\.\S+$/.test(email))
      return setError("Enter a valid work email.")
    if (!password) return setError("Password is required for authentication.")
    if (password.length < 4)
      return setError("Password must contain at least 4 characters.")

    setLoading(true)
    try {
      const res = await authService.login({ email: email.trim(), password })
      onLogin(res.user.email, res.user.name, res.user.organization || undefined)
      showToast("Authentication successful. Welcome to Sovereign AI.")
      navigate("/")
    } catch (err: any) {
      setError(err.message || "Authentication failed.")
    } finally {
      setLoading(false)
    }
  }

  function demoLogin() {
    setLoading(true)
    authService.setToken("demo-sovereign-token")
    authService.setSavedUser({
      id: "demo-user-1",
      email: "demo@sovereign.ai",
      name: "Demo Operator",
      organization: "Sovereign Industrial",
      role: "operator",
    })
    onLogin("demo@sovereign.ai", "Demo Operator", "Sovereign Industrial")
    showToast("Demo workspace opened")
    navigate("/")
    setLoading(false)
  }

  async function submitSignup(e: FormEvent) {
    e.preventDefault()
    setError("")
    const form = e.currentTarget as HTMLFormElement
    const data = new FormData(form)
    const name = String(data.get("name") || "").trim()
    const organization = String(data.get("organization") || "").trim()
    const signupEmail = String(data.get("email") || "").trim()
    const signupPassword = String(data.get("password") || "")
    const confirmPassword = String(data.get("confirmPassword") || "")

    if (!name) return setError("Full name is required.")
    if (!organization) return setError("Organization is required.")
    if (!/^\S+@\S+\.\S+$/.test(signupEmail))
      return setError("Enter a valid work email.")
    if (signupPassword.length < 6)
      return setError("Password must contain at least 6 characters.")
    if (signupPassword !== confirmPassword)
      return setError("Passwords do not match.")

    setLoading(true)
    try {
      const res = await authService.register({
        name,
        email: signupEmail,
        password: signupPassword,
        organization,
      })
      onLogin(res.user.email, res.user.name, res.user.organization || undefined)
      showToast("Account created successfully")
      navigate("/")
    } catch (err: any) {
      setError(err.message || "Registration failed.")
    } finally {
      setLoading(false)
    }
  }

  function submitForgot(e: FormEvent) {
    e.preventDefault()
    if (!/^\S+@\S+\.\S+$/.test(email))
      return setError("Enter a valid work email.")
    setError("")
    setSent(true)
  }

  function submitAccess(e: FormEvent) {
    e.preventDefault()
    setError("")
    setSent(true)
  }

  const resetMode = (
    next: "login" | "verify" | "signup" | "forgot" | "access",
  ) => {
    setMode(next)
    setError("")
    setSent(false)
  }

  return (
    <main className="sovereign-login-page">
      <div className="sovereign-noise" aria-hidden="true" />

      <header className="sovereign-login-header">
        <button
          className="sovereign-brand"
          type="button"
          onClick={() => resetMode("login")}
          aria-label="Sovereign AI home"
        >
          <SovereignMark size={44} />
          <span>Sovereign AI</span>
        </button>
        <div className="sovereign-header-right">
          <span>On-Premise</span>
          <i />
          <span>Secure</span>
          <i />
          <span>Private</span>
          <i />
          <span>Built for Critical Industries</span>
          <button
            className="sovereign-theme-button"
            onClick={() => setLight((v) => !v)}
            aria-label="Toggle theme"
          >
            {light ? <Moon size={15} /> : <Sun size={15} />}
          </button>
        </div>
      </header>

      <div className="sovereign-login-content">
        <section className="sovereign-hero">
          <div className="sovereign-kicker">YOUR PRIVATE AI WORKBENCH</div>
          <h1>
            AI for a<br />
            <span>Sovereign Tomorrow</span>
          </h1>
          <p className="sovereign-hero-copy">
            Secure. Local. Intelligent.
            <br />
            Built for organizations that demand control,
            <br />
            privacy and real impact.
          </p>

          <div className="sovereign-feature-list">
            <div className="sovereign-feature">
              <span className="sovereign-feature-icon">
                <ShieldCheck />
              </span>
              <div>
                <strong>Private &amp; Secure</strong>
                <small>Your data stays within your infrastructure</small>
              </div>
            </div>
            <div className="sovereign-feature">
              <span className="sovereign-feature-icon">
                <Orbit />
              </span>
              <div>
                <strong>On-Premise Deployment</strong>
                <small>Complete control, no external dependencies</small>
              </div>
            </div>
            <div className="sovereign-feature">
              <span className="sovereign-feature-icon">
                <UsersRound />
              </span>
              <div>
                <strong>Built for Critical Industries</strong>
                <small>Reliable. Robust. Real-world ready.</small>
              </div>
            </div>
            <div className="sovereign-feature">
              <span className="sovereign-feature-icon">
                <Infinity />
              </span>
              <div>
                <strong>One AI. Infinite Possibilities.</strong>
                <small>Analyze. Automate. Accelerate.</small>
              </div>
            </div>
          </div>

          <div className="sovereign-quote">
            “Sovereign AI — Intelligence
            <br />
            that works for you, on your terms.”
            <span />
          </div>

          <div className="sovereign-orbit-visual" aria-hidden="true">
            <div className="orbit-ring orbit-ring-one" />
            <div className="orbit-ring orbit-ring-two" />
            <div className="orbit-ring orbit-ring-three" />
            <div className="sovereign-orb">
              <div />
              <div />
              <div />
            </div>
            <div className="orbit-pill orbit-pill-analyze">
              <BarChart3 size={18} /> Analyze
            </div>
            <div className="orbit-pill orbit-pill-automate">
              <Settings2 size={18} /> Automate
            </div>
            <div className="orbit-pill orbit-pill-accelerate">
              <ArrowRight size={18} /> Accelerate
            </div>
            <span className="orbit-dot dot-one" />
            <span className="orbit-dot dot-two" />
            <span className="orbit-dot dot-three" />
          </div>
        </section>

        <section className="sovereign-auth-side">
          <div className="sovereign-auth-card">
            <div className="sovereign-auth-logo">
              <SovereignMark size={55} />
            </div>
            <div className="sovereign-auth-title">
              <h2>
                {mode === "login"
                  ? "Welcome back"
                  : mode === "verify"
                    ? "Verify your identity"
                    : mode === "signup"
                      ? "Create your account"
                      : mode === "forgot"
                        ? "Reset password"
                        : "Request access"}
              </h2>
              <p>
                {mode === "login"
                  ? "Sign in to access your secure AI workspace"
                  : mode === "verify"
                    ? "Enter your credentials again to continue securely"
                    : mode === "signup"
                      ? "Create your private Sovereign AI workspace"
                      : mode === "forgot"
                        ? "We will send reset instructions to your work email"
                        : "Tell us about your organization"}
              </p>
            </div>

            {mode === "login" && (
              <form onSubmit={submitLogin} className="sovereign-auth-form">
                <label>
                  <span>Email</span>
                  <div className="sovereign-input">
                    <Mail />
                    <input
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@example.com"
                      type="email"
                      autoComplete="email"
                    />
                  </div>
                </label>
                <label>
                  <span>Password</span>
                  <div className="sovereign-input">
                    <LockKeyhole />
                    <input
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Enter your password"
                      type={showPassword ? "text" : "password"}
                      autoComplete="current-password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                    >
                      {showPassword ? <EyeOff /> : <Eye />}
                    </button>
                  </div>
                </label>
                {error && <div className="sovereign-error">{error}</div>}
                <div className="sovereign-auth-options">
                  <label className="sovereign-check">
                    <input
                      type="checkbox"
                      checked={remember}
                      onChange={(e) => setRemember(e.target.checked)}
                    />
                    <span>Remember me</span>
                  </label>
                  <button
                    type="button"
                    className="sovereign-text-button"
                    onClick={() => resetMode("forgot")}
                  >
                    Forgot password?
                  </button>
                </div>
                <button className="sovereign-primary-button" disabled={loading}>
                  {loading ? (
                    <span className="sovereign-spinner" />
                  ) : (
                    <>
                      Sign In <ArrowRight size={18} />
                    </>
                  )}
                </button>
                <div className="sovereign-or">
                  <span>or</span>
                </div>
                <button
                  className="sovereign-demo-button"
                  type="button"
                  onClick={demoLogin}
                  disabled={loading}
                >
                  Try Demo Workspace
                </button>
                <p className="sovereign-signup">
                  New user?{" "}
                  <button type="button" onClick={() => resetMode("signup")}>
                    Create account
                  </button>
                </p>
              </form>
            )}

            {mode === "verify" && (
              <form
                onSubmit={submitVerification}
                className="sovereign-auth-form"
              >
                <div className="sovereign-verify-note">
                  <ShieldCheck size={17} />
                  <span>Second-step authentication required</span>
                </div>
                <label>
                  <span>Authentication Email</span>
                  <div className="sovereign-input">
                    <Mail />
                    <input
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      type="email"
                      autoFocus
                    />
                  </div>
                </label>
                <label>
                  <span>Authentication Password</span>
                  <div className="sovereign-input">
                    <LockKeyhole />
                    <input
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Re-enter your password"
                      type={showPassword ? "text" : "password"}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                    >
                      {showPassword ? <EyeOff /> : <Eye />}
                    </button>
                  </div>
                </label>
                {error && <div className="sovereign-error">{error}</div>}
                <label className="sovereign-check">
                  <input
                    type="checkbox"
                    checked={remember}
                    onChange={(e) => setRemember(e.target.checked)}
                  />
                  <span>Remember this device</span>
                </label>
                <button className="sovereign-primary-button" disabled={loading}>
                  {loading ? (
                    <span className="sovereign-spinner" />
                  ) : (
                    <>
                      Authenticate <ArrowRight size={18} />
                    </>
                  )}
                </button>
                <button
                  type="button"
                  className="sovereign-back-button"
                  onClick={() => {
                    setPassword("")
                    resetMode("login")
                  }}
                >
                  ← Back to Sign In
                </button>
              </form>
            )}

            {mode === "signup" && (
              <form
                onSubmit={submitSignup}
                className="sovereign-auth-form compact-form"
              >
                <label>
                  <span>Full Name</span>
                  <div className="sovereign-input">
                    <input
                      name="name"
                      placeholder="Your full name"
                      autoComplete="name"
                    />
                  </div>
                </label>
                <label>
                  <span>Organization</span>
                  <div className="sovereign-input">
                    <input
                      name="organization"
                      placeholder="Organization name"
                      autoComplete="organization"
                    />
                  </div>
                </label>
                <label>
                  <span>Work Email</span>
                  <div className="sovereign-input">
                    <Mail />
                    <input
                      name="email"
                      placeholder="you@example.com"
                      type="email"
                    />
                  </div>
                </label>
                <label>
                  <span>Password</span>
                  <div className="sovereign-input">
                    <LockKeyhole />
                    <input
                      name="password"
                      placeholder="Create a password"
                      type="password"
                    />
                  </div>
                </label>
                <label>
                  <span>Confirm Password</span>
                  <div className="sovereign-input">
                    <LockKeyhole />
                    <input
                      name="confirmPassword"
                      placeholder="Confirm your password"
                      type="password"
                    />
                  </div>
                </label>
                {error && <div className="sovereign-error">{error}</div>}
                <button className="sovereign-primary-button" disabled={loading}>
                  {loading ? (
                    <span className="sovereign-spinner" />
                  ) : (
                    <>
                      Create Account <ArrowRight size={18} />
                    </>
                  )}
                </button>
                <p className="sovereign-signup">
                  Already have an account?{" "}
                  <button type="button" onClick={() => resetMode("login")}>
                    Sign in
                  </button>
                </p>
              </form>
            )}

            {mode === "forgot" &&
              (sent ? (
                <div className="sovereign-success">
                  <ShieldCheck size={28} />
                  <h3>Instructions sent</h3>
                  <p>
                    Password reset instructions have been sent to your work
                    email.
                  </p>
                  <button
                    className="sovereign-primary-button"
                    onClick={() => resetMode("login")}
                  >
                    Back to Sign In
                  </button>
                </div>
              ) : (
                <form onSubmit={submitForgot} className="sovereign-auth-form">
                  <label>
                    <span>Work Email</span>
                    <div className="sovereign-input">
                      <Mail />
                      <input
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="you@example.com"
                        type="email"
                        autoFocus
                      />
                    </div>
                  </label>
                  {error && <div className="sovereign-error">{error}</div>}
                  <button className="sovereign-primary-button">
                    Send Reset Link <ArrowRight size={18} />
                  </button>
                  <button
                    type="button"
                    className="sovereign-back-button"
                    onClick={() => resetMode("login")}
                  >
                    ← Back to Sign In
                  </button>
                </form>
              ))}

            {mode === "access" &&
              (sent ? (
                <div className="sovereign-success">
                  <ShieldCheck size={28} />
                  <h3>Request submitted</h3>
                  <p>
                    Your workspace access request has been recorded for review.
                  </p>
                  <button
                    className="sovereign-primary-button"
                    onClick={() => resetMode("login")}
                  >
                    Back to Sign In
                  </button>
                </div>
              ) : (
                <form onSubmit={submitAccess} className="sovereign-auth-form">
                  <label>
                    <span>Full Name</span>
                    <div className="sovereign-input">
                      <input required placeholder="Your name" />
                    </div>
                  </label>
                  <label>
                    <span>Work Email</span>
                    <div className="sovereign-input">
                      <Mail />
                      <input
                        required
                        type="email"
                        placeholder="you@example.com"
                      />
                    </div>
                  </label>
                  <label>
                    <span>Organization</span>
                    <div className="sovereign-input">
                      <input required placeholder="Organization name" />
                    </div>
                  </label>
                  <label>
                    <span>Role</span>
                    <div className="sovereign-input">
                      <input required placeholder="e.g. Operations Engineer" />
                    </div>
                  </label>
                  {error && <div className="sovereign-error">{error}</div>}
                  <button className="sovereign-primary-button">
                    Submit Request <ArrowRight size={18} />
                  </button>
                  <button
                    type="button"
                    className="sovereign-back-button"
                    onClick={() => resetMode("login")}
                  >
                    ← Back to Sign In
                  </button>
                </form>
              ))}

            <div className="sovereign-security-note">
              <ShieldCheck size={16} />
              <div>
                <strong>Secure On-Premise Access</strong>
                <span>
                  Your session stays within your organization's secure
                  environment.
                </span>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  )
}

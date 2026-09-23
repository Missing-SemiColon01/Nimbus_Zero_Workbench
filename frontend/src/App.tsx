import { useState, useEffect } from "react"
import { BrowserRouter, Navigate, useLocation } from "react-router-dom"
import { Sidebar } from "./components/layout/Sidebar"
import { Header } from "./components/layout/Header"
import { ToastProvider } from "./components/ui/Toast"
import { Chat } from "./pages/Chat"
import { Login } from "./pages/Login"
import { KnowledgeBase } from "./pages/KnowledgeBase"
import { Documents } from "./pages/Documents"
import { Agents } from "./pages/Agents"
import { Workflows } from "./pages/Workflows"
import { SystemStatus } from "./pages/SystemStatus"
import { Security } from "./pages/Security"
import { Settings } from "./pages/Settings"
import { useSessions } from "./hooks/useSessions"
import { useTheme } from "./hooks/useTheme"
import { authService } from "./services/authService"

function AppInner() {
  const [authenticated, setAuthenticated] = useState(() =>
    authService.isAuthenticated(),
  )
  const [userEmail, setUserEmail] = useState(() => {
    const saved = authService.getSavedUser()
    return saved?.email || localStorage.getItem("sovereign-user-email") || ""
  })
  const [userName, setUserName] = useState(() => {
    const saved = authService.getSavedUser()
    return saved?.name || localStorage.getItem("sovereign-user-name") || ""
  })
  const [userOrg, setUserOrg] = useState(() => {
    const saved = authService.getSavedUser()
    return (
      saved?.organization ||
      localStorage.getItem("sovereign-user-organization") ||
      ""
    )
  })

  const {
    sessions,
    activeSession,
    activeId,
    setActiveId,
    createSession,
    renameSession,
    deleteSession,
    pinSession,
    addMessage,
    addMessages,
    updateMessage,
    clearAllHistory,
  } = useSessions()
  const { theme, setTheme, toggleTheme } = useTheme()
  const location = useLocation()
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false)

  // Validate token on mount
  useEffect(() => {
    const token = authService.getToken()
    if (token && token !== "demo-sovereign-token") {
      authService.verifyToken(token).then((res) => {
        if (!res.valid) {
          authService.removeToken()
          setAuthenticated(false)
        } else if (res.user) {
          setUserEmail(res.user.email)
          setUserName(res.user.name)
          if (res.user.organization) setUserOrg(res.user.organization)
        }
      })
    }
  }, [])

  // Mobile detection
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768)
  const [isTablet, setIsTablet] = useState(
    window.innerWidth >= 768 && window.innerWidth < 1200,
  )

  useEffect(() => {
    const handler = () => {
      const w = window.innerWidth
      setIsMobile(w < 768)
      setIsTablet(w >= 768 && w < 1200)
    }
    window.addEventListener("resize", handler)
    return () => window.removeEventListener("resize", handler)
  }, [])

  if (!authenticated) {
    if (location.pathname !== "/login") {
      return <Navigate to="/login" replace />
    }
    return (
      <Login
        onLogin={(email, name, org) => {
          setUserEmail(email)
          if (name) setUserName(name)
          if (org) setUserOrg(org)
          setAuthenticated(true)
        }}
      />
    )
  }

  if (location.pathname === "/login") {
    return <Navigate to="/" replace />
  }

  const isChatPage = location.pathname === "/"
  const sessionTitle = activeSession?.title || "Nimbus Zero Workbench"

  function handleSidebarToggle() {
    if (isMobile) {
      setMobileSidebarOpen(!mobileSidebarOpen)
    } else {
      setSidebarCollapsed(!sidebarCollapsed)
    }
  }

  const renderPage = () => {
    switch (location.pathname) {
      case "/knowledge":
        return <KnowledgeBase />
      case "/documents":
        return <Documents />
      case "/agents":
        return <Agents />
      case "/workflows":
        return <Workflows />
      case "/system":
        return <SystemStatus />
      case "/security":
        return <Security />
      case "/settings":
        return (
          <Settings
            theme={theme}
            onSetTheme={setTheme}
            onClearHistory={clearAllHistory}
          />
        )
      default:
        return (
          <Chat
            session={activeSession}
            onAddMessage={addMessage}
            onAddMessages={addMessages}
            onUpdateMessage={updateMessage}
          />
        )
    }
  }

  return (
    <div
      className="flex h-screen w-screen overflow-hidden"
      style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}
    >
      {/* Mobile sidebar overlay */}
      {isMobile && mobileSidebarOpen && (
        <>
          <div
            className="fixed inset-0 bg-black/50 z-40 backdrop-blur-sm"
            onClick={() => setMobileSidebarOpen(false)}
          />
          <div className="fixed left-0 top-0 bottom-0 z-50 animate-slide-in">
            <Sidebar
              sessions={sessions}
              activeId={activeId}
              onSelectSession={(id) => {
                setActiveId(id)
                setMobileSidebarOpen(false)
              }}
              onCreateSession={createSession}
              onRenameSession={renameSession}
              onDeleteSession={deleteSession}
              onPinSession={pinSession}
              collapsed={false}
              onToggleCollapse={() => setMobileSidebarOpen(false)}
            />
          </div>
        </>
      )}

      {/* Desktop/Tablet sidebar */}
      {!isMobile && (
        <Sidebar
          sessions={sessions}
          activeId={activeId}
          onSelectSession={setActiveId}
          onCreateSession={createSession}
          onRenameSession={renameSession}
          onDeleteSession={deleteSession}
          onPinSession={pinSession}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        />
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Header
          sessionTitle={sessionTitle}
          theme={theme}
          onToggleTheme={toggleTheme}
          onToggleSidebar={handleSidebarToggle}
          isMobile={isMobile}
          onLogout={async () => {
            await authService.logout()
            setAuthenticated(false)
            setUserEmail("")
            setUserName("")
            setUserOrg("")
          }}
          userEmail={userEmail}
          userName={userName}
          userOrg={userOrg}
        />

        <div className="flex flex-1 min-h-0 overflow-hidden">
          {renderPage()}
        </div>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AppInner />
      </ToastProvider>
    </BrowserRouter>
  )
}

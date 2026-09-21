import { useEffect } from "react"
import { useLocalStorage } from "./useLocalStorage"
import type { Theme } from "../types"

export function useTheme() {
  const [theme, setTheme] = useLocalStorage<Theme>("sovereign-theme", "dark")

  useEffect(() => {
    document.documentElement.classList.remove("dark", "light")
    document.documentElement.classList.add(theme)
    document.body.classList.remove("dark", "light")
    document.body.classList.add(theme)
  }, [theme])

  const toggleTheme = () => setTheme((t) => (t === "dark" ? "light" : "dark"))

  return { theme, setTheme, toggleTheme }
}

import { useState, useCallback, useRef, useEffect } from "react"

export function useLocalStorage<T>(
  key: string,
  initialValue: T,
): [T, (value: T | ((prev: T) => T)) => void] {
  const [storedValue, setStoredValue] = useState<T>(() => {
    try {
      const item = window.localStorage.getItem(key)
      if (item) {
        const parsed = JSON.parse(item)
        if (Array.isArray(initialValue) && !Array.isArray(parsed)) {
          return initialValue
        }
        return parsed
      }
      return initialValue
    } catch {
      return initialValue
    }
  })

  const storedValueRef = useRef<T>(storedValue)
  useEffect(() => {
    storedValueRef.current = storedValue
  }, [storedValue])

  const setValue = useCallback(
    (value: T | ((prev: T) => T)) => {
      try {
        setStoredValue((prev) => {
          const valueToStore = value instanceof Function ? value(prev) : value
          storedValueRef.current = valueToStore
          try {
            window.localStorage.setItem(key, JSON.stringify(valueToStore))
          } catch (storageError) {
            console.error(`Error writing localStorage key "${key}":`, storageError)
          }
          return valueToStore
        })
      } catch (error) {
        console.error(`Error in setValue for key "${key}":`, error)
      }
    },
    [key],
  )

  return [storedValue, setValue]
}

import { useState, useCallback } from 'react'

export type ToastType = 'success' | 'error' | 'warn' | 'info'

interface Toast {
  id: number
  message: string
  type: ToastType
}

let _nextId = 0

// Defined outside the hook so React never remounts the container on re-renders
export function ToastContainer({ toasts }: { toasts: Toast[] }) {
  return (
    <div className="toast-container" data-testid="toast-container">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.type}`} data-testid={`toast-${t.type}`}>
          {t.message}
        </div>
      ))}
    </div>
  )
}

export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([])

  const show = useCallback((message: string, type: ToastType = 'success') => {
    const id = _nextId++
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 3000)
  }, [])

  // Return the bound component so callers can render <ToastDisplay />
  const ToastDisplay = () => <ToastContainer toasts={toasts} />

  return { show, ToastContainer: ToastDisplay }
}

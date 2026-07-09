import { useState, useEffect, useCallback, createContext, useContext, type ReactNode } from 'react'
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react'

type ToastType = 'success' | 'error' | 'warning' | 'info'

interface Toast {
  id: number
  type: ToastType
  message: string
  exiting?: boolean
}

interface ToastContextType {
  toast: (type: ToastType, message: string) => void
}

const ToastContext = createContext<ToastContextType | null>(null)

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}

const ICONS: Record<ToastType, typeof CheckCircle> = {
  success: CheckCircle,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
}

const COLORS: Record<ToastType, string> = {
  success: 'border-l-green-500 bg-green-500/5',
  error: 'border-l-red-500 bg-red-500/5',
  warning: 'border-l-yellow-500 bg-yellow-500/5',
  info: 'border-l-blue-500 bg-blue-500/5',
}

const ICON_COLORS: Record<ToastType, string> = {
  success: 'text-green-400',
  error: 'text-red-400',
  warning: 'text-yellow-400',
  info: 'text-blue-400',
}

let nextId = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const addToast = useCallback((type: ToastType, message: string) => {
    const id = nextId++
    setToasts((prev) => [...prev, { id, type, message }])

    setTimeout(() => {
      setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, exiting: true } : t)))
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id))
      }, 300)
    }, 3500)
  }, [])

  return (
    <ToastContext.Provider value={{ toast: addToast }}>
      {children}
      {/* Toast container */}
      <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none max-w-sm w-full">
        {toasts.map((t) => {
          const Icon = ICONS[t.type]
          return (
            <div
              key={t.id}
              className={`pointer-events-auto flex items-start gap-3 p-4 rounded-lg border-l-4 shadow-xl backdrop-blur-sm bg-opacity-90 transition-all duration-300 ${
                t.exiting ? 'opacity-0 translate-x-4' : 'opacity-100 translate-x-0'
              } ${COLORS[t.type]}`}
            >
              <Icon className={`w-5 h-5 shrink-0 mt-0.5 ${ICON_COLORS[t.type]}`} />
              <p className="text-sm text-gray-200 flex-1">{t.message}</p>
              <button
                onClick={() => {
                  setToasts((prev) => prev.map((to) => (to.id === t.id ? { ...to, exiting: true } : to)))
                  setTimeout(() => setToasts((prev) => prev.filter((to) => to.id !== t.id)), 300)
                }}
                className="shrink-0 p-0.5 text-gray-500 hover:text-gray-300 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

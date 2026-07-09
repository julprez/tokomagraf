import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import { Activity, Database, Server, CheckCircle, XCircle } from 'lucide-react'

interface ServiceStatus {
  name: string
  icon: typeof Activity
  endpoint: string
  status: 'ok' | 'error' | 'checking'
  detail?: string
}

export default function Healthcheck() {
  const { data: apiHealth, isLoading: apiLoading } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.get('/health').then(r => r.data),
    refetchInterval: 10000,
  })

  const services: ServiceStatus[] = [
    {
      name: 'API',
      icon: Server,
      endpoint: '/api/health',
      status: apiLoading ? 'checking' : apiHealth?.status === 'ok' ? 'ok' : 'error',
      detail: apiHealth?.version || '—',
    },
    {
      name: 'Frontend',
      icon: Activity,
      endpoint: '/',
      status: 'ok',
      detail: 'React + Vite',
    },
  ]

  const allOk = services.every(s => s.status === 'ok')

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
        <Activity className="w-6 h-6 text-btc-orange" />
        Estado del Sistema
      </h1>

      <div className={`card text-center ${allOk ? 'border-l-4 border-l-green-500' : 'border-l-4 border-l-red-500'}`}>
        <p className="text-4xl font-bold mb-2">
          {allOk ? '✅' : '⚠️'}
        </p>
        <p className={`text-lg font-semibold ${allOk ? 'text-green-400' : 'text-yellow-400'}`}>
          {allOk ? 'Todos los servicios operativos' : 'Algunos servicios tienen problemas'}
        </p>
      </div>

      <div className="space-y-3">
        {services.map((svc) => (
          <div key={svc.name} className="card flex items-center justify-between py-4 px-5">
            <div className="flex items-center gap-4">
              <svc.icon className="w-5 h-5 text-gray-400" />
              <div>
                <p className="font-semibold text-gray-200">{svc.name}</p>
                <p className="text-xs text-gray-500 font-mono">{svc.endpoint}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {svc.status === 'checking' ? (
                <span className="text-xs text-gray-500 animate-pulse">Verificando…</span>
              ) : svc.status === 'ok' ? (
                <>
                  <CheckCircle className="w-5 h-5 text-green-400" />
                  <span className="text-xs text-green-400 font-medium">Online</span>
                </>
              ) : (
                <>
                  <XCircle className="w-5 h-5 text-red-400" />
                  <span className="text-xs text-red-400 font-medium">Error</span>
                </>
              )}
              {svc.detail && <span className="text-xs text-gray-600 ml-1">{svc.detail}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

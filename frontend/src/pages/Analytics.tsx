import { useQuery } from '@tanstack/react-query'
import { portfolio, prices } from '../api/client'
import { BarChart3, TrendingUp, TrendingDown } from 'lucide-react'
import { EmptyState } from '../components/EmptyState'
import { SkeletonCard } from '../components/Skeleton'

export default function Analytics() {
  const { data: analysis, isLoading } = useQuery({
    queryKey: ['analysis'],
    queryFn: portfolio.analysis,
    refetchInterval: 300000,
  })

  const { data: chartData } = useQuery({
    queryKey: ['btcChart', 90],
    queryFn: () => prices.chart(90),
  })

  if (isLoading) {
    return (
      <div className="space-y-6">
        <SkeletonCard lines={4} />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1,2,3].map(i => <SkeletonCard key={i} lines={3} />)}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-100">📊 Análisis Técnico</h1>

      {!analysis ? (
        <EmptyState icon={BarChart3} title="Sin datos" description="No hay suficientes datos históricos para el análisis." />
      ) : (
        <>
          {/* Señal general */}
          <div className="card text-center">
            <p className="text-sm text-gray-500 uppercase tracking-wider mb-2">Señal General</p>
            <p className={`text-3xl sm:text-4xl font-bold capitalize ${
              analysis.overall_signal === 'compra' ? 'text-green-400' : 
              analysis.overall_signal === 'venta' ? 'text-red-400' : 'text-yellow-400'
            }`}>
              {analysis.overall_signal}
            </p>
            <p className="text-gray-500 mt-1">Tendencia: <span className="text-gray-200 capitalize">{analysis.trend}</span></p>
            <p className="text-gray-500">Fortaleza: <span className="text-gray-200 capitalize">{analysis.signal_strength}</span></p>
          </div>

          {/* Indicadores grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* RSI */}
            <div className="card">
              <p className="text-sm text-gray-500 mb-2">RSI (14)</p>
              <p className={`text-3xl sm:text-4xl font-bold ${
                analysis.rsi > 70 ? 'text-red-400' : analysis.rsi < 30 ? 'text-green-400' : 'text-yellow-400'
              }`}>
                {analysis.rsi?.toFixed(1) || '—'}
              </p>
              <div className="mt-2 h-2 bg-surface-light rounded-full overflow-hidden">
                <div className={`h-full rounded-full transition-all ${
                  analysis.rsi > 70 ? 'bg-red-400' : analysis.rsi < 30 ? 'bg-green-400' : 'bg-yellow-400'
                }`} style={{ width: `${Math.min(100, (analysis.rsi || 50))}%` }} />
              </div>
            </div>

            {/* MACD */}
            <div className="card">
              <p className="text-sm text-gray-500 mb-2">MACD</p>
              <p className="text-2xl font-bold text-gray-100">{analysis.macd?.line?.toFixed(2) || '—'}</p>
              <p className="text-sm text-gray-500">Signal: {analysis.macd?.signal?.toFixed(2) || '—'}</p>
              <p className={`text-sm font-semibold ${
                analysis.macd?.cross === 'alcista' ? 'text-green-400' : 
                analysis.macd?.cross === 'bajista' ? 'text-red-400' : 'text-gray-500'
              }`}>
                Cruce: {analysis.macd?.cross || '—'}
              </p>
            </div>

            {/* SMA */}
            <div className="card">
              <p className="text-sm text-gray-500 mb-2">Medias Móviles</p>
              <p className="text-sm text-gray-400">SMA 50: <span className="text-gray-200 font-mono">${analysis.sma_50?.toLocaleString('en-US', { maximumFractionDigits: 0 }) || '—'}</span></p>
              <p className="text-sm text-gray-400">SMA 200: <span className="text-gray-200 font-mono">${analysis.sma_200?.toLocaleString('en-US', { maximumFractionDigits: 0 }) || '—'}</span></p>
              {analysis.sma_50 && analysis.sma_200 && (
                <p className={`text-sm font-semibold mt-1 ${analysis.sma_50 > analysis.sma_200 ? 'text-green-400' : 'text-red-400'}`}>
                  {analysis.sma_50 > analysis.sma_200 ? '✅ Golden Cross' : '❌ Death Cross'}
                </p>
              )}
            </div>
          </div>

          {/* Señales detalladas */}
          {analysis.signals && analysis.signals.length > 0 && (
            <div className="card">
              <h2 className="text-lg font-semibold text-gray-200 mb-4">📡 Señales</h2>
              <div className="space-y-3">
                {analysis.signals.map((sig: any, i: number) => (
                  <div key={i} className="flex items-center gap-3 py-2 border-b border-surface-light last:border-0">
                    <span className={sig.signal === 'compra' ? 'text-green-400' : 'text-red-400'}>
                      {sig.signal === 'compra' ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
                    </span>
                    <div>
                      <p className="text-sm font-medium text-gray-200">{sig.name}: {sig.signal}</p>
                      <p className="text-xs text-gray-500">{sig.detail}</p>
                    </div>
                    <span className={`ml-auto text-xs font-semibold px-2 py-1 rounded ${
                      sig.weight >= 3 ? 'bg-yellow-500/10 text-yellow-400' : 'bg-gray-500/10 text-gray-400'
                    }`}>
                      peso {sig.weight}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Soporte y Resistencia */}
          {analysis.support_resistance && (
            <div className="grid grid-cols-2 gap-4">
              <div className="card text-center">
                <p className="text-sm text-gray-500 mb-2">🛡️ Soporte</p>
                <p className="text-3xl font-bold text-green-400">
                  ${analysis.support_resistance.support?.toLocaleString('en-US', { maximumFractionDigits: 0 }) || '—'}
                </p>
              </div>
              <div className="card text-center">
                <p className="text-sm text-gray-500 mb-2">🧱 Resistencia</p>
                <p className="text-3xl font-bold text-red-400">
                  ${analysis.support_resistance.resistance?.toLocaleString('en-US', { maximumFractionDigits: 0 }) || '—'}
                </p>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

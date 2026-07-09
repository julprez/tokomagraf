import { useQuery } from '@tanstack/react-query'
import { predictions as predictionsApi } from '../api/client'
import {
  TrendingUp, TrendingDown, Minus, AlertTriangle,
  BarChart3, Target, Activity, Zap, Shield,
  BrainCircuit, DollarSign, Bitcoin,
} from 'lucide-react'
import { EmptyState } from '../components/EmptyState'
import { SkeletonCard } from '../components/Skeleton'

const signalConfig: Record<string, { label: string; color: string; bg: string; icon: any }> = {
  compra_fuerte: { label: 'Compra Fuerte', color: 'text-green-400', bg: 'bg-green-500/10', icon: TrendingUp },
  compra:         { label: 'Compra',        color: 'text-green-300', bg: 'bg-green-500/5',  icon: TrendingUp },
  neutral:        { label: 'Neutral',       color: 'text-yellow-400', bg: 'bg-yellow-500/10', icon: Minus },
  venta:          { label: 'Venta',         color: 'text-red-300',   bg: 'bg-red-500/5',     icon: TrendingDown },
  venta_fuerte:   { label: 'Venta Fuerte',  color: 'text-red-400',   bg: 'bg-red-500/10',    icon: TrendingDown },
}

const directionConfig: Record<string, { color: string; icon: any }> = {
  alcista:  { color: 'text-green-400', icon: TrendingUp },
  bajista:  { color: 'text-red-400',   icon: TrendingDown },
  neutral:  { color: 'text-gray-400',  icon: Minus },
}

export default function Predictions() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['prediction'],
    queryFn: predictionsApi.get,
    refetchInterval: 60000,
  })

  if (isLoading) {
    return (
      <div className="space-y-6">
        <SkeletonCard lines={4} />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1,2,3,4,5,6,7,8].map(i => <SkeletonCard key={i} lines={2} />)}
        </div>
      </div>
    )
  }

  if (error || data?.error) {
    return (        <EmptyState icon={AlertTriangle} title="Sin datos suficientes" description="No hay suficientes datos históricos para generar una predicción." />
    )
  }

  const signal = signalConfig[data.signal] || signalConfig.neutral
  const SignalIcon = signal.icon
  const score = data.score

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
          <BrainCircuit className="w-6 h-6 text-btc-orange" />
          Predicción de Mercado
        </h1>
        <span className="text-xs sm:text-sm text-gray-500">
          🕐 {new Date(data.updated_at).toLocaleString()}
        </span>
      </div>

      {/* Score principal */}
      <div className="card text-center relative overflow-hidden">
        {/* Anillo de score */}
        <div className="relative w-32 h-32 sm:w-40 sm:h-40 mx-auto mb-4">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
            {/* Fondo del anillo */}
            <circle
              cx="50" cy="50" r="42"
              fill="none"
              stroke="#1e293b"
              strokeWidth="8"
            />
            {/* Score */}
            <circle
              cx="50" cy="50" r="42"
              fill="none"
              stroke="currentColor"
              strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={`${score * 2.64} ${264 - score * 2.64}`}
              className={signal.color}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className={`text-4xl sm:text-5xl font-bold font-mono ${signal.color}`}>
              {score.toFixed(0)}%
            </span>
          </div>
        </div>

        <div className={`inline-flex items-center gap-2 px-3 sm:px-4 py-2 rounded-full ${signal.bg} ${signal.color} font-semibold text-base sm:text-lg mb-2`}>
          <SignalIcon className="w-5 h-5" />
          {signal.label}
        </div>

        <p className="text-gray-500 text-sm mt-2">
          Precio BTC: <span className="text-gray-200 font-mono font-semibold">${data.current_price?.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
          {data.change_24h != null && (
            <span className={`ml-2 ${data.change_24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {data.change_24h >= 0 ? '↑' : '↓'} {Math.abs(data.change_24h).toFixed(2)}%
            </span>
          )}
        </p>
      </div>

      {/* Indicadores clave */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <IndicatorCard
          icon={Activity}
          label="RSI (14)"
          value={data.details?.rsi != null ? data.details.rsi.toFixed(1) : '—'}
          status={
            data.details?.rsi > 70 ? 'high' :
            data.details?.rsi < 30 ? 'low' : 'normal'
          }
        />
        <IndicatorCard
          icon={Zap}
          label="MACD"
          value={data.details?.macd?.line?.toFixed(2) || '—'}
          sub={`Signal: ${data.details?.macd?.signal?.toFixed(2) || '—'}`}
          status={
            data.details?.macd?.histogram > 0 ? 'low' :
            data.details?.macd?.histogram < 0 ? 'high' : 'normal'
          }
        />
        <IndicatorCard
          icon={BarChart3}
          label="SMA 50"
          value={data.details?.sma_50 ? `$${(data.details.sma_50).toLocaleString('en-US', { maximumFractionDigits: 0 })}` : '—'}
          sub={`SMA 200: ${data.details?.sma_200 ? `$${data.details.sma_200.toLocaleString('en-US', { maximumFractionDigits: 0 })}` : '—'}`}
          status="normal"
        />
        <IndicatorCard
          icon={Target}
          label="Soporte / Resistencia"
          value={data.details?.support_resistance?.support ? `$${data.details.support_resistance.support.toLocaleString('en-US', { maximumFractionDigits: 0 })}` : '—'}
          sub={`Res: ${data.details?.support_resistance?.resistance ? `$${data.details.support_resistance.resistance.toLocaleString('en-US', { maximumFractionDigits: 0 })}` : '—'}`}
          status="normal"
        />
        <IndicatorCard
          icon={AlertTriangle}
          label="Fear & Greed"
          value={data.details?.fear_greed?.value != null ? `${data.details.fear_greed.value}` : '—'}
          sub={data.details?.fear_greed?.classification || ''}
          status={
            data.details?.fear_greed?.value > 75 ? 'high' :
            data.details?.fear_greed?.value < 25 ? 'low' : 'normal'
          }
        />
        <IndicatorCard
          icon={Bitcoin}
          label="Dominancia BTC"
          value={data.details?.global_metrics?.btc_dominance != null ? `${data.details.global_metrics.btc_dominance.toFixed(1)}%` : '—'}
          sub={`Cap: ${data.details?.global_metrics?.total_market_cap ? `$${(data.details.global_metrics.total_market_cap / 1e12).toFixed(2)}T` : '—'}`}
          status={
            data.details?.global_metrics?.btc_dominance > 55 ? 'high' :
            data.details?.global_metrics?.btc_dominance < 40 ? 'low' : 'normal'
          }
        />
        <IndicatorCard
          icon={DollarSign}
          label="Volumen 24h"
          value={data.details?.global_metrics?.total_volume ? `$${(data.details.global_metrics.total_volume / 1e9).toFixed(2)}B` : '—'}
          status="normal"
        />
        <IndicatorCard
          icon={Shield}
          label="Upside / Downside"
          value={data.details?.support_resistance?.upside_pct != null ? `+${data.details.support_resistance.upside_pct}%` : '—'}
          sub={data.details?.support_resistance?.downside_pct != null ? `-${Math.abs(data.details.support_resistance.downside_pct)}%` : ''}
          status={
            data.details?.support_resistance?.upside_pct > 10 ? 'low' :
            data.details?.support_resistance?.downside_pct > 10 ? 'high' : 'normal'
          }
        />
      </div>

      {/* Motivos detallados */}
      {data.reasons && data.reasons.length > 0 && (
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-200 mb-4 flex items-center gap-2">
            <BrainCircuit className="w-5 h-5 text-btc-orange" />
            Motivos del Análisis
          </h2>
          <div className="space-y-2">
            {data.reasons.map((reason: any, i: number) => {
              const dirCfg = directionConfig[reason.direction] || directionConfig.neutral
              const DirIcon = dirCfg.icon
              return (
                <div
                  key={i}
                  className="flex items-start gap-3 p-3 rounded-lg bg-surface-light/50 hover:bg-surface-light transition-colors"
                >
                  <div className={`mt-0.5 ${dirCfg.color}`}>
                    <DirIcon className="w-5 h-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-gray-200">{reason.indicator}</p>
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${dirCfg.color} bg-current/10`}>
                        {reason.direction}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">{reason.detail}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <div className={`text-sm font-mono font-bold ${
                      reason.impact > 0.3 ? 'text-green-400' :
                      reason.impact < -0.3 ? 'text-red-400' :
                      'text-gray-500'
                    }`}>
                      {reason.impact > 0 ? '+' : ''}{reason.impact.toFixed(2)}
                    </div>
                    <div className="text-xs text-gray-600">peso {reason.weight}</div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Disclaimer */}
      <div className="bg-yellow-500/5 border border-yellow-500/10 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-yellow-400 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-yellow-400">Disclaimer</p>
            <p className="text-xs text-gray-500 mt-1">
              Esta predicción es solo una referencia basada en análisis técnico y datos de mercado.
              No es asesoramiento financiero. tokomagraf no realiza compras ni ventas automáticas.
              Usá esta información como una herramienta más en tu proceso de decisión.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

function IndicatorCard({
  icon: Icon, label, value, sub, status,
}: {
  icon: any; label: string; value: string; sub?: string; status: 'high' | 'low' | 'normal'
}) {
  const statusColor = status === 'high' ? 'text-red-400' : status === 'low' ? 'text-green-400' : 'text-gray-400'
  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`w-4 h-4 ${status === 'normal' ? 'text-btc-orange' : statusColor}`} />
        <p className="text-xs text-gray-500 font-medium">{label}</p>
      </div>
      <p className={`text-lg font-bold font-mono ${statusColor}`}>{value}</p>
      {sub && <p className="text-xs text-gray-600 mt-0.5">{sub}</p>}
    </div>
  )
}

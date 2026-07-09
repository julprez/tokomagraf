import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'
import {
  TrendingUp, TrendingDown, Bitcoin,
  BarChart3, Settings, Save, RefreshCw, BrainCircuit,
  Activity, Target,
} from 'lucide-react'
import { dca as dcaApi } from '../api/client'
import { EmptyState } from '../components/EmptyState'
import { SkeletonChart } from '../components/Skeleton'

const COLORS = {
  real: '#f7931a',
  dca: '#3b82f6',
  green: '#22c55e',
  red: '#ef4444',
  purple: '#a855f7',
  cyan: '#06b6d4',
}

export default function DCA() {
  const queryClient = useQueryClient()
  const [showConfig, setShowConfig] = useState(false)
  const [frequency, setFrequency] = useState('weekly')
  const [day, setDay] = useState(1)

  const { data, isLoading, error } = useQuery({
    queryKey: ['dcaComparison'],
    queryFn: dcaApi.comparison,
    refetchInterval: 300000,
    retry: 2,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10000),
    staleTime: 120000,
  })

  const { data: config } = useQuery({
    queryKey: ['dcaConfig'],
    queryFn: dcaApi.config,
  })

  const configMutation = useMutation({
    mutationFn: (data: { frequency: string; day: number }) => dcaApi.updateConfig(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dcaComparison'] })
      queryClient.invalidateQueries({ queryKey: ['dcaConfig'] })
      setShowConfig(false)
    },
  })

  // Inicializar formulario con valores actuales
  useEffect(() => {
    if (config) {
      setFrequency(config.frequency || 'weekly')
      setDay(config.day || 1)
    }
  }, [config])

  if (isLoading) {
    return (
      <div className="space-y-6">
        <SkeletonChart height={220} />
        <SkeletonChart height={160} />
        <SkeletonChart height={200} />
      </div>
    )
  }

  if (error) {
    const errorMsg = error instanceof Error ? error.message : ''
    return (        <EmptyState icon={BarChart3} title="Error al cargar DCA" description={errorMsg ? errorMsg : 'Intentalo de nuevo.'} action={<button onClick={() => queryClient.invalidateQueries({ queryKey: ['dcaComparison'] })} className="btn-secondary py-2 px-4">Reintentar</button>} />
    )
  }

  if (!data) {
    return (        <EmptyState icon={BarChart3} title="Sin datos para comparar" description="Registrá operaciones para ver la comparativa con DCA." />
    )
  }

  const r = data.real
  const d = data.dca
  const cmp = data.comparacion
  const isRealWinning = cmp.ganador === 'real'

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
          <Activity className="w-6 h-6 text-btc-orange" />
          Comparativa DCA
        </h1>
        <button onClick={() => { setShowConfig(!showConfig); if (config) { setFrequency(config.frequency); setDay(config.day) } }} className="btn-secondary flex items-center gap-2 py-2 px-4 text-sm w-full sm:w-auto">
          <Settings className="w-4 h-4" />
          Configurar DCA
        </button>
      </div>

      {/* Config Panel */}
      {showConfig && (
        <div className="card border border-btc-orange/20">
          <h2 className="text-lg font-semibold text-gray-200 mb-4 flex items-center gap-2">
            <Settings className="w-5 h-5 text-btc-orange" />
            Configurar Estrategia DCA
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div>
              <label className="label">Frecuencia</label>
              <select
                className="input-field"
                value={frequency}
                onChange={(e) => setFrequency(e.target.value)}
              >
                <option value="weekly">Semanal</option>
                <option value="monthly">Mensual</option>
              </select>
            </div>
            <div>
              <label className="label">
                {frequency === 'weekly' ? 'Día de la semana' : 'Día del mes'}
              </label>
              <select
                className="input-field"
                value={day}
                onChange={(e) => setDay(Number(e.target.value))}
              >
                {frequency === 'weekly' ? (
                  <>
                    <option value={0}>Lunes</option>
                    <option value={1}>Martes</option>
                    <option value={2}>Miércoles</option>
                    <option value={3}>Jueves</option>
                    <option value={4}>Viernes</option>
                    <option value={5}>Sábado</option>
                    <option value={6}>Domingo</option>
                  </>
                ) : (
                  Array.from({ length: 28 }, (_, i) => (
                    <option key={i + 1} value={i + 1}>{i + 1}</option>
                  ))
                )}
              </select>
            </div>
            <div className="flex items-end">
              <button
                onClick={() => configMutation.mutate({ frequency, day })}
                disabled={configMutation.isPending}
                className="btn-primary w-full flex items-center justify-center gap-2 py-3"
              >
                <Save className="w-4 h-4" />
                {configMutation.isPending ? 'Guardando…' : 'Guardar y recalcular'}
              </button>
            </div>
          </div>
          <p className="text-xs text-gray-600">
            La DCA invierte el mismo capital total (${r.capital_invertido?.toLocaleString()}) 
            en montos iguales cada {frequency === 'weekly' ? 'semana' : 'mes'}.
          </p>
        </div>
      )}

      {/* Resumen comparativo */}
      <div className={`card relative overflow-hidden ${isRealWinning ? 'border-l-4 border-l-green-500' : 'border-l-4 border-l-blue-500'}`}>
        <div className="flex items-center gap-3 mb-4">
          {isRealWinning ? (
            <TrendingUp className="w-6 h-6 text-green-400" />
          ) : (
            <Bitcoin className="w-6 h-6 text-blue-400" />
          )}
          <div>
            <p className="text-lg font-bold text-gray-100">
              {isRealWinning ? '🎯 Tu estrategia lidera' : '📊 El DCA lidera'}
            </p>
            <p className="text-sm text-gray-500">{cmp.resumen}</p>
          </div>
        </div>
      </div>

      {/* Tabla comparativa */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-200 mb-4">📊 Comparativa</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-light">
                <th className="text-left py-3 px-2 text-gray-500 font-medium">Indicador</th>
                <th className="text-right py-3 px-2 text-btc-orange font-medium">Tu Cartera</th>
                <th className="text-right py-3 px-2 text-blue-400 font-medium">DCA</th>
                <th className="text-right py-3 px-2 text-gray-500 font-medium">Diferencia</th>
              </tr>
            </thead>
            <tbody>
              <TableRow label="Capital invertido" real={r.capital_invertido} dca={d.capital_invertido} fmt="currency" />
              <TableRow label="BTC acumulado" real={r.btc_acumulado} dca={d.btc_acumulado} fmt="btc" />
              <TableRow label="Valor actual" real={r.valor_actual} dca={d.valor_actual} fmt="currency" />
              <TableRow label="Beneficio" real={r.beneficio} dca={d.beneficio} fmt="currency" />
              <TableRow label="Rentabilidad" real={r.rentabilidad_pct} dca={d.rentabilidad_pct} fmt="percent" />
              <TableRow label="Coste medio BTC" real={r.coste_medio} dca={d.coste_medio} fmt="currency" />
              <TableRow label="Compras" real={r.num_compras} dca={d.num_compras} fmt="number" />
              <TableRow label="Ventas" real={r.num_ventas} dca={d.num_ventas} fmt="number" />
              <TableRow label="Máx. Drawdown" real={r.max_drawdown_pct} dca={d.max_drawdown_pct} fmt="percent" negativeIsGood />
            </tbody>
          </table>
        </div>
      </div>

      {/* Gráficos */}
      {data.charts && (
        <>
          {/* 1. Evolución ambas carteras */}
          {data.charts.evolucion_real && data.charts.evolucion_dca && (
            <ChartCard title="Evolución: Tu Cartera vs DCA" icon={TrendingUp} color={COLORS.real}>
              <div className="h-[200px] md:h-[300px]"><ResponsiveContainer width="100%" height="100%">
                <LineChart>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis
                    dataKey="fecha"
                    stroke="#475569" fontSize={11}
                    tickFormatter={(v) => v?.slice(5) || ''}
                    type="category"
                    allowDuplicatedCategory={false}
                  />
                  <YAxis stroke="#475569" fontSize={11} tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} />
                  <Tooltip
                    contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#e2e8f0' }}
                    formatter={(value: number) => [`$${value.toLocaleString('en-US', { minimumFractionDigits: 2 })}`]}
                  />
                  <Line data={data.charts.evolucion_real} dataKey="valor" stroke={COLORS.real} strokeWidth={2} dot={false} name="Tu cartera" />
                  <Line data={data.charts.evolucion_dca} dataKey="valor" stroke={COLORS.dca} strokeWidth={2} dot={false} name="DCA" />
                </LineChart>
              </ResponsiveContainer></div>
              <div className="flex items-center gap-4 mt-3 text-xs">
                <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-btc-orange inline-block" /> Tu cartera</span>
                <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-blue-400 inline-block" /> DCA</span>
              </div>
            </ChartCard>
          )}

          {/* 2. Diferencia acumulada */}
          {data.charts.diferencia && data.charts.diferencia.length > 0 && (
            <ChartCard title="Diferencia Acumulada (Real - DCA)" icon={BarChart3} color={COLORS.purple}>
              <div className="h-[150px] md:h-[220px]"><ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.charts.diferencia}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="fecha" stroke="#475569" fontSize={11} tickFormatter={(v) => v?.slice(5) || ''} />
                  <YAxis stroke="#475569" fontSize={11} tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} />
                  <Tooltip
                    contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#e2e8f0' }}
                    formatter={(value: number) => [`$${value.toLocaleString('en-US', { minimumFractionDigits: 2 })}`, 'Diferencia']}
                  />
                  <Bar
                    dataKey="diferencia"
                    radius={[3, 3, 0, 0]}
                    shape={(props: any) => {
                      const { x, y, width, height, payload } = props
                      const fill = payload?.diferencia >= 0 ? COLORS.green : COLORS.red
                      return <rect x={x} y={y} width={width} height={height} fill={fill} rx={3} ry={3} />
                    }}
                  />
                </BarChart>
              </ResponsiveContainer></div>
            </ChartCard>
          )}

          {/* 3. BTC acumulados */}
          {data.charts.btc_acumulado && data.charts.btc_acumulado.length > 0 && (
            <ChartCard title="BTC Acumulados" icon={Bitcoin} color={COLORS.cyan}>
              <div className="h-[180px] md:h-[260px]"><ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.charts.btc_acumulado}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="fecha" stroke="#475569" fontSize={11} tickFormatter={(v) => v?.slice(5) || ''} />
                  <YAxis stroke="#475569" fontSize={11} tickFormatter={(v) => v.toFixed(4)} domain={['auto', 'auto']} />
                  <Tooltip
                    contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#e2e8f0' }}
                    formatter={(value: number, name: string) => [
                      value.toFixed(8) + ' BTC',
                      name === 'real_btc' ? 'Tu cartera' : 'DCA'
                    ]}
                  />
                  <Area type="monotone" dataKey="real_btc" stroke={COLORS.real} fill={COLORS.real} fillOpacity={0.1} strokeWidth={2} name="real_btc" />
                  <Area type="monotone" dataKey="dca_btc" stroke={COLORS.dca} fill={COLORS.dca} fillOpacity={0.1} strokeWidth={2} name="dca_btc" />
                </AreaChart>
              </ResponsiveContainer></div>
              <div className="flex items-center gap-4 mt-3 text-xs">
                <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-btc-orange inline-block" /> Tu cartera</span>
                <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-blue-400 inline-block" /> DCA</span>
              </div>
            </ChartCard>
          )}

          {/* 4. Rentabilidad comparativa */}
          <ChartCard title="Rentabilidad vs DCA" icon={Target} color={COLORS.purple}>
            <div className="grid grid-cols-2 gap-4">
              <div className="text-center p-4 rounded-lg bg-surface-light/50">
                <p className="text-sm text-gray-500 mb-1">Tu Cartera</p>
                <p className={`text-2xl md:text-3xl font-bold font-mono ${r.rentabilidad_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {r.rentabilidad_pct >= 0 ? '+' : ''}{r.rentabilidad_pct?.toFixed(1)}%
                </p>
              </div>
              <div className="text-center p-4 rounded-lg bg-surface-light/50">
                <p className="text-sm text-gray-500 mb-1">DCA</p>
                <p className={`text-2xl md:text-3xl font-bold font-mono ${d.rentabilidad_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {d.rentabilidad_pct >= 0 ? '+' : ''}{d.rentabilidad_pct?.toFixed(1)}%
                </p>
              </div>
            </div>
            <div className="mt-4 p-3 rounded-lg bg-surface-light/30 text-center">
              <p className="text-sm text-gray-500">Diferencia</p>
              <p className={`text-2xl font-bold font-mono ${cmp.diferencia_rentabilidad_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {cmp.diferencia_rentabilidad_pct >= 0 ? '+' : ''}{cmp.diferencia_rentabilidad_pct?.toFixed(2)} puntos
              </p>
            </div>
          </ChartCard>
        </>
      )}

      {/* AI Insights — Motor de Inteligencia */}
      {data.intelligence && data.intelligence.observations && data.intelligence.observations.length > 0 && (
        <div className="card bg-gradient-to-r from-purple-500/5 to-btc-orange/5 border border-purple-500/10">
          <div className="flex items-center gap-2 mb-4">
            <BrainCircuit className="w-5 h-5 text-purple-400" />
            <h2 className="text-lg font-semibold text-gray-200">Análisis Inteligente</h2>
            {data.intelligence.timing_score != null && (
              <span className={`ml-auto text-xs font-bold px-2 py-1 rounded-full ${
                data.intelligence.timing_score > 0 ? 'bg-green-500/10 text-green-400' :
                data.intelligence.timing_score < 0 ? 'bg-red-500/10 text-red-400' :
                'bg-gray-500/10 text-gray-400'
              }`}>
                Timing: {data.intelligence.timing_score > 0 ? '+' : ''}{data.intelligence.timing_score}
              </span>
            )}
          </div>

          {/* Resumen */}
          {data.intelligence.summary && (
            <p className="text-sm text-gray-400 mb-4 italic border-l-2 border-purple-500/30 pl-3">
              {data.intelligence.summary}
            </p>
          )}

          {/* Observaciones */}
          <div className="space-y-3">
            {data.intelligence.observations.map((obs: any, i: number) => (
              <div
                key={i}
                className={`flex items-start gap-3 p-3 rounded-lg ${
                  obs.impact === 'positive' ? 'bg-green-500/5 border border-green-500/10' :
                  obs.impact === 'negative' ? 'bg-red-500/5 border border-red-500/10' :
                  'bg-surface-light/50 border border-surface-light'
                }`}
              >
                <span className="text-lg shrink-0 mt-0.5">{obs.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold text-gray-200">{obs.title}</p>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                      obs.impact === 'positive' ? 'bg-green-500/10 text-green-400' :
                      obs.impact === 'negative' ? 'bg-red-500/10 text-red-400' :
                      'bg-gray-500/10 text-gray-400'
                    }`}>
                      {obs.impact === 'positive' ? '👍 Positivo' : obs.impact === 'negative' ? '👎 A mejorar' : 'ℹ️'}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mt-1 leading-relaxed">{obs.detail}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Métricas adicionales */}
          {data.intelligence.buy_dip_count > 0 && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4 pt-4 border-t border-surface-light">
              <MiniInsight label="Compras en caídas" value={`${data.intelligence.buy_dip_count}`} color="text-green-400" />
              <MiniInsight label="Ventas prematuras" value={`${data.intelligence.sell_premature_count}`} color="text-red-400" />
              <MiniInsight label="Ventas acertadas" value={`${data.intelligence.sell_good_count}`} color="text-green-400" />
              <MiniInsight label="P&L perdido ventas" value={`$${data.intelligence.pnl_lost_from_sells?.toLocaleString('en-US', { minimumFractionDigits: 0 }) || '0'}`} color={data.intelligence.pnl_lost_from_sells > 0 ? 'text-red-400' : 'text-gray-400'} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Componentes ──

function TableRow({
  label, real, dca, fmt, negativeIsGood,
}: {
  label: string; real: number; dca: number; fmt: 'currency' | 'percent' | 'btc' | 'number'; negativeIsGood?: boolean
}) {
  const diff = real - dca
  const fmtVal = (v: number) => {
    switch (fmt) {
      case 'currency': return `$${v.toLocaleString('en-US', { minimumFractionDigits: 2 })}`
      case 'percent': return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`
      case 'btc': return `${v.toFixed(8)} BTC`
      case 'number': return v.toLocaleString()
    }
  }

  const isDiffPositive = negativeIsGood ? diff < 0 : diff > 0

  return (
    <tr className="border-b border-surface-light/50 hover:bg-surface-light/20">
      <td className="py-2.5 px-2 text-gray-400">{label}</td>
      <td className="py-2.5 px-2 text-right font-mono font-medium text-btc-orange">{fmtVal(real)}</td>
      <td className="py-2.5 px-2 text-right font-mono font-medium text-blue-400">{fmtVal(dca)}</td>
      <td className={`py-2.5 px-2 text-right font-mono font-medium ${isDiffPositive ? 'text-green-400' : diff !== 0 ? 'text-red-400' : 'text-gray-500'}`}>
        {diff !== 0 ? `${diff >= 0 ? '+' : ''}${fmt === 'percent' ? diff.toFixed(2) + '%' : fmt === 'currency' ? '$' + Math.abs(diff).toLocaleString('en-US', { minimumFractionDigits: 2 }) : fmt === 'btc' ? diff.toFixed(8) + ' BTC' : diff.toLocaleString()}` : '—'}
      </td>
    </tr>
  )
}

function ChartCard({ title, icon: Icon, color, children }: {
  title: string; icon: any; color: string; children: React.ReactNode
}) {
  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-4">
        <Icon className="w-5 h-5" style={{ color }} />
        <h2 className="text-lg font-semibold text-gray-200">{title}</h2>
      </div>
      {children}
    </div>
  )
}

function MiniInsight({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="text-center">
      <p className="text-xs text-gray-600 mb-1">{label}</p>
      <p className={`text-lg font-bold font-mono ${color}`}>{value}</p>
    </div>
  )
}

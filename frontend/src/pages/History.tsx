import { useQuery } from '@tanstack/react-query'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area, CartesianGrid,
} from 'recharts'
import {
  TrendingUp, TrendingDown, DollarSign, Bitcoin, Wallet,
  BarChart3, Calendar, Clock, Activity,
} from 'lucide-react'
import { portfolio as portfolioApi, operations as opsApi, prices as pricesApi } from '../api/client'
import { EmptyState } from '../components/EmptyState'
import { DashboardSkeleton } from '../components/Skeleton'
import { useToast } from '../components/Toast'

const CHART_COLORS = {
  btc: '#f7931a',
  green: '#22c55e',
  red: '#ef4444',
  blue: '#3b82f6',
  purple: '#a855f7',
  yellow: '#eab308',
  cyan: '#06b6d4',
  gray: '#64748b',
}

export default function History() {
  const { toast } = useToast()
  const { data: charts, isLoading: chartsLoading } = useQuery({
    queryKey: ['portfolioCharts'],
    queryFn: portfolioApi.charts,
    refetchInterval: 60000,
  })

  const { data: btcChart } = useQuery({
    queryKey: ['btcChart', 90],
    queryFn: () => pricesApi.chart(90),
    refetchInterval: 300000,
  })

  const { data: ops, isLoading: opsLoading } = useQuery({
    queryKey: ['operations'],
    queryFn: () => opsApi.list(50),
    refetchInterval: 30000,
  })

  const { data: techAnalysis } = useQuery({
    queryKey: ['analysis'],
    queryFn: portfolioApi.analysis,
    refetchInterval: 300000,
  })

  const btcChartPrices = btcChart?.prices?.map((p: any) => ({
    time: new Date(p.timestamp).toLocaleDateString(),
    price: p.price,
  })) || []

  if (chartsLoading) {
    return <DashboardSkeleton />
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-100">📊 Gráficos y Evolución</h1>

      {!charts ? (
        <EmptyState icon={BarChart3} title="Sin datos históricos" description="No hay datos históricos para mostrar gráficos." />
      ) : (
        <>
          {/* ── 1. Evolución Patrimonio ── */}
          <ChartCard title="Evolución del Patrimonio" icon={TrendingUp} color={CHART_COLORS.btc}>
            <div className="h-[200px] md:h-[280px]"><ResponsiveContainer width="100%" height="100%">
              <AreaChart data={charts.patrimonio}>
                <defs>
                  <linearGradient id="gradPatrimonio" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={CHART_COLORS.btc} stopOpacity={0.25} />
                    <stop offset="100%" stopColor={CHART_COLORS.btc} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="fecha" stroke="#475569" fontSize={11} tickFormatter={(v) => v?.slice(5) || ''} />
                <YAxis stroke="#475569" fontSize={11} tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#e2e8f0' }}
                  formatter={(value: number) => [`$${value.toLocaleString('en-US', { minimumFractionDigits: 2 })}`, 'Valor']}
                  labelFormatter={(label) => `Fecha: ${label}`}
                />
                <Area type="monotone" dataKey="valor" stroke={CHART_COLORS.btc} fill="url(#gradPatrimonio)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer></div>
          </ChartCard>

          {/* ── 2. Evolución BTC ── */}
          {btcChartPrices.length > 0 && (
            <ChartCard title="Evolución BTC (90 días)" icon={Bitcoin} color={CHART_COLORS.btc}>
              <div className="h-[180px] md:h-[260px]"><ResponsiveContainer width="100%" height="100%">
                <AreaChart data={btcChartPrices}>
                  <defs>
                    <linearGradient id="gradBtc" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={CHART_COLORS.btc} stopOpacity={0.2} />
                      <stop offset="100%" stopColor={CHART_COLORS.btc} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="time" stroke="#475569" fontSize={11} />
                  <YAxis stroke="#475569" fontSize={11} domain={['auto', 'auto']} tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} />
                  <Tooltip
                    contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#e2e8f0' }}
                    formatter={(value: number) => [`$${value.toLocaleString('en-US', { minimumFractionDigits: 2 })}`, 'BTC/USD']}
                  />
                  <Area type="monotone" dataKey="price" stroke={CHART_COLORS.btc} fill="url(#gradBtc)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer></div>
            </ChartCard>
          )}

          {/* ── 3. Ganancia Diaria ── */}
          <ChartCard title="Ganancia / Pérdida Diaria" icon={Activity} color={CHART_COLORS.green}>
            <div className="h-[160px] md:h-[220px]"><ResponsiveContainer width="100%" height="100%">
              <BarChart data={charts.ganancia_diaria}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="fecha" stroke="#475569" fontSize={11} tickFormatter={(v) => v?.slice(5) || ''} />
                <YAxis stroke="#475569" fontSize={11} tickFormatter={(v) => `$${v}`} />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#e2e8f0' }}
                  formatter={(value: number) => [`$${value.toFixed(2)}`, 'Ganancia']}
                  labelFormatter={(label) => `Fecha: ${label}`}
                />
                <Bar
                  dataKey="ganancia"
                  fill={CHART_COLORS.green}
                  radius={[3, 3, 0, 0]}
                  shape={(props: any) => {
                    const { x, y, width, height, payload } = props
                    const fill = payload?.ganancia >= 0 ? CHART_COLORS.green : CHART_COLORS.red
                    return <rect x={x} y={y} width={width} height={height} fill={fill} rx={3} ry={3} />
                  }}
                />
              </BarChart>
            </ResponsiveContainer></div>
          </ChartCard>

          {/* ── 4. Beneficio Acumulado ── */}
          <ChartCard title="Beneficio / Pérdida Acumulado" icon={TrendingUp} color={CHART_COLORS.green}>
            <div className="h-[180px] md:h-[260px]"><ResponsiveContainer width="100%" height="100%">
              <AreaChart data={charts.beneficio_acumulado}>
                <defs>
                  <linearGradient id="gradPnl" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={CHART_COLORS.green} stopOpacity={0.2} />
                    <stop offset="100%" stopColor={CHART_COLORS.green} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="fecha" stroke="#475569" fontSize={11} tickFormatter={(v) => v?.slice(5) || ''} />
                <YAxis stroke="#475569" fontSize={11} tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#e2e8f0' }}
                  formatter={(value: number) => [`$${value.toLocaleString('en-US', { minimumFractionDigits: 2 })}`, 'P&L']}
                  labelFormatter={(label) => `Fecha: ${label}`}
                />
                <Area type="monotone" dataKey="pnl" stroke={CHART_COLORS.green} fill="url(#gradPnl)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer></div>
          </ChartCard>

          {/* ── 5. Aportes de Capital ── */}
          {charts.aportes && charts.aportes.length > 0 && (
            <ChartCard title="Aportes de Capital" icon={Wallet} color={CHART_COLORS.blue}>
              <div className="h-[160px] md:h-[220px]"><ResponsiveContainer width="100%" height="100%">
                <BarChart data={charts.aportes}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="fecha" stroke="#475569" fontSize={11} />
                  <YAxis stroke="#475569" fontSize={11} tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} />
                  <Tooltip
                    contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#e2e8f0' }}
                    formatter={(value: number, name: string) => [`$${value.toFixed(2)}`, name === 'monto' ? 'Aporte' : 'Acumulado']}
                  />
                  <Bar dataKey="monto" fill={CHART_COLORS.blue} radius={[3, 3, 0, 0]} name="monto" />
                </BarChart>
              </ResponsiveContainer></div>
            </ChartCard>
          )}

          {/* ── 6. Evolución Coste Medio BTC ── */}
          {charts.coste_medio && charts.coste_medio.length > 0 && (
            <ChartCard title="Evolución del Coste Medio BTC" icon={Bitcoin} color={CHART_COLORS.purple}>
              <div className="h-[180px] md:h-[260px]"><ResponsiveContainer width="100%" height="100%">
                <LineChart data={charts.coste_medio}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="fecha" stroke="#475569" fontSize={11} />
                  <YAxis stroke="#475569" fontSize={11} tickFormatter={(v) => `$${v.toLocaleString()}`} />
                  <Tooltip
                    contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#e2e8f0' }}
                    formatter={(value: number, name: string) => [
                      name === 'coste_medio' ? `$${value.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : `${value.toFixed(8)} BTC`,
                      name === 'coste_medio' ? 'Coste Medio' : 'BTC Acumulado'
                    ]}
                  />
                  <Line type="monotone" dataKey="coste_medio" stroke={CHART_COLORS.purple} strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="btc_acumulado" stroke={CHART_COLORS.cyan} strokeWidth={1.5} dot={false} opacity={0.5} />
                </LineChart>
              </ResponsiveContainer></div>
            </ChartCard>
          )}

          {/* ── 7. Rentabilidad Mensual ── */}
          {charts.rentabilidad_mensual && charts.rentabilidad_mensual.length > 0 && (
            <ChartCard title="Rentabilidad Mensual" icon={Calendar} color={CHART_COLORS.yellow}>
              <div className="h-[180px] md:h-[250px]"><ResponsiveContainer width="100%" height="100%">
                <BarChart data={charts.rentabilidad_mensual}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="mes" stroke="#475569" fontSize={11} />
                  <YAxis stroke="#475569" fontSize={11} tickFormatter={(v) => `${v.toFixed(1)}%`} />
                  <Tooltip
                    contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#e2e8f0' }}
                    formatter={(value: number) => [`${value.toFixed(2)}%`, 'Retorno']}
                    labelFormatter={(label) => `Mes: ${label}`}
                  />
                  <Bar
                    dataKey="retorno"
                    radius={[3, 3, 0, 0]}
                    shape={(props: any) => {
                      const { x, y, width, height, payload } = props
                      const fill = payload?.retorno >= 0 ? CHART_COLORS.green : CHART_COLORS.red
                      return <rect x={x} y={y} width={width} height={height} fill={fill} rx={3} ry={3} />
                    }}
                  />              </BarChart>
            </ResponsiveContainer></div>
          </ChartCard>
          )}

          {/* ── Análisis Técnico BTC ── */}
          {techAnalysis && (
            <ChartCard title="Análisis Técnico BTC" icon={Bitcoin} color={CHART_COLORS.btc}>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                <MiniStat label="RSI" value={techAnalysis.rsi?.toFixed(1)} color={techAnalysis.rsi > 70 ? 'text-red-400' : techAnalysis.rsi < 30 ? 'text-green-400' : 'text-gray-200'} />
                <MiniStat label="SMA 50" value={techAnalysis.sma_50 ? `$${(techAnalysis.sma_50).toLocaleString('en-US', { maximumFractionDigits: 0 })}` : '—'} color="text-gray-200" />
                <MiniStat label="SMA 200" value={techAnalysis.sma_200 ? `$${(techAnalysis.sma_200).toLocaleString('en-US', { maximumFractionDigits: 0 })}` : '—'} color="text-gray-200" />
                <MiniStat label="Tendencia" value={techAnalysis.trend} color={techAnalysis.trend === 'alcista' ? 'text-green-400' : techAnalysis.trend === 'bajista' ? 'text-red-400' : 'text-yellow-400'} />
              </div>
              <p className="text-xs text-gray-600">Señal general: <span className="font-semibold uppercase">{techAnalysis.overall_signal}</span></p>
            </ChartCard>
          )}

          {/* ── Resumen de indicadores clave ── */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <KpiCard
              title="Patrimonio"
              value={charts.patrimonio?.[charts.patrimonio.length - 1]?.valor}
              prefix="$"
              icon={DollarSign}
              color="text-btc-orange"
            />
            <KpiCard
              title="BTC"
              value={charts.patrimonio?.[charts.patrimonio.length - 1]?.btc}
              suffix=" BTC"
              icon={Bitcoin}
              color="text-btc-orange"
            />
            <KpiCard
              title="USDC"
              value={charts.patrimonio?.[charts.patrimonio.length - 1]?.usdc}
              prefix="$"
              icon={Wallet}
              color="text-blue-400"
            />
            <KpiCard
              title="P&L Acumulado"
              value={charts.beneficio_acumulado?.[charts.beneficio_acumulado.length - 1]?.pnl}
              prefix="$"
              icon={TrendingUp}
              color={
                (charts.beneficio_acumulado?.[charts.beneficio_acumulado.length - 1]?.pnl || 0) >= 0
                  ? 'text-green-400' : 'text-red-400'
              }
            />
          </div>
        </>
      )}

      {/* ── Separador ── */}
      <hr className="border-surface-light my-8" />

      {/* ── Historial de Operaciones ── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h2 className="text-xl font-bold text-gray-100 flex items-center gap-2">
          <Clock className="w-5 h-5 text-gray-400" />
          Historial de Operaciones
        </h2>
        <button
          onClick={async () => {
            try {
              const blob = await opsApi.exportCsv()
              const url = URL.createObjectURL(blob)
              const a = document.createElement('a')
              a.href = url
              a.download = 'tokomagraf_operaciones.csv'
              a.click()
              URL.revokeObjectURL(url)
            } catch { toast('error', 'Error al exportar CSV') }
          }}
          className="btn-secondary flex items-center gap-2 py-2 px-4 text-sm w-full sm:w-auto"
        >
          📥 Exportar CSV
        </button>
      </div>

      {opsLoading ? (
        <div className="space-y-2">
          {[1,2,3,4].map(i => <div key={i} className="card py-3"><div className="animate-pulse bg-surface-light rounded h-12" /></div>)}
        </div>
      ) : !ops || ops.length === 0 ? (
        <EmptyState icon={Clock} title="Sin operaciones" description="No hay operaciones registradas." size="sm" />
      ) : (
        <div className="space-y-2">
          {ops.map((op: any) => (
            <div key={op.id} className="card flex items-center justify-between py-3 px-3 sm:px-5 gap-2">
              <div className="flex items-center gap-2 sm:gap-4 min-w-0">
                <span className={`text-lg shrink-0 ${
                  op.tipo === 'buy' ? 'text-green-400' :
                  op.tipo === 'sell' ? 'text-red-400' :
                  op.tipo === 'deposit' ? 'text-blue-400' : 'text-yellow-400'
                }`}>
                  {op.tipo === 'buy' ? '🟢' : op.tipo === 'sell' ? '🔴' : op.tipo === 'deposit' ? '📥' : '📤'}
                </span>
                <div className="min-w-0">
                  <p className="font-semibold text-gray-200 capitalize truncate text-sm sm:text-base">{op.tipo} · {op.activo}</p>
                  <p className="text-xs text-gray-500 truncate">{new Date(op.fecha).toLocaleString()}</p>
                </div>
              </div>
              <div className="text-right shrink-0">
                <p className="font-mono font-bold text-gray-100 text-sm sm:text-base truncate">{op.cantidad} {op.activo}</p>
                <p className="text-xs text-gray-500">@ ${op.precio?.toFixed(2)}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Componentes ──

function ChartCard({
  title, icon: Icon, color, children,
}: {
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

function MiniStat({ label, value, color }: { label: string; value: string | undefined; color: string }) {
  return (
    <div className="bg-surface-light/50 rounded-lg p-3 text-center">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`text-sm font-bold font-mono ${color || 'text-gray-200'}`}>{value || '—'}</p>
    </div>
  )
}

function KpiCard({
  title, value, prefix, suffix, icon: Icon, color,
}: {
  title: string; value: number | undefined; prefix?: string; suffix?: string; icon: any; color: string
}) {
  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`w-4 h-4 ${color}`} />
        <p className="text-xs text-gray-500">{title}</p>
      </div>
      <p className={`text-lg font-bold font-mono ${color}`}>
        {value != null ? `${prefix || ''}${value.toLocaleString('en-US', { minimumFractionDigits: 2 })}${suffix || ''}` : '—'}
      </p>
    </div>
  )
}

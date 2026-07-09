import { useQuery } from '@tanstack/react-query'
import { useState, useEffect, useMemo } from 'react'
import { TrendingUp, TrendingDown, DollarSign, Bitcoin, Wallet, BarChart3, Calendar, ArrowUpRight, ArrowDownRight, Clock, Zap } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Area, AreaChart, ReferenceDot, ReferenceLine, ReferenceArea } from 'recharts'
import { portfolio as portfolioApi, prices as pricesApi } from '../api/client'
import { DashboardSkeleton } from '../components/Skeleton'

export default function Dashboard() {
  const { data: dash, isLoading: dashLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: portfolioApi.dashboard,
    refetchInterval: 60000,
  })

  const { data: chartData } = useQuery({
    queryKey: ['btcChart', 7],
    queryFn: () => pricesApi.chart(7),
  })

  const { data: intradayData } = useQuery({
    queryKey: ['btcChart', 1],
    queryFn: () => pricesApi.chart(1),
    refetchInterval: 300000,
  })

  const { data: analysis } = useQuery({
    queryKey: ['analysis'],
    queryFn: portfolioApi.analysis,
    refetchInterval: 300000,
  })

  const [chartMode, setChartMode] = useState<'portfolio' | 'btc'>('portfolio')
  const zoneOpacity = (() => {
    const saved = localStorage.getItem('chartZoneOpacity')
    return saved ? parseInt(saved) / 100 : 0.06
  })()

  const portfolioChartData = useMemo(() => {
    if (!chartData?.prices?.length || !dash) return []
    const btc = dash.btc_balance || 0
    const usdc = dash.usdc_balance || 0
    return chartData.prices.map((p: any) => ({
      time: new Date(p.timestamp).toLocaleDateString(),
      value: btc * p.price + usdc,
    }))
  }, [chartData, dash?.btc_balance, dash?.usdc_balance])

  const btcChartData = useMemo(() => {
    if (!chartData?.prices?.length) return []
    return chartData.prices.map((p: any) => ({
      time: new Date(p.timestamp).toLocaleDateString(),
      value: p.price,
    }))
  }, [chartData])

  const dailyVolatility = useMemo(() => {
    if (!chartData?.prices?.length || !dash) return []
    const btc = dash.btc_balance || 0
    const usdc = dash.usdc_balance || 0
    const invested = dash.total_invested || 0
    const byDay: Record<string, { high: number; low: number; close: number }> = {}
    for (const p of chartData.prices) {
      const portfolioVal = btc * p.price + usdc
      const day = new Date(p.timestamp).toLocaleDateString()
      if (!byDay[day]) byDay[day] = { high: portfolioVal, low: portfolioVal, close: portfolioVal }
      else {
        if (portfolioVal > byDay[day].high) byDay[day].high = portfolioVal
        if (portfolioVal < byDay[day].low) byDay[day].low = portfolioVal
        byDay[day].close = portfolioVal
      }
    }
    return Object.entries(byDay)
      .map(([day, { high, low, close }]) => ({
        day, high, low, close,
        rangePct: ((high - low) / low * 100),
        vsInvested: invested > 0 ? close - invested : 0,
        aboveInvested: close >= invested,
      }))
      .sort((a, b) => b.rangePct - a.rangePct)
      .slice(0, 4)
  }, [chartData, dash?.btc_balance, dash?.usdc_balance, dash?.total_invested])

  if (dashLoading) {
    return <DashboardSkeleton />
  }

  if (!dash) {
    return (
      <div className="card text-center py-16">
        <Bitcoin className="w-16 h-16 text-btc-orange mx-auto mb-4" />
        <h2 className="text-xl font-bold text-gray-200 mb-2">Bienvenido a tokomagraf</h2>
        <p className="text-gray-500">Registrá tu primera operación para ver tu dashboard.</p>
      </div>
    )
  }

  const isPositive = dash.total_pnl >= 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-100">Panel de Cartera</h1>
        <span className="text-sm text-gray-500">🕐 {new Date(dash.updated_at).toLocaleString()}</span>
      </div>

      {/* Main Value */}
      <div className="card">
        <p className="text-sm text-gray-500 uppercase tracking-wider mb-1">Patrimonio Total</p>
        <p className="text-3xl md:text-5xl font-bold text-gray-100 font-mono tabular-nums">
          ${dash.portfolio_value.toLocaleString('en-US', { minimumFractionDigits: 2 })}
        </p>
        <div className="flex items-center gap-2 mt-2">
          <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm font-semibold ${
            isPositive ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
          }`}>
            {isPositive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
            {isPositive ? '+' : ''}{dash.total_pnl_pct?.toFixed(2)}%
          </span>
          <span className={`font-mono text-sm ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
            {isPositive ? '+' : ''}${Math.abs(dash.total_pnl).toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </span>
        </div>
      </div>

      {/* Daily & Monthly Result */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <DailyResultCard
          dailyProfit={dash.daily_profit}
          portfolioValue={dash.portfolio_value}
          label="Resultado del día"
          sparklineData={intradayData?.prices?.map((p: any) => p.price) || []}
          btcBalance={dash.btc_balance || 0}
          usdcBalance={dash.usdc_balance || 0}
          showCloseCountdown
        />
        <DailyResultCard
          dailyProfit={dash.monthly_profit}
          portfolioValue={dash.portfolio_value}
          label="Resultado del mes"
        />
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard icon={Bitcoin} label="BTC" value={dash.btc_balance?.toFixed(8)} color="text-btc-orange" />
        <StatCard icon={DollarSign} label="USDC" value={`$${dash.usdc_balance?.toFixed(2)}`} color="text-blue-400" />
        <StatCard icon={Wallet} label="Capital Aportado" value={`$${dash.total_invested?.toLocaleString('en-US', { minimumFractionDigits: 2 })}`} color="text-gray-400" />
        <StatCard icon={BarChart3} label="Precio BTC" value={`$${dash.btc_price?.toLocaleString('en-US', { minimumFractionDigits: 2 })}`} color="text-btc-orange" />
      </div>

      {/* Daily Volatility Ranking */}
      {dailyVolatility.length > 0 && (
        <div className="card">
          <div className="flex items-center gap-2 mb-3">
            <Zap className="w-4 h-4 text-yellow-400" />
            <h2 className="text-lg font-semibold text-gray-200">Días con mayor volatilidad</h2>
          </div>
          <div className="space-y-2">
            {dailyVolatility.map((d, i) => (
              <div key={d.day} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-600 w-5">#{i + 1}</span>
                  <span className="text-gray-400">{d.day}</span>
                  <span className="text-xs text-gray-600">
                    ${d.low.toLocaleString('en-US', { maximumFractionDigits: 0 })} → ${d.high.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                  </span>
                  <span className={`text-[10px] font-mono ${d.aboveInvested ? 'text-green-400' : 'text-red-400'}`}>
                    {d.aboveInvested ? '▲' : '▼'} ${Math.abs(d.vsInvested).toLocaleString('en-US', { maximumFractionDigits: 0 })}
                  </span>
                </div>
                <span className={`font-mono font-semibold text-sm ${d.rangePct > 5 ? 'text-red-400' : d.rangePct > 2 ? 'text-yellow-400' : 'text-green-400'}`}>
                  {d.rangePct.toFixed(2)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Price Chart */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-200">
            📈 {chartMode === 'portfolio' ? 'Portfolio' : 'BTC/USD'} — Últimos 7 días
          </h2>
          <div className="flex bg-surface rounded-lg p-0.5">
            <button
              onClick={() => setChartMode('portfolio')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                chartMode === 'portfolio' ? 'bg-btc-orange/20 text-btc-orange' : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              Portfolio
            </button>
            <button
              onClick={() => setChartMode('btc')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                chartMode === 'btc' ? 'bg-btc-orange/20 text-btc-orange' : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              BTC
            </button>
          </div>
        </div>
        {(chartMode === 'portfolio' ? portfolioChartData : btcChartData).length > 0 ? (
          <div className="h-[220px] md:h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartMode === 'portfolio' ? portfolioChartData : btcChartData}>
              <defs>
                <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f7931a" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#f7931a" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="time" stroke="#475569" fontSize={12} />
              <YAxis stroke="#475569" fontSize={12} domain={['auto', 'auto']} tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#e2e8f0' }}
                formatter={(value: number) => [`$${value.toLocaleString('en-US', { minimumFractionDigits: 2 })}`, chartMode === 'portfolio' ? 'Patrimonio' : 'BTC/USD']}
              />
              <Area type="monotone" dataKey="value" stroke="#f7931a" fill="url(#colorPrice)" strokeWidth={2} />
              {chartMode === 'portfolio' && (
                <>
                  <ReferenceArea y1={dash.total_invested} y2={999999999} fill="#4ade80" fillOpacity={zoneOpacity} label={{ value: 'Zona de ganancia', position: 'insideTop', fill: '#4ade80', fontSize: 10 }} />
                  <ReferenceArea y1={0} y2={dash.total_invested} fill="#f87171" fillOpacity={zoneOpacity} label={{ value: 'Zona de pérdida', position: 'insideBottom', fill: '#f87171', fontSize: 10 }} />
                  <ReferenceLine y={dash.total_invested} stroke="#64748b" strokeDasharray="6 4" strokeWidth={1} label={{ value: 'Capital aportado', position: 'insideTopRight', fill: '#94a3b8', fontSize: 11 }} />
                </>
              )}
            </AreaChart>
          </ResponsiveContainer>
        </div>
        ) : (
          <div className="h-[220px] md:h-[300px] flex items-center justify-center text-gray-600">Cargando gráfica…</div>
        )}
      </div>

      {/* Analysis Summary */}
      {analysis && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="card">
            <p className="text-sm text-gray-500 mb-1">Tendencia</p>
            <p className="text-2xl font-bold capitalize text-gray-100">{analysis.trend}</p>
            <p className="text-sm text-gray-500 mt-1">Señal: <span className="font-semibold uppercase">{analysis.overall_signal}</span></p>
          </div>
          <div className="card">
            <p className="text-sm text-gray-500 mb-1">RSI (14)</p>
            <p className={`text-3xl font-bold ${analysis.rsi > 70 ? 'text-red-400' : analysis.rsi < 30 ? 'text-green-400' : 'text-yellow-400'}`}>
              {analysis.rsi?.toFixed(1)}
            </p>
            <p className="text-sm text-gray-500 mt-1">SMA 50: ${analysis.sma_50?.toLocaleString('en-US', { maximumFractionDigits: 0 })}</p>
          </div>
          <div className="card">
            <p className="text-sm text-gray-500 mb-1">Soporte / Resistencia</p>
            <p className="text-lg font-bold text-green-400">${analysis.support_resistance?.support?.toLocaleString('en-US', { maximumFractionDigits: 0 }) || '—'}</p>
            <p className="text-lg font-bold text-red-400">${analysis.support_resistance?.resistance?.toLocaleString('en-US', { maximumFractionDigits: 0 }) || '—'}</p>
          </div>
        </div>
      )}
    </div>
  )
}

function StatCard({ icon: Icon, label, value, color }: { icon: any; label: string; value: string; color: string }) {
  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`w-4 h-4 ${color}`} />
        <p className="stat-label">{label}</p>
      </div>
      <p className={`stat-value ${color}`}>{value || '—'}</p>
    </div>
  )
}

function DailyResultCard({ dailyProfit, portfolioValue, label, sparklineData, showCloseCountdown, btcBalance, usdcBalance }: { dailyProfit?: number | null; portfolioValue: number; label: string; sparklineData?: number[]; showCloseCountdown?: boolean; btcBalance?: number; usdcBalance?: number }) {
  if (dailyProfit == null) {
    return (
      <div className="card">
        <div className="flex items-center gap-2 mb-2">
          <Calendar className="w-4 h-4 text-gray-500" />
          <p className="stat-label">{label}</p>
        </div>
        <p className="text-sm text-gray-500">Sin datos aún</p>
        <p className="text-xs text-gray-600 mt-1">Disponible tras el primer día</p>
      </div>
    )
  }

  const isPositive = dailyProfit >= 0
  const startValue = portfolioValue - dailyProfit
  const pct = startValue > 0 ? (dailyProfit / startValue * 100) : 0
  const Icon = isPositive ? ArrowUpRight : ArrowDownRight
  const sparkColor = isPositive ? '#4ade80' : '#f87171'
  const sparkData = sparklineData?.map((price, i) => ({ i, price })) || []
  const gradId = `sparkGrad-${label.replace(/\s+/g, '-')}`
  const maxIdx = sparkData.length > 0 ? sparkData.reduce((maxI, p, i, arr) => p.price > arr[maxI].price ? i : maxI, 0) : -1
  const minIdx = sparkData.length > 0 ? sparkData.reduce((minI, p, i, arr) => p.price < arr[minI].price ? i : minI, 0) : -1
  const prices = sparklineData?.length ? sparklineData : null
  const dailyHigh = prices && btcBalance != null && usdcBalance != null
    ? (btcBalance || 0) * Math.max(...prices) + (usdcBalance || 0)
    : null
  const dailyLow = prices && btcBalance != null && usdcBalance != null
    ? (btcBalance || 0) * Math.min(...prices) + (usdcBalance || 0)
    : null
  const volatilityPct = dailyHigh != null && dailyLow != null && dailyLow > 0
    ? ((dailyHigh - dailyLow) / dailyLow * 100)
    : null

  const [timeToClose, setTimeToClose] = useState({ hours: 0, pct: 0 })

  useEffect(() => {
    if (!showCloseCountdown) return
    const update = () => {
      const now = new Date()
      const midnight = new Date(now)
      midnight.setHours(24, 0, 0, 0)
      const msLeft = midnight.getTime() - now.getTime()
      const hoursLeft = Math.max(0, msLeft / (1000 * 60 * 60))
      const msElapsed = now.getTime() - new Date(now).setHours(0, 0, 0, 0)
      const pctElapsed = Math.min(100, (msElapsed / (24 * 60 * 60 * 1000)) * 100)
      setTimeToClose({ hours: hoursLeft, pct: pctElapsed })
    }
    update()
    const timer = setInterval(update, 60000)
    return () => clearInterval(timer)
  }, [showCloseCountdown])

  return (
    <div className={`card border-l-4 ${isPositive ? 'border-l-green-500' : 'border-l-red-500'}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-gray-400" />
          <p className="stat-label">{label}</p>
        </div>
        <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold ${
          isPositive ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
        }`}>
          <Icon className="w-3.5 h-3.5" />
          {isPositive ? '+' : ''}{pct.toFixed(2)}%
        </span>
      </div>
      <div className="flex items-end gap-3">
        <div className="flex-1">
          <span className={`text-3xl font-bold font-mono tabular-nums ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
            {isPositive ? '+' : ''}${Math.abs(dailyProfit).toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </span>
          <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
            <span>Inicio: <span className="text-gray-400 font-mono">${startValue.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span></span>
            <span>Actual: <span className="text-gray-400 font-mono">${portfolioValue.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span></span>
          </div>
          {dailyHigh != null && dailyLow != null && (
            <div className="flex items-center gap-3 mt-1.5 text-[10px]">
              <span className="text-green-400">
                ▲ Máx: <span className="font-mono">${dailyHigh.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
              </span>
              <span className="text-red-400">
                ▼ Mín: <span className="font-mono">${dailyLow.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
              </span>
              {volatilityPct != null && (
                <span className="text-gray-500">
                  Rango: <span className="font-mono text-gray-400">{volatilityPct.toFixed(2)}%</span>
                </span>
              )}
            </div>
          )}
        </div>
        {sparkData.length > 1 && (
          <div className="w-24 h-12 shrink-0">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={sparkData}>
                <defs>
                  <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={sparkColor} stopOpacity={0.2} />
                    <stop offset="100%" stopColor={sparkColor} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area type="monotone" dataKey="price" stroke={sparkColor} fill={`url(#${gradId})`} strokeWidth={1.5} dot={false} />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '6px', color: '#e2e8f0', fontSize: '11px', padding: '4px 8px' }}
                  formatter={(value: number) => [`$${value.toLocaleString('en-US', { minimumFractionDigits: 2 })}`, 'BTC']}
                  labelFormatter={() => ''}
                />
                {maxIdx >= 0 && (
                  <ReferenceDot x={sparkData[maxIdx].i} y={sparkData[maxIdx].price} r={2.5} fill="#4ade80" stroke="#4ade80" strokeWidth={1} />
                )}
                {minIdx >= 0 && minIdx !== maxIdx && (
                  <ReferenceDot x={sparkData[minIdx].i} y={sparkData[minIdx].price} r={2.5} fill="#f87171" stroke="#f87171" strokeWidth={1} />
                )}
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
      {showCloseCountdown && (
        <div className="mt-3 pt-3 border-t border-surface-light">
          <div className="flex items-center justify-between text-xs text-gray-500 mb-1.5">
            <span className="flex items-center gap-1.5">
              <Clock className="w-3 h-3" />
              Cierre diario en
            </span>
            <span className="text-gray-400 font-mono">
              {timeToClose.hours < 1 ? '< 1 h' : `~${Math.round(timeToClose.hours)} h`}
            </span>
          </div>
          <div className="w-full h-1.5 bg-surface rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-1000"
              style={{
                width: `${timeToClose.pct}%`,
                background: timeToClose.pct > 80 ? '#f87171' : timeToClose.pct > 50 ? '#facc15' : '#4ade80',
              }}
            />
          </div>
          <p className="text-[10px] text-gray-600 mt-1">{timeToClose.pct.toFixed(0)}% del día transcurrido</p>
        </div>
      )}
    </div>
  )
}

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { portfolio as portfolioApi, prices as pricesApi } from '../api/client'
import { Calculator, Bitcoin, Target, HelpCircle, TrendingUp, TrendingDown } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine, Cell } from 'recharts'

const SCENARIOS = [
  { label: '-30%', factor: 0.7 },
  { label: 'Actual', factor: 1 },
  { label: '+50%', factor: 1.5 },
  { label: '2x', factor: 2 },
  { label: '3x', factor: 3 },
  { label: 'Personalizado', factor: null },
]

export default function ScenarioSimulator() {
  const navigate = useNavigate()
  const { data: dash } = useQuery({
    queryKey: ['dashboard'],
    queryFn: portfolioApi.dashboard,
    refetchInterval: 60000,
  })

  const { data: btcPrice } = useQuery({
    queryKey: ['btcPrice'],
    queryFn: pricesApi.btc,
    refetchInterval: 60000,
  })

  const [customPrice, setCustomPrice] = useState('')
  const [activeScenario, setActiveScenario] = useState<string>('Actual')

  const currentPrice = btcPrice?.price_usd || 0
  const btcBalance = dash?.btc_balance || 0
  const usdcBalance = dash?.usdc_balance || 0
  const invested = dash?.total_invested || 0

  const currentValue = dash?.portfolio_value || 0

  // Calcular resultados y sugerencias para cada escenario
  const getResult = (targetPrice: number) => {
    if (targetPrice <= 0) return null
    const projectedValue = btcBalance * targetPrice + usdcBalance
    const difference = projectedValue - currentValue
    const pctChange = currentValue > 0 ? (difference / currentValue) * 100 : 0
    const vsInvested = projectedValue - invested
    const vsInvestedPct = invested > 0 ? (vsInvested / invested) * 100 : 0

    // Sugerencia de acción
    const priceDiff = targetPrice - currentPrice
    const isBullish = targetPrice > currentPrice && currentPrice > 0
    const btcFromUsdc = usdcBalance > 0 && currentPrice > 0 ? usdcBalance / currentPrice : 0

    let suggestion = ''
    if (isBullish && usdcBalance > 0 && btcFromUsdc > 0.00001) {
      const extraGain = btcFromUsdc * (targetPrice - currentPrice)
      suggestion = `💡 Con tus $${usdcBalance.toFixed(0)} USDC comprarías ${btcFromUsdc.toFixed(6)} BTC → valdrían $${(btcFromUsdc * targetPrice).toLocaleString('en-US', { maximumFractionDigits: 0 })} (+$${extraGain.toLocaleString('en-US', { maximumFractionDigits: 0 })})`
    } else if (isBullish && usdcBalance <= 0) {
      const gainPerBtc = targetPrice - currentPrice
      suggestion = `💡 Cada BTC extra que compres hoy genera +$${gainPerBtc.toLocaleString('en-US', { maximumFractionDigits: 0 })} a este precio`
    } else if (targetPrice < currentPrice && btcBalance > 0 && currentPrice > 0) {
      const lossAvoided = btcBalance * (currentPrice - targetPrice)
      if (lossAvoided > 0) {
        suggestion = `🛡️ Vendiendo tus ${btcBalance.toFixed(4)} BTC ahora evitarías $${lossAvoided.toLocaleString('en-US', { maximumFractionDigits: 0 })} de pérdida`
      }
    }

    return { projectedValue, difference, pctChange, vsInvested, vsInvestedPct, suggestion, isBullish }
  }

  const scenarios = SCENARIOS.map(s => ({
    ...s,
    price: s.factor ? Math.round(currentPrice * s.factor) : parseFloat(customPrice) || 0,
    result: s.factor
      ? getResult(Math.round(currentPrice * s.factor))
      : customPrice ? getResult(parseFloat(customPrice)) : null,
    isActive: s.label === activeScenario,
  }))

  if (!dash && !btcPrice) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500 animate-pulse">Cargando datos de cartera…</div>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
        <Calculator className="w-6 h-6 text-btc-orange" />
        Simulador de Escenarios
      </h1>

      {/* Explicación */}
      <div className="card bg-btc-orange/5 border border-btc-orange/10">
        <div className="flex items-start gap-3">
          <HelpCircle className="w-5 h-5 text-btc-orange mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-btc-orange mb-1">¿Qué hace esto?</p>
            <p className="text-xs text-gray-400 leading-relaxed">
              <strong>Simulá</strong> cuánto valdría tu cartera si BTC llegara a distintos precios.
              Útil para planificar estrategias, definir targets de venta, o simplemente soñar 🚀.
              Los datos de BTC y USDC se toman de tu cartera real.
            </p>
          </div>
        </div>
      </div>

      {/* Datos actuales */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-200 mb-4 flex items-center gap-2">
          <Bitcoin className="w-5 h-5 text-btc-orange" />
          Tu cartera actual
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
          <div>
            <p className="text-xs text-gray-500 mb-1">BTC</p>
            <p className="text-xl font-bold font-mono text-btc-orange">{btcBalance.toFixed(8)}</p>
            <p className="text-[10px] text-gray-600">≈ ${(btcBalance * currentPrice).toLocaleString('en-US', { maximumFractionDigits: 0 })}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-1">USDC</p>
            <p className="text-xl font-bold font-mono text-blue-400">${usdcBalance.toFixed(2)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-1">Precio BTC</p>
            <p className="text-xl font-bold font-mono text-gray-100">
              ${currentPrice.toLocaleString('en-US', { maximumFractionDigits: 0 })}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-1">Valor cartera</p>
            <p className="text-xl font-bold font-mono text-green-400">
              ${currentValue.toLocaleString('en-US', { maximumFractionDigits: 0 })}
            </p>
          </div>
        </div>
        {invested > 0 && btcBalance > 0 && (
          <p className="text-xs text-gray-600 mt-3 text-center">
            Capital aportado: <span className="text-gray-400 font-mono">${invested.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
            {' · '}
            Precio breakeven: <span className="text-gray-400 font-mono">${Math.max(0, (invested - usdcBalance) / btcBalance).toLocaleString('en-US', { maximumFractionDigits: 0 })}</span>
            <span className="text-gray-600"> (recuperar inversión)</span>
          </p>
        )}
      </div>

      {/* Escenarios */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-200 mb-4 flex items-center gap-2">
          <Target className="w-5 h-5 text-btc-orange" />
          Escenarios de BTC
        </h2>

        {/* Botones de escenario */}
        <div className="flex flex-wrap gap-2 mb-6">
          {scenarios.map(s => (
            <button
              key={s.label}
              onClick={() => {
                setActiveScenario(s.label)
                if (s.label === 'Personalizado') {
                  // keep custom price
                } else if (s.factor) {
                  setCustomPrice('')
                }
              }}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all border ${
                s.isActive
                  ? 'bg-btc-orange/10 border-btc-orange/30 text-btc-orange'
                  : 'bg-surface border-surface-light text-gray-400 hover:text-gray-200 hover:border-surface-lighter'
              }`}
            >
              {s.label === 'Personalizado' ? '🎯 Personalizado' : s.label}
              {s.factor && currentPrice > 0 && (
                <span className="block text-[10px] opacity-60">
                  ${Math.round(currentPrice * s.factor).toLocaleString()}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Input personalizado */}
        {activeScenario === 'Personalizado' && (
          <div className="mb-4">
            <label className="label">Precio BTC objetivo (USD)</label>
            <input
              type="number"
              className="input-field"
              value={customPrice}
              onChange={(e) => setCustomPrice(e.target.value)}
              placeholder="Ej: 250000"
              min="0"
            />
          </div>
        )}

        {/* Gráfico comparativo */}
        {currentPrice > 0 && scenarios.filter(s => s.result && s.price > 0).length > 0 && (
          <div className="mb-6">
            <div className="h-[220px] md:h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={scenarios.filter(s => s.result && s.price > 0).map(s => ({
                    name: s.label === 'Personalizado' ? 'Personalizado' : `${s.label} ($${Math.round(s.price / 1000)}k)`,
                    valor: s.result!.projectedValue,
                    ganancia: s.result!.difference,
                    fill: s.result!.difference >= 0 ? '#22c55e' : '#ef4444',
                  }))}
                  margin={{ top: 10, right: 10, left: 10, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                  <XAxis dataKey="name" stroke="#475569" fontSize={10} tick={{ fill: '#94a3b8' }} />
                  <YAxis
                    stroke="#475569"
                    fontSize={10}
                    tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                    tick={{ fill: '#94a3b8' }}
                  />
                  <Tooltip
                    contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#e2e8f0', fontSize: 12 }}
                    formatter={(value: number) => [`$${value.toLocaleString('en-US', { minimumFractionDigits: 0 })}`, 'Valor cartera']}
                  />
                  <ReferenceLine y={currentValue} stroke="#f7931a" strokeDasharray="4 4" strokeWidth={1} label={{ value: 'Hoy', position: 'insideTopLeft', fill: '#f7931a', fontSize: 10 }} />
                  {invested > 0 && (
                    <ReferenceLine y={invested} stroke="#64748b" strokeDasharray="2 2" strokeWidth={1} label={{ value: 'Invertido', position: 'insideTopRight', fill: '#94a3b8', fontSize: 10 }} />
                  )}
                  <Bar dataKey="valor" radius={[4, 4, 0, 0]} maxBarSize={60}>
                    {scenarios.filter(s => s.result && s.price > 0).map((s, i) => (
                      <Cell key={i} fill={s.result!.difference >= 0 ? '#22c55e' : '#ef4444'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="text-[10px] text-gray-600 mt-2 text-center">
              Línea naranja = valor actual · Línea gris = capital invertido · Verde = ganancia · Rojo = pérdida
            </p>
          </div>
        )}

        {/* Resultados de cada escenario */}
        <div className="space-y-3">
          {scenarios
            .filter(s => s.result && s.price > 0)
            .map(s => (
              <div
                key={s.label}
                className={`p-4 rounded-lg border transition-all ${
                  s.isActive
                    ? 'bg-surface-light/50 border-btc-orange/30'
                    : 'bg-surface-light/20 border-transparent'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-gray-200">
                    {s.label === 'Personalizado' ? '🎯 Personalizado' : s.label}
                  </span>
                  <span className="text-xs text-gray-500 font-mono">
                    BTC a ${s.price.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <p className="text-[10px] text-gray-600 mb-0.5">Valor cartera</p>
                    <p className="text-sm font-bold font-mono text-gray-100">
                      ${s.result!.projectedValue.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] text-gray-600 mb-0.5">Ganancia</p>
                    <p className={`text-sm font-bold font-mono ${s.result!.difference >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {s.result!.difference >= 0 ? '+' : ''}${Math.abs(s.result!.difference).toLocaleString('en-US', { maximumFractionDigits: 0 })}
                    </p>
                    <p className={`text-[10px] ${s.result!.pctChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      ({s.result!.pctChange >= 0 ? '+' : ''}{s.result!.pctChange.toFixed(1)}%)
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] text-gray-600 mb-0.5">vs Invertido</p>
                    <p className={`text-sm font-bold font-mono ${s.result!.vsInvested >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {s.result!.vsInvested >= 0 ? '+' : ''}${Math.abs(s.result!.vsInvested).toLocaleString('en-US', { maximumFractionDigits: 0 })}
                    </p>
                    <p className={`text-[10px] ${s.result!.vsInvestedPct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      ({s.result!.vsInvestedPct >= 0 ? '+' : ''}{s.result!.vsInvestedPct.toFixed(1)}%)
                    </p>
                  </div>
                </div>

                {/* Sugerencia de acción */}
                {s.result!.suggestion && s.label !== 'Actual' && (
                  <div className={`mt-3 pt-3 border-t border-surface-light flex items-center gap-3 ${
                    s.result!.isBullish ? 'text-green-400/80' : 'text-red-400/80'
                  }`}>
                    <div className="flex items-start gap-2 flex-1 min-w-0">
                      {s.result!.isBullish ? <TrendingUp className="w-4 h-4 shrink-0 mt-0.5" /> : <TrendingDown className="w-4 h-4 shrink-0 mt-0.5" />}
                      <p className="text-xs leading-relaxed">{s.result!.suggestion}</p>
                    </div>
                    <button
                      onClick={() => {
                        if (s.result!.isBullish) {
                          navigate('/operations', { state: { tipo: 'buy', activo: 'BTC', precio: currentPrice, usdcAmount: usdcBalance } })
                        } else {
                          navigate('/operations', { state: { tipo: 'sell', activo: 'BTC', precio: currentPrice, cantidad: btcBalance } })
                        }
                      }}
                      className="btn-primary text-xs py-1.5 px-3 shrink-0"
                    >
                      {s.result!.isBullish ? 'Comprar BTC' : 'Vender BTC'}
                    </button>
                  </div>
                )}
              </div>
            ))}
        </div>

        {currentPrice <= 0 && (
          <p className="text-sm text-gray-500 text-center py-4">
            Esperando precio BTC para calcular escenarios…
          </p>
        )}
      </div>
    </div>
  )
}

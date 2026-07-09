import { useState, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { operations as opsApi, prices as pricesApi, portfolio as portfolioApi } from '../api/client'
import { Bitcoin, DollarSign, Plus, Minus, ArrowDownToLine, ArrowUpFromLine, Percent, Wallet } from 'lucide-react'
import { useToast } from '../components/Toast'
import { SkeletonCard } from '../components/Skeleton'

const TYPES = [
  { value: 'buy', label: 'Comprar', icon: Plus, color: 'text-green-400' },
  { value: 'sell', label: 'Vender', icon: Minus, color: 'text-red-400' },
  { value: 'deposit', label: 'Depositar', icon: ArrowDownToLine, color: 'text-blue-400' },
  { value: 'withdraw', label: 'Retirar', icon: ArrowUpFromLine, color: 'text-yellow-400' },
]

const ASSETS = ['BTC', 'USDC', 'EUR']

const WITHDRAW_PCTS = [100, 50, 25]

export default function Operations() {
  const location = useLocation()
  const [tipo, setTipo] = useState('buy')
  const [activo, setActivo] = useState('BTC')
  const [cantidad, setCantidad] = useState('')
  const [precio, setPrecio] = useState('')
  const [comision, setComision] = useState('0')
  const [comisionPct, setComisionPct] = useState('')
  const [comisionMode, setComisionMode] = useState<'fixed' | 'pct'>('fixed')
  const [usdcAmount, setUsdcAmount] = useState('')
  const [notes, setNotes] = useState('')
  const { toast } = useToast()
  const queryClient = useQueryClient()

  // Obtener precio BTC y balances
  const { data: btcPrice } = useQuery({
    queryKey: ['btcPrice'],
    queryFn: pricesApi.btc,
    refetchInterval: 30000,
  })

  const { data: balances } = useQuery({
    queryKey: ['balances'],
    queryFn: portfolioApi.balances,
    refetchInterval: 15000,
  })

  const btcPriceUsd = btcPrice?.price_usd || 0

  // Pre-fill form from simulator navigation
  useEffect(() => {
    const state = location.state as any
    if (!state?.tipo) return
    if (state.tipo) setTipo(state.tipo)
    if (state.activo) setActivo(state.activo)
    if (state.precio) setPrecio(String(state.precio))
    if (state.cantidad) setCantidad(state.cantidad.toFixed ? state.cantidad.toFixed(8) : String(state.cantidad))
    if (state.usdcAmount) setUsdcAmount(String(state.usdcAmount))
    window.history.replaceState({}, '')
  }, [location.key])

  // Auto-precio para compra BTC
  useEffect(() => {
    if (tipo === 'buy' && activo === 'BTC' && !precio && btcPriceUsd) {
      setPrecio(String(btcPriceUsd))
    }
  }, [tipo, activo, btcPriceUsd])

  // Auto-calcular: si cambia cantidad y precio, mostrar total
  const cantidadNum = parseFloat(cantidad) || 0
  const precioNum = parseFloat(precio) || 0
  const totalUsd = cantidadNum * precioNum

  // Si el usuario pone un monto en USDC, calcular BTC equivalente
  const usdcAmountNum = parseFloat(usdcAmount) || 0
  useEffect(() => {
    if (usdcAmountNum > 0 && precioNum > 0 && activo === 'BTC' && tipo === 'buy') {
      const btcQty = (usdcAmountNum / precioNum).toFixed(8)
      if (btcQty !== cantidad) {
        setCantidad(btcQty)
      }
    }
  }, [usdcAmountNum, precioNum, activo, tipo])

  // Si cambia cantidad en compra BTC, calcular USDC equivalente (solo si no hay monto USDC activo)
  useEffect(() => {
    if (cantidadNum > 0 && precioNum > 0 && activo === 'BTC' && tipo === 'buy' && usdcAmount === '') {
      setUsdcAmount(String(totalUsd))
    }
  }, [cantidadNum, precioNum, activo, tipo])

  // Calcular comisión final
  const calcularComision = () => {
    if (comisionMode === 'pct') {
      const pct = parseFloat(comisionPct) || 0
      return (pct / 100) * totalUsd
    }
    return parseFloat(comision) || 0
  }

  const mutation = useMutation({
    mutationFn: (data: any) => {
      if (data.tipo === 'deposit') return opsApi.deposit(data)
      if (data.tipo === 'withdraw') return opsApi.withdraw(data)
      return data.tipo === 'buy' ? opsApi.buy(data) : opsApi.sell(data)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      queryClient.invalidateQueries({ queryKey: ['operations'] })
      queryClient.invalidateQueries({ queryKey: ['balances'] })
      toast('success', 'Operación registrada exitosamente')
      setCantidad('')
      setPrecio(tipo === 'buy' && activo === 'BTC' && btcPriceUsd > 0 ? String(btcPriceUsd) : '')
      setComision('0')
      setComisionPct('')
      setUsdcAmount('')
      setNotes('')
    },
    onError: (err: any) => {
      toast('error', err.response?.data?.detail || 'Error al registrar operación')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    const comisionFinal = calcularComision()
    // Para depósitos/retiros: USDC/EUR = 1 USD, BTC usa el precio de mercado
    const precioEnvio = (tipo === 'deposit' || tipo === 'withdraw')
      ? (activo === 'BTC' && btcPriceUsd > 0 ? btcPriceUsd : 1)
      : (precioNum || 1)
    const payload: any = {
      tipo,
      activo,
      cantidad: cantidadNum,
      precio: precioEnvio,
      comision: comisionFinal,
      notes: notes || "",
    }

    mutation.mutate(payload)
  }

  // Balance disponible para el activo seleccionado
  const balanceDisponible = activo === 'BTC'
    ? (balances?.btc ?? 0)
    : activo === 'USDC'
    ? (balances?.usdc ?? 0)
    : (balances?.eur ?? 0)

  return (
    <div className="max-w-lg mx-auto">
      <h1 className="text-2xl font-bold text-gray-100 mb-6">📝 Nueva Operación</h1>

      <div className="card">
        {/* Balance disponible */}
        {balances && (tipo === 'sell' || tipo === 'withdraw') && (
          <div className="flex items-center gap-2 text-sm text-gray-500 mb-4 p-2 bg-surface-light/30 rounded-lg">
            <Wallet className="w-4 h-4 text-btc-orange" />
            <span>Disponible: <strong className="text-gray-200 font-mono">
              {activo === 'BTC' ? balanceDisponible.toFixed(8) : balanceDisponible.toFixed(2)} {activo}
            </strong></span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Type selector */}
          <div className="grid grid-cols-2 gap-2">
            {TYPES.map((t) => {
              const Icon = t.icon
              const isSelected = tipo === t.value
              return (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => setTipo(t.value)}
                  className={`flex items-center gap-2 px-4 py-3 rounded-lg text-sm font-medium transition-all border ${
                    isSelected
                      ? 'bg-btc-orange/10 border-btc-orange/30 text-btc-orange'
                      : 'bg-surface border-surface-light text-gray-500 hover:text-gray-300 hover:border-surface-lighter'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${t.color}`} />
                  {t.label}
                </button>
              )
            })}
          </div>

          {/* Asset selector */}
          <div>
            <label className="label">Activo</label>
            <div className="flex gap-2">
              {ASSETS.map((a) => (
                <button
                  key={a}
                  type="button"
                  onClick={() => setActivo(a)}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all border ${
                    activo === a
                      ? 'bg-btc-orange/10 border-btc-orange/30 text-btc-orange'
                      : 'bg-surface border-surface-light text-gray-500 hover:text-gray-300'
                  }`}
                >
                  {a === 'BTC' ? '₿' : '$'} {a}
                </button>
              ))}
            </div>
          </div>

          {/* Para compra BTC: opción de ingresar monto en USDC */}
          {tipo === 'buy' && activo === 'BTC' && (
            <div>
              <label className="label">O gastar en USDC</label>
              <div className="flex gap-2 flex-col sm:flex-row">
                <div className="flex gap-2 flex-1">
                  <input
                    type="number" step="any"
                    className="input-field flex-1"
                    value={usdcAmount}
                    onChange={(e) => setUsdcAmount(e.target.value)}
                    placeholder="Ej: 500"
                    min="0"
                  />
                  <span className="flex items-center text-sm text-gray-500">USDC</span>
                </div>
              </div>
              {usdcAmountNum > 0 && precioNum > 0 && (
                <p className="text-xs text-gray-600 mt-1 truncate">
                  ≈ {(usdcAmountNum / precioNum).toFixed(8)} BTC
                </p>
              )}
            </div>
          )}

          {/* Cantidad */}
          <div>
            <label className="label">Cantidad</label>
            <div className="flex gap-2 flex-col sm:flex-row">
              <input
                type="number" step="any"
                className="input-field flex-1"
                value={cantidad}
                onChange={(e) => setCantidad(e.target.value)}
                placeholder="0.00"
                required
                min="0"
              />
              {/* Quick withdraw buttons */}
              {(tipo === 'withdraw' || tipo === 'sell') && balanceDisponible > 0 && (
                <div className="flex gap-1 shrink-0">
                  {WITHDRAW_PCTS.map((pct) => {
                    const amount = (balanceDisponible * pct) / 100
                    return (
                      <button
                        key={pct}
                        type="button"
                        onClick={() => setCantidad(activo === 'BTC' ? amount.toFixed(8) : amount.toFixed(2))}
                        className="px-2 py-1 text-xs font-medium rounded bg-surface-light text-gray-400 hover:text-gray-200 hover:bg-surface transition-colors"
                        title={`${pct}% = ${activo === 'BTC' ? amount.toFixed(8) : amount.toFixed(2)} ${activo}`}
                      >
                        {pct === 100 ? 'Max' : `${pct}%`}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
            {/* Mostrar total en USD para compra/venta BTC */}
            {tipo !== 'deposit' && tipo !== 'withdraw' && cantidadNum > 0 && precioNum > 0 && (
              <p className="text-xs text-gray-600 mt-1">
                Total: <span className="font-mono font-semibold text-gray-400">
                  ${totalUsd.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </span>
                {activo === 'BTC' && (
                  <> · Precio BTC: <span className="font-mono text-gray-400">${btcPriceUsd.toLocaleString()}</span></>
                )}
              </p>
            )}
          </div>

          {/* Precio (oculto para withdraw y deposit) */}
          {tipo !== 'withdraw' && tipo !== 'deposit' && (
            <div>
              <label className="label">{activo === 'BTC' ? 'Precio BTC (USD)' : 'Precio unitario (USD)'}</label>
              <div className="flex gap-2">
                <input
                  type="number" step="any"
                  className="input-field flex-1"
                  value={precio}
                  onChange={(e) => setPrecio(e.target.value)}
                  placeholder="1.00"
                  required
                  min="1"
                />
                {activo === 'BTC' && btcPriceUsd > 0 && (
                  <button
                    type="button"
                    onClick={() => setPrecio(String(btcPriceUsd))}
                    className="px-3 py-2 text-xs font-medium rounded bg-surface-light text-gray-400 hover:text-gray-200 hover:bg-surface transition-colors whitespace-nowrap"
                  >
                    Precio actual
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Comisión con toggle fijo / porcentaje */}
          {tipo !== 'deposit' && tipo !== 'withdraw' && (
            <div>
              <label className="label">Comisión</label>
              <div className="flex gap-2 mb-2">
                <button
                  type="button"
                  onClick={() => setComisionMode('fixed')}
                  className={`px-3 py-1 text-xs rounded-full font-medium transition-all ${
                    comisionMode === 'fixed'
                      ? 'bg-btc-orange/10 text-btc-orange border border-btc-orange/20'
                      : 'bg-surface-light text-gray-500 border border-transparent hover:text-gray-300'
                  }`}
                >
                  <DollarSign className="w-3 h-3 inline" /> Monto fijo
                </button>
                <button
                  type="button"
                  onClick={() => setComisionMode('pct')}
                  className={`px-3 py-1 text-xs rounded-full font-medium transition-all ${
                    comisionMode === 'pct'
                      ? 'bg-btc-orange/10 text-btc-orange border border-btc-orange/20'
                      : 'bg-surface-light text-gray-500 border border-transparent hover:text-gray-300'
                  }`}
                >
                  <Percent className="w-3 h-3 inline" /> Porcentaje
                </button>
              </div>

              {comisionMode === 'fixed' ? (
                <input
                  type="number" step="any"
                  className="input-field"
                  value={comision}
                  onChange={(e) => setComision(e.target.value)}
                  placeholder="0.00"
                  min="0"
                />
              ) : (
                <div className="flex gap-2 items-center">
                  <input
                    type="number" step="any"
                    className="input-field flex-1"
                    value={comisionPct}
                    onChange={(e) => setComisionPct(e.target.value)}
                    placeholder="0.1"
                    min="0"
                    max="100"
                  />
                  <span className="text-sm text-gray-500 font-mono">%</span>
                  {comisionPct && cantidadNum > 0 && precioNum > 0 && (
                    <span className="text-xs text-gray-600 font-mono">
                      = ${(calcularComision()).toFixed(2)}
                    </span>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Notas de trading */}
          {tipo !== 'deposit' && tipo !== 'withdraw' && (
            <div>
              <label className="label">Nota de trading (opcional)</label>
              <input
                type="text"
                className="input-field"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Ej: Comprado por ruptura de resistencia"
              />
            </div>
          )}

          {/* Resumen */}
          <div className="bg-surface-light/30 rounded-lg p-3 space-y-1 text-xs text-gray-500">
            <div className="flex justify-between">
              <span>Operación</span>
              <span className="text-gray-300 font-medium capitalize">{tipo} · {activo}</span>
            </div>
            <div className="flex justify-between">
              <span>Cantidad</span>
              <span className="text-gray-300 font-mono">{cantidadNum || '—'}</span>
            </div>
            {tipo === 'deposit' || tipo === 'withdraw' ? (
              <div className="flex justify-between pt-1 mt-1 border-t border-surface-light">
                <span className="font-medium">Importe</span>
                <span className="text-gray-200 font-mono font-semibold">
                  {activo === 'BTC' ? '₿' : '$'}{cantidadNum.toLocaleString('en-US', { minimumFractionDigits: activo === 'BTC' ? 8 : 2 })}
                </span>
              </div>
            ) : (
              <>
                <div className="flex justify-between">
                  <span>Precio</span>
                  <span className="text-gray-300 font-mono">{precioNum ? `$${precioNum.toFixed(2)}` : '—'}</span>
                </div>
                <div className="flex justify-between border-t border-surface-light pt-1 mt-1">
                  <span className="font-medium">Total</span>
                  <span className="text-gray-200 font-mono font-semibold">${totalUsd.toFixed(2)}</span>
                </div>
                {calcularComision() > 0 && (
                  <div className="flex justify-between">
                    <span>Comisión</span>
                    <span className="text-red-400 font-mono">-${calcularComision().toFixed(2)}</span>
                  </div>
                )}
              </>
            )}
          </div>

          <button type="submit" disabled={mutation.isPending} className="btn-primary w-full">
            {mutation.isPending ? 'Registrando…' : 'Registrar Operación'}
          </button>
        </form>
      </div>
    </div>
  )
}

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { alerts, prices } from '../api/client'
import { Bell, Plus, Trash2, AlertTriangle, TrendingUp, TrendingDown, DollarSign, Bitcoin } from 'lucide-react'
import { useToast } from '../components/Toast'
import { EmptyState } from '../components/EmptyState'

const ALERT_TYPES = [
  { value: 'price_above', label: 'Precio supera', icon: TrendingUp, color: 'text-green-400' },
  { value: 'price_below', label: 'Precio baja de', icon: TrendingDown, color: 'text-red-400' },
  { value: 'profit_target', label: 'Ganancia objetivo %', icon: DollarSign, color: 'text-blue-400' },
  { value: 'loss_limit', label: 'Límite de pérdida %', icon: AlertTriangle, color: 'text-yellow-400' },
]

export default function Alerts() {
  const [showForm, setShowForm] = useState(false)
  const [type, setType] = useState('price_above')
  const [targetValue, setTargetValue] = useState('')
  const [note, setNote] = useState('')
  const [asset, setAsset] = useState('BTC')
  const queryClient = useQueryClient()

  const { data: alertList, isLoading, isError, error: queryError } = useQuery({
    queryKey: ['alerts'],
    queryFn: alerts.list,
    refetchInterval: 30000,
  })

  const { toast } = useToast()

  const createMutation = useMutation({
    mutationFn: alerts.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
      setShowForm(false)
      setTargetValue('')
      setNote('')
      toast('success', '✅ Alerta creada')
    },
    onError: (err: any) => {
      toast('error', err?.response?.data?.detail || err?.message || 'Error al crear la alerta')
    },
  })

  const { data: btcPrice } = useQuery({
    queryKey: ['btcPrice'],
    queryFn: prices.btc,
    refetchInterval: 60000,
    enabled: showForm || (!!alertList && alertList.length > 0),
  })

  const deleteMutation = useMutation({
    mutationFn: alerts.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
      toast('info', 'Alerta eliminada')
    },
  })

  const toggleMutation = useMutation({
    mutationFn: alerts.toggle,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['alerts'] }),
  })

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate({
      alert_type: type,
      target_value: parseFloat(targetValue),
      asset,
      note,
    })
  }

  const typeIcon = (t: string) => {
    const found = ALERT_TYPES.find((at) => at.value === t)
    return found?.icon || Bell
  }

  const typeLabel = (t: string) => {
    const found = ALERT_TYPES.find((at) => at.value === t)
    return found?.label || t
  }

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
        <h1 className="text-2xl font-bold text-gray-100">🔔 Alertas</h1>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary flex items-center gap-2 w-full sm:w-auto">
          <Plus className="w-4 h-4" /> Nueva Alerta
        </button>
      </div>

      {/* Create Form */}
      {showForm && (
        <div className="card mb-6">
          <h2 className="text-lg font-semibold text-gray-200 mb-4">Nueva Alerta</h2>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="label">Tipo de alerta</label>
              <div className="grid grid-cols-2 gap-2">
                {ALERT_TYPES.map((t) => {
                  const Icon = t.icon
                  const isSelected = type === t.value
                  return (
                    <button
                      key={t.value}
                      type="button"
                      onClick={() => setType(t.value)}
                      className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all border ${
                        isSelected
                          ? 'bg-btc-orange/10 border-btc-orange/30 text-btc-orange'
                          : 'bg-surface border-surface-light text-gray-500 hover:text-gray-300'
                      }`}
                    >
                      <Icon className={`w-4 h-4 ${t.color}`} />
                      {t.label}
                    </button>
                  )
                })}
              </div>
            </div>

            <div>
              <label className="label">Activo</label>
              <div className="flex gap-2">
                {['BTC', 'USDC', 'USDT'].map((a) => (
                  <button
                    key={a}
                    type="button"
                    onClick={() => setAsset(a)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all border ${
                      asset === a
                        ? 'bg-btc-orange/10 border-btc-orange/30 text-btc-orange'
                        : 'bg-surface border-surface-light text-gray-500'
                    }`}
                  >
                    {a}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="label">
                {type === 'profit_target' || type === 'loss_limit' ? 'Valor objetivo (%)' : 'Precio objetivo (USD)'}
              </label>
              <div className="flex gap-2">
                <input
                  type="number"
                  step="any"
                  className="input-field flex-1"
                  value={targetValue}
                  onChange={(e) => setTargetValue(e.target.value)}
                  placeholder={type.includes('price') ? '50000' : '50'}
                  required
                  min="0"
                />
                {btcPrice?.price_usd && (type === 'price_above' || type === 'price_below') && (
                  <button
                    type="button"
                    onClick={() => setTargetValue(btcPrice.price_usd.toString())}
                    className="shrink-0 px-3 py-2 rounded-lg text-xs font-medium bg-btc-orange/10 border border-btc-orange/30 text-btc-orange hover:bg-btc-orange/20 transition-all"
                    title={`Usar precio actual: $${btcPrice.price_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}`}
                  >
                    Usar actual
                  </button>
                )}
              </div>
              {btcPrice?.price_usd && (
                <p className="text-xs text-gray-500 mt-1.5 flex flex-wrap items-center gap-x-1.5 gap-y-1">
                  <span className="flex items-center gap-1.5">
                    <Bitcoin className="w-3.5 h-3.5 text-btc-orange" />
                    Precio actual BTC:{' '}
                    <span className="text-gray-300 font-medium">${btcPrice.price_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
                  </span>
                  {btcPrice.change_24h != null && (
                    <span className={btcPrice.change_24h >= 0 ? 'text-green-400' : 'text-red-400'}>
                      ({btcPrice.change_24h >= 0 ? '+' : ''}{btcPrice.change_24h.toFixed(2)}%)
                    </span>
                  )}
                  {targetValue && !isNaN(parseFloat(targetValue)) && (type === 'profit_target' || type === 'loss_limit') && (
                    <span className="text-btc-orange font-medium">
                      → ≈ ${type === 'profit_target'
                        ? (btcPrice.price_usd * (1 + parseFloat(targetValue) / 100)).toLocaleString('en-US', { minimumFractionDigits: 2 })
                        : (btcPrice.price_usd * (1 - parseFloat(targetValue) / 100)).toLocaleString('en-US', { minimumFractionDigits: 2 })
                      } USD
                    </span>
                  )}
                </p>
              )}
            </div>

            <div>
              <label className="label">Nota (opcional)</label>
              <input
                type="text"
                className="input-field"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Ej: Vender cuando llegue a este precio"
              />
            </div>

            <div className="flex gap-3">
              <button type="submit" className="btn-primary flex-1" disabled={createMutation.isPending}>
                {createMutation.isPending ? 'Creando…' : 'Crear Alerta'}
              </button>
              <button type="button" onClick={() => setShowForm(false)} className="btn-secondary">
                Cancelar
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Alert List */}
      {isLoading ? (
        <div className="space-y-2">
          {[1,2,3].map(i => <div key={i} className="card py-4"><div className="animate-pulse bg-surface-light rounded h-16" /></div>)}
        </div>
      ) : isError ? (
        <div className="card text-center py-16 border-red-500/30">
          <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <p className="text-red-400 mb-2">Error al cargar alertas</p>
          <p className="text-sm text-gray-500">{(queryError as any)?.response?.data?.detail || (queryError as any)?.message || 'Ocurrió un error inesperado'}</p>
        </div>
      ) : !alertList || alertList.length === 0 ? (
        <EmptyState icon={Bell} title="No hay alertas configuradas" description="Creá una alerta para recibir notificaciones cuando el precio alcance tu objetivo." />
      ) : (
        <div className="space-y-3">
          {alertList.map((alert: any) => {
            const at = alert.alert_type ?? alert.type
            const Icon = typeIcon(at)
            const isPriceAlert = at === 'price_above' || at === 'price_below'
            return (
              <div key={alert.id} className={`card flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 py-4 px-3 sm:px-5 border-l-4 ${
                alert.triggered ? 'border-l-green-500' : alert.active ? 'border-l-btc-orange' : 'border-l-gray-600'
              }`}>
                <div className="flex items-start gap-3 sm:gap-4 min-w-0">
                  <Icon className={`w-5 h-5 shrink-0 mt-0.5 ${alert.triggered ? 'text-green-400' : alert.active ? 'text-btc-orange' : 'text-gray-600'}`} />
                  <div className="min-w-0">
                    <p className="font-semibold text-gray-200 text-sm sm:text-base">
                      {typeLabel(alert.alert_type ?? alert.type)}
                      <span className="text-btc-orange ml-2">${alert.target_value?.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
                    </p>
                    <p className="text-xs text-gray-500 truncate">
                      {alert.asset} · Creada: {new Date(alert.created_at).toLocaleDateString()}
                      {alert.note && ` · ${alert.note}`}
                    </p>
                    {btcPrice?.price_usd && isPriceAlert && (
                      <p className="text-xs text-gray-500 mt-0.5">
                        <Bitcoin className="w-3 h-3 text-btc-orange inline mr-1" />
                        Actual: ${btcPrice.price_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                        {' · '}
                        {at === 'price_above' ? (
                          btcPrice.price_usd >= alert.target_value ? (
                            <span className="text-green-400">✓ Superado</span>
                          ) : (
                            <span className="text-gray-400">
                              Falta {((alert.target_value - btcPrice.price_usd) / btcPrice.price_usd * 100).toFixed(1)}%
                            </span>
                          )
                        ) : (
                          btcPrice.price_usd <= alert.target_value ? (
                            <span className="text-green-400">✓ Alcanzado</span>
                          ) : (
                            <span className="text-gray-400">
                              A {((btcPrice.price_usd - alert.target_value) / btcPrice.price_usd * 100).toFixed(1)}% por encima
                            </span>
                          )
                        )}
                      </p>
                    )}
                    {alert.triggered && (
                      <p className="text-xs text-green-400 mt-1">✅ Activada {alert.triggered_at ? new Date(alert.triggered_at).toLocaleString() : ''}</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2 self-end sm:self-auto">
                  <span className={`text-xs px-2 py-1 rounded-full whitespace-nowrap ${
                    alert.active ? 'bg-green-500/10 text-green-400' : 'bg-gray-500/10 text-gray-500'
                  }`}>
                    {alert.active ? 'Activa' : 'Inactiva'}
                  </span>
                  <button
                    onClick={() => deleteMutation.mutate(alert.id)}
                    className="p-2 text-gray-600 hover:text-red-400 transition-colors"
                    title="Eliminar"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

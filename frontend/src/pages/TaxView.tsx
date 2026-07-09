import { useQuery } from '@tanstack/react-query'
import { operations as opsApi, prices as pricesApi } from '../api/client'
import { DollarSign, Calendar } from 'lucide-react'

const CURRENT_YEAR = new Date().getFullYear()

export default function TaxView() {
  const { data: ops, isLoading } = useQuery({
    queryKey: ['operations'],
    queryFn: () => opsApi.list(500),
    refetchInterval: 120000,
  })

  const { data: btcPrice } = useQuery({
    queryKey: ['btcPrice'],
    queryFn: pricesApi.btc,
    refetchInterval: 120000,
  })

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="card"><div className="animate-pulse bg-surface-light rounded h-24" /></div>
        ))}
      </div>
    )
  }

  if (!ops || ops.length === 0) {
    return (
      <div className="card text-center py-16">
        <Calendar className="w-12 h-12 text-gray-600 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-gray-200 mb-2">Sin operaciones</h2>
        <p className="text-gray-500">Registrá operaciones para ver el resumen fiscal.</p>
      </div>
    )
  }

  // Calcular P&L fiscal por año (FIFO simplificado)
  const currentBtcPrice = btcPrice?.price_usd || 0
  const byYear: Record<number, { buys: any[]; sells: any[]; totalCost: number; totalProceeds: number; realizedPnl: number }> = {}

  for (const op of ops) {
    const year = new Date(op.fecha).getFullYear()
    if (!byYear[year]) byYear[year] = { buys: [], sells: [], totalCost: 0, totalProceeds: 0, realizedPnl: 0 }

    if (op.tipo === 'buy') {
      byYear[year].buys.push(op)
      byYear[year].totalCost += op.cantidad * op.precio
    } else if (op.tipo === 'sell') {
      byYear[year].sells.push(op)
      byYear[year].totalProceeds += op.cantidad * op.precio
    }
  }

  // Calcular P&L realizado simplificado (solo compras/ventas, no depósitos/retiros)
  for (const year of Object.keys(byYear)) {
    const y = byYear[Number(year)]
    y.realizedPnl = y.totalProceeds - y.totalCost
  }

  const years = Object.keys(byYear).map(Number).sort((a, b) => b - a)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
          <DollarSign className="w-6 h-6 text-green-400" />
          Resumen Fiscal
        </h1>
        <span className="text-xs text-gray-500">
          BTC actual: ${currentBtcPrice.toLocaleString('en-US', { minimumFractionDigits: 2 })}
        </span>
      </div>

      <div className="bg-yellow-500/5 border border-yellow-500/10 rounded-lg p-4">
        <p className="text-xs text-yellow-400/80">
          ⚠️ Este es un cálculo FIFO simplificado con fines informativos. No constituye asesoramiento fiscal.
          Consultá con un contador para tu declaración de impuestos.
        </p>
      </div>

      {years.map((year) => {
        const y = byYear[year]
        const isCurrentYear = year === CURRENT_YEAR
        return (
          <div key={year} className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-200 flex items-center gap-2">
                <Calendar className="w-5 h-5 text-btc-orange" />
                {year} {isCurrentYear && <span className="text-xs text-gray-500 font-normal">(en curso)</span>}
              </h2>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-xs text-gray-500 mb-1">Compras</p>
                <p className="text-lg font-bold font-mono text-gray-100">
                  ${y.totalCost.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">Ventas</p>
                <p className="text-lg font-bold font-mono text-gray-100">
                  ${y.totalProceeds.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">P&L Realizado</p>
                <p className={`text-lg font-bold font-mono ${y.realizedPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {y.realizedPnl >= 0 ? '+' : ''}${y.realizedPnl.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">Operaciones</p>
                <p className="text-lg font-bold font-mono text-gray-100">
                  {y.buys.length + y.sells.length}
                </p>
              </div>
            </div>
          </div>
        )
      })}

      {years.length === 0 && (
        <div className="card text-center py-12">
          <p className="text-gray-500">No hay datos fiscales para mostrar.</p>
        </div>
      )}
    </div>
  )
}

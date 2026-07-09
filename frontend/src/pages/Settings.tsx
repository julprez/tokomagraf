import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { auth, exchanges } from '../api/client'
import { Settings as SettingsIcon, User, Key, Plus, Trash2, ExternalLink, Save, Edit3, Wallet, Shield, Check, Palette } from 'lucide-react'

export default function Settings() {
  // ── Profile State ──
  const [name, setName] = useState('')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [profileMsg, setProfileMsg] = useState('')
  const queryClient = useQueryClient()

  // ── Exchanges State ──
  const [showExchangeForm, setShowExchangeForm] = useState(false)
  const [exName, setExName] = useState('')
  const [exKey, setExKey] = useState('')
  const [exSecret, setExSecret] = useState('')
  const [exchangeMsg, setExchangeMsg] = useState('')

  // ── Profile ──
  const { data: user } = useQuery({
    queryKey: ['me'],
    queryFn: auth.me,
  })

  // Inicializar name con el nombre actual del usuario
  useEffect(() => {
    if (user) setName(user.name || '')
  }, [user])

  const isSeedUser = !user?.email

  const profileMutation = useMutation({
    mutationFn: auth.updateProfile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['me'] })
      setProfileMsg('✅ Nombre actualizado')
      setTimeout(() => setProfileMsg(''), 3000)
    },
    onError: (err: any) => {
      setProfileMsg(`❌ ${err.response?.data?.detail || 'Error al actualizar'}`)
    },
  })

  // ── Exchanges ──
  const { data: exchangeList, isLoading: exLoading } = useQuery({
    queryKey: ['exchanges'],
    queryFn: exchanges.list,
  })

  const createExchangeMutation = useMutation({
    mutationFn: exchanges.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exchanges'] })
      setShowExchangeForm(false)
      setExName('')
      setExKey('')
      setExSecret('')
      setExchangeMsg('✅ API Key agregada')
      setTimeout(() => setExchangeMsg(''), 3000)
    },
    onError: (err: any) => {
      setExchangeMsg(`❌ ${err.response?.data?.detail || 'Error al agregar API Key'}`)
    },
  })

  const deleteExchangeMutation = useMutation({
    mutationFn: exchanges.delete,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['exchanges'] }),
  })

  const handleProfileUpdate = (e: React.FormEvent) => {
    e.preventDefault()
    const data: any = {}
    if (name) data.name = name
    if (currentPassword && newPassword) {
      data.current_password = currentPassword
      data.new_password = newPassword
    }
    if (Object.keys(data).length > 0) {
      profileMutation.mutate(data)
    }
  }

  const handleAddExchange = (e: React.FormEvent) => {
    e.preventDefault()
    createExchangeMutation.mutate({
      name: exName,
      api_key: exKey,
      api_secret: exSecret,
    })
  }

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <h1 className="text-2xl font-bold text-gray-100">⚙️ Configuración</h1>

      {/* Profile Section */}
      <div className="card">
        <div className="flex items-center gap-3 mb-6">
          <User className="w-5 h-5 text-btc-orange" />
          <h2 className="text-lg font-semibold text-gray-200">Perfil</h2>
        </div>

        {user && (
          <div className="mb-4 p-3 bg-surface-light rounded-lg text-sm space-y-1">
            {isSeedUser ? (
              <>
                <div className="flex items-center gap-2 text-gray-400">
                  <Wallet className="w-4 h-4 text-btc-orange" />
                  <span>Wallet con seed phrase</span>
                  <span className="bg-green-500/10 text-green-400 text-xs px-2 py-0.5 rounded-full">● Segura</span>
                </div>
                <p className="text-gray-600 text-xs">Miembro desde {new Date(user.created_at).toLocaleDateString()}</p>
              </>
            ) : (
              <>
                <div className="flex items-center gap-2 text-gray-400">
                  <User className="w-4 h-4 text-gray-500" />
                  <span>Email: <span className="text-gray-200">{user.email}</span></span>
                </div>
                <p className="text-gray-600 text-xs">Miembro desde {new Date(user.created_at).toLocaleDateString()}</p>
              </>
            )}
          </div>
        )}

        {profileMsg && (
          <div className={`px-4 py-3 rounded-lg mb-4 text-sm ${profileMsg.startsWith('✅') ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
            {profileMsg}
          </div>
        )}

        <form onSubmit={handleProfileUpdate} className="space-y-4">
          <div>
            <label className="label">Nombre de la wallet</label>
            <div className="flex gap-2">
              <input
                type="text"
                className="input-field flex-1"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Mi Wallet"
              />
              <button
                type="submit"
                className="btn-primary flex items-center gap-2 px-4"
                disabled={profileMutation.isPending || !name || name === user?.name}
              >
                <Edit3 className="w-4 h-4" />
                {profileMutation.isPending ? '…' : 'Renombrar'}
              </button>
            </div>
            {name !== user?.name && user && (
              <p className="text-xs text-gray-600 mt-1">
                Nombre actual: <span className="text-gray-400">{user.name}</span>
              </p>
            )}
          </div>

          {!isSeedUser && (
            <div className="border-t border-surface-light pt-4">
              <p className="text-sm text-gray-500 mb-3">Cambiar contraseña (opcional)</p>
              <div className="space-y-3">
                <div>
                  <label className="label">Contraseña actual</label>
                  <input type="password" className="input-field" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} placeholder="••••••••" />
                </div>
                <div>
                  <label className="label">Nueva contraseña</label>
                  <input type="password" className="input-field" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="Mínimo 6 caracteres" minLength={6} />
                </div>
              </div>
            </div>
          )}
        </form>
      </div>

      {/* API Keys Section */}
      <div className="card">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Key className="w-5 h-5 text-btc-orange" />
            <h2 className="text-lg font-semibold text-gray-200">API Keys de Exchanges</h2>
          </div>
          <button onClick={() => setShowExchangeForm(!showExchangeForm)} className="btn-primary flex items-center gap-2 text-sm py-1.5 px-3">
            <Plus className="w-4 h-4" /> Agregar
          </button>
        </div>

        <p className="text-sm text-gray-500 mb-4">
          Conectá tus exchanges para sincronizar operaciones automáticamente. Las keys se almacenan cifradas.
        </p>

        {exchangeMsg && (
          <div className={`px-4 py-3 rounded-lg mb-4 text-sm ${exchangeMsg.startsWith('✅') ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
            {exchangeMsg}
          </div>
        )}

        {/* Add Exchange Form */}
        {showExchangeForm && (
          <form onSubmit={handleAddExchange} className="bg-surface-light rounded-lg p-4 mb-4 space-y-3">
            <div>
              <label className="label">Exchange</label>
              <select className="input-field" value={exName} onChange={(e) => setExName(e.target.value)} required>
                <option value="">Seleccionar…</option>
                <option value="binance">Binance</option>
                <option value="pionex">Pionex</option>
                <option value="kraken">Kraken</option>
                <option value="coinbase">Coinbase</option>
                <option value="other">Otro</option>
              </select>
            </div>
            <div>
              <label className="label">API Key</label>
              <input type="text" className="input-field" value={exKey} onChange={(e) => setExKey(e.target.value)} placeholder="••••••••" required />
            </div>
            <div>
              <label className="label">API Secret</label>
              <input type="password" className="input-field" value={exSecret} onChange={(e) => setExSecret(e.target.value)} placeholder="••••••••" required />
            </div>
            <div className="flex gap-3">
              <button type="submit" className="btn-primary flex-1" disabled={createExchangeMutation.isPending}>
                {createExchangeMutation.isPending ? 'Conectando…' : 'Conectar'}
              </button>
              <button type="button" onClick={() => setShowExchangeForm(false)} className="btn-secondary">Cancelar</button>
            </div>
          </form>
        )}

        {/* Exchange List */}
        {exLoading ? (
          <div className="text-center text-gray-500 py-8 animate-pulse">Cargando exchanges…</div>
        ) : !exchangeList || exchangeList.length === 0 ? (
          <div className="text-center py-8">
            <ExternalLink className="w-8 h-8 text-gray-600 mx-auto mb-2" />
            <p className="text-gray-500 text-sm">No hay exchanges conectados.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {exchangeList.map((ex: any) => (
              <div key={ex.id} className="flex items-center justify-between bg-surface-light rounded-lg px-4 py-3">
                <div>
                  <p className="font-medium text-gray-200 capitalize">{ex.name}</p>
                  <p className="text-xs text-gray-500 font-mono">{ex.api_key}</p>
                </div>
                <button
                  onClick={() => deleteExchangeMutation.mutate(ex.id)}
                  className="p-2 text-gray-600 hover:text-red-400 transition-colors"
                  title="Eliminar"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Chart Customization */}
      <div className="card">
        <div className="flex items-center gap-3 mb-6">
          <Palette className="w-5 h-5 text-btc-orange" />
          <h2 className="text-lg font-semibold text-gray-200">Personalización del gráfico</h2>
        </div>
        <ChartOpacitySetting />
      </div>
    </div>
  )
}

function ChartOpacitySetting() {
  const [opacity, setOpacity] = useState(() => {
    const saved = localStorage.getItem('chartZoneOpacity')
    return saved ? parseFloat(saved) : 6
  })

  useEffect(() => {
    localStorage.setItem('chartZoneOpacity', opacity.toString())
  }, [opacity])

  const actualOpacity = opacity / 100

  return (
    <div className="space-y-3">
      <div>
        <label className="label">Opacidad zonas ganancia/pérdida</label>
        <p className="text-xs text-gray-500 mb-2">Ajustá la visibilidad de las áreas verde y roja en el gráfico del portfolio.</p>
        <div className="flex items-center gap-4">
          <input
            type="range"
            min="1"
            max="20"
            step="1"
            value={opacity}
            onChange={(e) => setOpacity(parseInt(e.target.value))}
            className="flex-1 accent-btc-orange"
          />
          <span className="text-sm text-gray-400 font-mono w-12 text-right">{opacity}%</span>
        </div>
      </div>
      <div className="flex gap-4 text-xs">
        <div className="flex items-center gap-1.5">
          <div className="w-4 h-4 rounded" style={{ background: `rgba(74, 222, 128, ${actualOpacity})` }} />
          <span className="text-gray-500">Ganancia</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-4 h-4 rounded" style={{ background: `rgba(248, 113, 113, ${actualOpacity})` }} />
          <span className="text-gray-500">Pérdida</span>
        </div>
      </div>
    </div>
  )
}

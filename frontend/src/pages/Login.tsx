import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { auth } from '../api/client'
import { Bitcoin, Copy, Check, Eye, EyeOff, Shield, AlertTriangle } from 'lucide-react'

type Mode = 'choose' | 'create' | 'restore' | 'saved' | 'login'

export default function Login() {
  const [mode, setMode] = useState<Mode>('choose')
  const [seedWords, setSeedWords] = useState<string[]>([])
  const [inputWords, setInputWords] = useState<string[]>(Array(6).fill(''))
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)
  const [showWords, setShowWords] = useState(false)
  const copyRef = useRef<HTMLTextAreaElement>(null)
  const navigate = useNavigate()

  // ── Generar nueva seed phrase ──
  const handleCreate = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await auth.generateSeed()
      setSeedWords(data.words)
      localStorage.setItem('token', data.access_token)
      setMode('saved')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al generar cuenta')
    } finally {
      setLoading(false)
    }
  }

  // ── Iniciar sesión con seed phrase ──
  const handleLogin = async () => {
    const words = inputWords.map((w) => w.trim().toLowerCase())
    if (words.some((w) => !w)) {
      setError('Completá las 6 palabras')
      return
    }
    setLoading(true)
    setError('')
    try {
      const data = await auth.loginSeed({ words })
      localStorage.setItem('token', data.access_token)
      navigate('/dashboard')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Seed phrase inválida')
    } finally {
      setLoading(false)
    }
  }

  // ── Copiar seed phrase (fallback para HTTP sin SSL) ──
  const handleCopy = () => {
    const text = seedWords.join(' ')
    // Intentar con Clipboard API (HTTPS/localhost)
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      }).catch(() => fallbackCopy(text))
    } else {
      fallbackCopy(text)
    }
  }

  const fallbackCopy = (text: string) => {
    try {
      const ta = copyRef.current
      if (!ta) return
      ta.value = text
      ta.select()
      ta.setSelectionRange(0, text.length)
      const ok = document.execCommand('copy')
      if (!ok) throw new Error('execCommand returned false')
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setError('No se pudo copiar. Seleccioná las palabras manualmente.')
    }
  }

  // ── Continuar despuès de guardar ──
  const handleContinue = () => {
    navigate('/dashboard')
  }

  // ── Render ──
  return (
    <div className="min-h-screen bg-[#0b1121] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-gradient-to-br from-btc-orange to-btc-dark rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-xl shadow-btc-orange/20">
            <Bitcoin className="w-10 h-10 text-[#0f172a]" />
          </div>
          <h1 className="text-3xl font-bold text-gray-100">tokomagraf</h1>
          <p className="text-gray-500 mt-1">Gestor de Cartera Cripto</p>
        </div>

        {/* ── CHOOSE MODE ── */}
        {mode === 'choose' && (
          <div className="card space-y-4">
            <h2 className="text-xl font-semibold text-gray-200 text-center">Acceder a tu cartera</h2>
            <p className="text-sm text-gray-500 text-center">
              Usá una seed phrase como llave de acceso, igual que en las wallets cripto.
            </p>

            <button onClick={() => setMode('create')} className="btn-primary w-full py-3">
              🆕 Crear nueva wallet
            </button>
            <button onClick={() => setMode('restore')} className="btn-secondary w-full py-3">
              🔑 Ya tengo una seed phrase
            </button>

            <div className="border-t border-surface-light pt-4 mt-2">
              <p className="text-xs text-gray-600 text-center">
                ¿Email y contraseña? Usá{' '}
                <button onClick={() => setMode('login')} className="text-btc-orange hover:underline">
                  inicio de sesión tradicional
                </button>
              </p>
            </div>
          </div>
        )}

        {/* ── LOGIN EMAIL MODE (original) ── */}
        {mode === 'login' && (
          <EmailLogin onBack={() => setMode('choose')} navigate={navigate} />
        )}

        {/* ── CREATE WALLET ── */}
        {mode === 'create' && !loading && seedWords.length === 0 && (
          <div className="card">
            <h2 className="text-xl font-semibold text-gray-200 mb-4">🆕 Crear nueva wallet</h2>
            <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-4 mb-6">
              <div className="flex items-start gap-3">
                <Shield className="w-5 h-5 text-yellow-400 mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-semibold text-yellow-400">Importante</p>
                  <p className="text-xs text-yellow-300/70 mt-1">
                    Tu seed phrase es la única forma de recuperar tu cuenta. Nadie en tokomagraf puede recuperarla por ti.
                    Escribila en papel y guardala en un lugar seguro.
                  </p>
                </div>
              </div>
            </div>
            <button onClick={handleCreate} disabled={loading} className="btn-primary w-full py-3">
              {loading ? 'Generando…' : '🎲 Generar seed phrase'}
            </button>
            <button onClick={() => setMode('choose')} className="btn-secondary w-full mt-3 py-2">
              Volver
            </button>
          </div>
        )}

        {mode === 'create' && loading && (
          <div className="card text-center py-12">
            <div className="animate-pulse space-y-3">
              <div className="h-4 bg-surface-light rounded w-3/4 mx-auto" />
              <div className="h-4 bg-surface-light rounded w-1/2 mx-auto" />
              <div className="h-4 bg-surface-light rounded w-2/3 mx-auto" />
            </div>
            <p className="text-gray-500 mt-4">Generando seed phrase segura…</p>
          </div>
        )}

        {/* ── SEED PHRASE SAVED ── */}
        {mode === 'saved' && seedWords.length > 0 && (
          <div className="card">
            <h2 className="text-xl font-semibold text-gray-200 mb-2">🔐 Tu seed phrase</h2>
            <p className="text-sm text-red-400 mb-4 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              <span>No la compartas con nadie. Es tu única llave de acceso.</span>
            </p>

            {/* Words display */}
            <div className="bg-surface-light rounded-xl p-5 mb-4">
              <div className="grid grid-cols-2 gap-3">
                {seedWords.map((word, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="text-xs text-gray-500 w-5 text-right">{i + 1}.</span>
                    <span className="font-mono font-bold text-lg text-btc-orange">{word}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Textarea oculto para fallback de copia */}
            <textarea
              ref={copyRef}
              readOnly
              className="fixed left-[-9999px] top-0 w-px h-px opacity-0"
              aria-hidden
            />

            {/* Actions */}
            <div className="flex gap-3">
              <button onClick={handleCopy} className="btn-secondary flex-1 flex items-center justify-center gap-2 py-3">
                {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
                {copied ? 'Copiado' : 'Copiar'}
              </button>
              <button onClick={handleContinue} className="btn-primary flex-1 py-3">
                ✅ Ya lo guardé
              </button>
            </div>
            <p className="text-xs text-gray-600 text-center mt-4">
              Vas a poder iniciar sesión con estas 6 palabras.
            </p>
          </div>
        )}

        {/* ── RESTORE / LOGIN WITH SEED ── */}
        {mode === 'restore' && (
          <div className="card">
            <h2 className="text-xl font-semibold text-gray-200 mb-2">🔑 Iniciar sesión</h2>
            <p className="text-sm text-gray-500 mb-4">Ingresá las 6 palabras de tu seed phrase en orden.</p>

            <div className="space-y-3 mb-4">
              {inputWords.map((word, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="text-xs text-gray-500 w-5 text-right shrink-0">{i + 1}.</span>
                  <input
                    type={showWords ? 'text' : 'password'}
                    className="input-field flex-1"
                    value={word}
                    onChange={(e) => {
                      const newWords = [...inputWords]
                      newWords[i] = e.target.value
                      setInputWords(newWords)
                    }}
                    placeholder={`Palabra ${i + 1}`}
                    autoComplete="off"
                  />
                </div>
              ))}
            </div>

            <button
              onClick={() => setShowWords(!showWords)}
              className="text-xs text-gray-500 hover:text-gray-300 flex items-center gap-1 mb-4"
            >
              {showWords ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
              {showWords ? 'Ocultar palabras' : 'Mostrar palabras'}
            </button>

            {error && (
              <p className="text-red-400 text-sm bg-red-500/10 px-3 py-2 rounded-lg mb-4">{error}</p>
            )}

            <button onClick={handleLogin} disabled={loading} className="btn-primary w-full py-3">
              {loading ? 'Verificando…' : '🔓 Acceder'}
            </button>

            <button onClick={() => { setMode('choose'); setError(''); setInputWords(Array(6).fill('')) }} className="btn-secondary w-full mt-3 py-2">
              Volver
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Traditional Email Login (kept from original) ──

function EmailLogin({ onBack, navigate }: { onBack: () => void; navigate: (path: string) => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [isRegister, setIsRegister] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const data = isRegister
        ? await auth.register({ name: email.split('@')[0], email, password })
        : await auth.login({ email, password })
      localStorage.setItem('token', data.access_token)
      navigate('/dashboard')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error de autenticación')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card">
      <h2 className="text-xl font-semibold text-gray-200 mb-6">
        {isRegister ? 'Crear Cuenta' : 'Iniciar Sesión'}
      </h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="label">Email</label>
          <input type="email" className="input-field" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email@ejemplo.com" required />
        </div>
        <div>
          <label className="label">Contraseña</label>
          <input type="password" className="input-field" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" required minLength={6} />
        </div>

        {error && <p className="text-red-400 text-sm bg-red-500/10 px-3 py-2 rounded-lg">{error}</p>}

        <button type="submit" className="btn-primary w-full" disabled={loading}>
          {loading ? 'Procesando…' : isRegister ? 'Crear Cuenta' : 'Iniciar Sesión'}
        </button>
      </form>

      <div className="mt-4 text-center space-y-2">
        <button onClick={() => { setIsRegister(!isRegister); setError('') }} className="text-sm text-gray-500 hover:text-btc-orange transition-colors block w-full">
          {isRegister ? '¿Ya tenés cuenta? Iniciá sesión' : '¿No tenés cuenta? Registrate'}
        </button>
        <button onClick={onBack} className="text-sm text-gray-600 hover:text-gray-400 transition-colors">
          ← Volver al inicio
        </button>
      </div>
    </div>
  )
}

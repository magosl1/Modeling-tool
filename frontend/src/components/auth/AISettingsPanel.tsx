import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { aiSettingsApi } from '../../services/api'
import type { AIProvider, AISettingsUpdate } from '../../types/api'
import toast from 'react-hot-toast'

const PROVIDER_OPTIONS: { value: AIProvider; label: string; hint: string }[] = [
  { value: 'google', label: 'Google AI Studio (Gemini)', hint: 'Get your key at aistudio.google.com' },
  { value: 'anthropic', label: 'Anthropic (Claude)', hint: 'Get your key at console.anthropic.com' },
  { value: 'openai', label: 'OpenAI', hint: 'Get your key at platform.openai.com' },
]

const DEFAULT_MODELS: Record<AIProvider, { cheap: string; smart: string }> = {
  google: { cheap: 'gemini-2.5-flash', smart: 'gemini-2.5-pro' },
  anthropic: { cheap: 'claude-sonnet-4-20250514', smart: 'claude-opus-4-20250514' },
  openai: { cheap: 'gpt-4o-mini', smart: 'gpt-4o' },
}

export default function AISettingsPanel() {
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data: existing, isLoading } = useQuery({
    queryKey: ['ai-settings'],
    queryFn: () => aiSettingsApi.get().then(r => r.data),
    retry: false,
  })

  const [provider, setProvider] = useState<AIProvider>('google')
  const [apiKey, setApiKey] = useState('')
  const [cheapModel, setCheapModel] = useState('gemini-2.5-flash')
  const [smartModel, setSmartModel] = useState('gemini-2.5-pro')
  const [showKey, setShowKey] = useState(false)

  useEffect(() => {
    if (existing) {
      setProvider(existing.provider as AIProvider)
      setCheapModel(existing.cheap_model)
      setSmartModel(existing.smart_model)
    }
  }, [existing])

  const handleProviderChange = (p: AIProvider) => {
    setProvider(p)
    const defaults = DEFAULT_MODELS[p]
    setCheapModel(defaults.cheap)
    setSmartModel(defaults.smart)
  }

  const saveMutation = useMutation({
    mutationFn: (data: AISettingsUpdate) => aiSettingsApi.save(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ai-settings'] })
      toast.success('AI settings saved')
      setApiKey('')
    },
    onError: () => toast.error('Failed to save settings'),
  })

  const deleteMutation = useMutation({
    mutationFn: () => aiSettingsApi.delete(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ai-settings'] })
      toast.success('AI settings removed')
    },
    onError: () => toast.error('Failed to delete settings'),
  })

  const testMutation = useMutation({
    mutationFn: () => aiSettingsApi.test(),
    onSuccess: (res) => {
      const r = res.data
      if (r.success) {
        toast.success(r.message, { duration: 5000 })
      } else {
        toast.error(r.message, { duration: 8000 })
      }
    },
    onError: () => toast.error('Failed to test connection'),
  })

  const handleSave = () => {
    if (!apiKey && !existing) {
      toast.error('Please enter your API key')
      return
    }
    saveMutation.mutate({
      provider,
      api_key: apiKey || '___UNCHANGED___',
      cheap_model: cheapModel,
      smart_model: smartModel,
    })
  }

  const handleDelete = () => {
    if (confirm('Remove your AI settings? You can always reconfigure them later.')) {
      deleteMutation.mutate()
    }
  }

  const providerInfo = PROVIDER_OPTIONS.find(p => p.value === provider)

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">Loading…</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-3xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => navigate('/')} className="text-gray-500 hover:text-gray-700" id="back-to-dashboard">
              ← Back
            </button>
            <h1 className="text-xl font-bold text-gray-900">AI Settings</h1>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8 space-y-6">
        {/* Info banner */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-800">
          <strong>🔒 Your key is encrypted</strong> and only used to process your uploads. It never leaves the backend server.
        </div>

        {/* Existing key status */}
        {existing && (
          <div className="card">
            <h2 className="text-sm font-medium text-gray-500 mb-2">Current configuration</h2>
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <span className="text-gray-500">Provider:</span>
                <p className="font-medium">{existing.provider}</p>
              </div>
              <div>
                <span className="text-gray-500">API Key:</span>
                <p className="font-mono font-medium">{existing.api_key_masked}</p>
              </div>
              <div>
                <span className="text-gray-500">Models:</span>
                <p className="font-medium">{existing.cheap_model} / {existing.smart_model}</p>
              </div>
            </div>
          </div>
        )}

        {/* Configuration form */}
        <div className="card space-y-5">
          <h2 className="text-lg font-semibold text-gray-900">
            {existing ? 'Update configuration' : 'Configure AI provider'}
          </h2>

          {/* Provider */}
          <div>
            <label className="label">Provider</label>
            <select
              id="ai-provider-select"
              value={provider}
              onChange={(e) => handleProviderChange(e.target.value as AIProvider)}
              className="input"
            >
              {PROVIDER_OPTIONS.map(p => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
            {providerInfo && (
              <p className="text-xs text-gray-500 mt-1">{providerInfo.hint}</p>
            )}
          </div>

          {/* API Key */}
          <div>
            <label className="label">API Key {existing && <span className="text-gray-400">(leave blank to keep current)</span>}</label>
            <div className="relative">
              <input
                id="ai-api-key-input"
                type={showKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={existing ? '••••••••' : 'Paste your API key here'}
                className="input pr-16"
              />
              <button
                type="button"
                onClick={() => setShowKey(!showKey)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-gray-500 hover:text-gray-700"
              >
                {showKey ? 'Hide' : 'Show'}
              </button>
            </div>
          </div>

          {/* Models */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Fast model (cheaper)</label>
              <input
                id="ai-cheap-model-input"
                type="text"
                value={cheapModel}
                onChange={(e) => setCheapModel(e.target.value)}
                className="input"
              />
              <p className="text-xs text-gray-500 mt-1">Used for most documents</p>
            </div>
            <div>
              <label className="label">Smart model (more capable)</label>
              <input
                id="ai-smart-model-input"
                type="text"
                value={smartModel}
                onChange={(e) => setSmartModel(e.target.value)}
                className="input"
              />
              <p className="text-xs text-gray-500 mt-1">Used for complex PDFs and messy layouts</p>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              id="ai-settings-save-btn"
              onClick={handleSave}
              disabled={saveMutation.isPending}
              className="btn-primary"
            >
              {saveMutation.isPending ? 'Saving…' : 'Save settings'}
            </button>

            {existing && (
              <>
                <button
                  id="ai-settings-test-btn"
                  onClick={() => testMutation.mutate()}
                  disabled={testMutation.isPending}
                  className="btn-secondary"
                >
                  {testMutation.isPending ? 'Testing…' : '🔌 Test connection'}
                </button>
                <button
                  id="ai-settings-delete-btn"
                  onClick={handleDelete}
                  disabled={deleteMutation.isPending}
                  className="btn-secondary text-red-600 hover:text-red-700"
                >
                  Remove key
                </button>
              </>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}

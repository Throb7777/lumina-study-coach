import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import {
  Bot,
  CircleAlert,
  CircleCheck,
  Database,
  Download,
  ExternalLink,
  FolderCog,
  FolderOpen,
  Library,
  LoaderCircle,
  LogOut,
  Power,
  RefreshCw,
  RotateCcw,
  Save,
  Type,
  UserRound,
} from 'lucide-react'
import {
  useLoaderData,
  useLocation,
  useOutletContext,
  useSearchParams,
} from 'react-router-dom'
import type { AppOutletContext } from '../App'
import { api } from '../api'
import type {
  AiProvider,
  AiProviderOptions,
  AiProviderStatus,
  CourseSummary,
  ExportContentType,
  MaterialSearchSettings,
  ObsidianVaultCandidate,
} from '../api'
import { AppDialog } from '../components/AppDialog'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { DraftStatus } from '../components/DraftStatus'
import { MaterialLibraryDialog } from '../components/MaterialLibraryDialog'
import { UnsavedChangesGuard } from '../components/UnsavedChangesGuard'
import { clearDraft, readDraft, writeDraft } from '../draftStorage'
import type { EditorFontSize, UiFontSize } from '../preferences'
import { defaultAppearancePreferences } from '../preferences'
import type { SettingsRouteData } from '../routeData'
import { useTransientNotice } from '../useTransientNotice'

const fontSizeOptions: { label: string; value: UiFontSize }[] = [
  { label: '小', value: 'small' },
  { label: '标准', value: 'standard' },
  { label: '大', value: 'large' },
]
const manualVaultDraftKey = 'settings-manual-obsidian-path'
const learnerProfileDraftKey = 'settings-learner-profile'
const emptyGeminiLogin = {
  open: false,
  loginId: '',
  phase: 'idle' as 'idle' | 'starting' | 'waiting' | 'cancelling' | 'failed',
  detail: '',
  error: '',
}
const exportContentOptions: {
  label: string
  value: ExportContentType
}[] = [
  { label: '课程大纲', value: 'outline' },
  { label: '每日学习记录', value: 'daily_records' },
  { label: '学习评阅', value: 'ai_reviews' },
  { label: '练习与批改', value: 'exercises' },
  { label: '错题', value: 'mistakes' },
  { label: '小节笔记', value: 'notes' },
]

interface SizeControlProps<T extends UiFontSize | EditorFontSize> {
  label: string
  value: T
  onChange: (value: T) => void
}

function SizeControl<T extends UiFontSize | EditorFontSize>({ label, value, onChange }: SizeControlProps<T>) {
  return (
    <div className="settings-control-row">
      <div>
        <strong>{label}</strong>
        <span>选择后立即应用</span>
      </div>
      <div className="segmented-control" role="group" aria-label={label}>
        {fontSizeOptions.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={value === option.value}
            onClick={() => onChange(option.value as T)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  )
}

export function SettingsPage() {
  const routeData = useLoaderData() as SettingsRouteData
  const location = useLocation()
  const { appearance, onAppearanceChange } = useOutletContext<AppOutletContext>()
  const [searchParams, setSearchParams] = useSearchParams()
  const initialVaultPath = routeData.settings?.obsidian_vault_path ?? ''
  const initialLearnerProfile = routeData.settings?.learner_profile ?? ''
  const desktopLaunch = routeData.settings?.desktop_launch ?? false
  const [restoredManualPath] = useState<string | null>(() => readDraft(manualVaultDraftKey, initialVaultPath))
  const [vaultPath, setVaultPath] = useState(initialVaultPath)
  const [manualPath, setManualPath] = useState(restoredManualPath ?? initialVaultPath)
  const [restoredLearnerProfile] = useState<string | null>(() => (
    readDraft(learnerProfileDraftKey, initialLearnerProfile)
  ))
  const [learnerProfile, setLearnerProfile] = useState(
    restoredLearnerProfile ?? initialLearnerProfile,
  )
  const [savedLearnerProfile, setSavedLearnerProfile] = useState(initialLearnerProfile)
  const [profileBusy, setProfileBusy] = useState(false)
  const [manualPathOpen, setManualPathOpen] = useState(restoredManualPath !== null)
  const [vaults, setVaults] = useState<ObsidianVaultCandidate[]>(routeData.discovery?.vaults ?? [])
  const [browseSupported, setBrowseSupported] = useState(routeData.discovery?.browse_supported ?? false)
  const [loadingVaults, setLoadingVaults] = useState(false)
  const [browsing, setBrowsing] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(routeData.settingsError)
  const [discoveryError, setDiscoveryError] = useState(routeData.discoveryError)
  const [notice, setNotice] = useTransientNotice()
  const [pendingVault, setPendingVault] = useState<ObsidianVaultCandidate | null>(null)
  const [exportOpen, setExportOpen] = useState(false)
  const [exportCourses, setExportCourses] = useState<CourseSummary[]>([])
  const [selectedCourseIds, setSelectedCourseIds] = useState<number[]>([])
  const [selectedContentTypes, setSelectedContentTypes] = useState<ExportContentType[]>([])
  const [exportLoading, setExportLoading] = useState(false)
  const [exportBusy, setExportBusy] = useState(false)
  const [exportError, setExportError] = useState('')
  const [providers, setProviders] = useState<AiProviderStatus[]>([])
  const [providerOptions, setProviderOptions] = useState<AiProviderOptions[]>([])
  const [providerDrafts, setProviderDrafts] = useState<Partial<Record<AiProvider, {
    model: string
    reasoningEffort: string
  }>>>({})
  const [providersLoading, setProvidersLoading] = useState(true)
  const [providerBusy, setProviderBusy] = useState<AiProvider | ''>('')
  const [providerSettingsBusy, setProviderSettingsBusy] = useState<AiProvider | ''>('')
  const [providerError, setProviderError] = useState('')
  const [geminiLogin, setGeminiLogin] = useState(emptyGeminiLogin)
  const geminiLoginControllerRef = useRef<AbortController | null>(null)
  const [geminiDisconnectOpen, setGeminiDisconnectOpen] = useState(false)
  const [geminiDisconnectError, setGeminiDisconnectError] = useState('')
  const [geminiDisconnectTrigger, setGeminiDisconnectTrigger] = useState<HTMLButtonElement | null>(null)
  const [shutdownOpen, setShutdownOpen] = useState(false)
  const [shutdownBusy, setShutdownBusy] = useState(false)
  const [shutdownError, setShutdownError] = useState('')
  const [serviceStopped, setServiceStopped] = useState(false)
  const [materialDialogTrigger, setMaterialDialogTrigger] = useState<HTMLButtonElement | null>(null)
  const [materialSearch, setMaterialSearch] = useState<MaterialSearchSettings>({
    semantic_enabled: routeData.settings?.semantic_search_enabled ?? false,
    model_ready: routeData.settings?.semantic_search_model_ready ?? false,
    model: 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
    model_size: '约 220 MB',
  })
  const [materialSearchBusy, setMaterialSearchBusy] = useState(false)
  const [materialSearchError, setMaterialSearchError] = useState('')
  const materialDialogOpen = searchParams.get('dialog') === 'materials'

  useEffect(() => {
    if (location.hash !== '#local-service') return
    const frame = window.requestAnimationFrame(() => {
      document.getElementById('local-service')?.scrollIntoView({ block: 'start' })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [location.hash])

  const hasUnsavedSettings = manualPath !== vaultPath || learnerProfile !== savedLearnerProfile

  async function toggleSemanticSearch() {
    setMaterialSearchBusy(true)
    setMaterialSearchError('')
    try {
      const needsModel = !materialSearch.semantic_enabled || !materialSearch.model_ready
      const updated = needsModel
        ? await api.enableMaterialSearch()
        : await api.disableMaterialSearch()
      setMaterialSearch(updated)
      setNotice(updated.semantic_enabled ? '语义检索已启用' : '语义检索已关闭')
    } catch (requestError) {
      setMaterialSearchError(
        requestError instanceof Error ? requestError.message : '更新语义检索设置失败',
      )
    } finally {
      setMaterialSearchBusy(false)
    }
  }

  async function shutdownLocalService() {
    setShutdownBusy(true)
    setShutdownError('')
    try {
      await api.shutdownLocalService()
      setShutdownOpen(false)
      setServiceStopped(true)
    } catch (requestError) {
      setShutdownError(requestError instanceof Error ? requestError.message : '无法关闭本地服务')
    } finally {
      setShutdownBusy(false)
    }
  }

  function acceptProviderOptions(options: AiProviderOptions[]) {
    setProviderOptions(options)
    setProviderDrafts(Object.fromEntries(options.map((provider) => [
      provider.provider,
      {
        model: provider.selected_model,
        reasoningEffort: provider.selected_reasoning_effort,
      },
    ])))
  }

  async function refreshProviders(signal?: AbortSignal) {
    setProvidersLoading(true)
    setProviderError('')
    try {
      const snapshot = await api.getAiProviderSnapshot(signal)
      setProviders(snapshot.providers)
      acceptProviderOptions(snapshot.options)
    } catch (requestError) {
      if (!(requestError instanceof Error && requestError.name === 'AbortError')) {
        setProviderError(requestError instanceof Error ? requestError.message : '读取模型连接状态失败')
      }
    } finally {
      if (!signal?.aborted) setProvidersLoading(false)
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    api.getAiProviderSnapshot(controller.signal)
      .then((snapshot) => {
        setProviders(Array.isArray(snapshot.providers) ? snapshot.providers : [])
        acceptProviderOptions(Array.isArray(snapshot.options) ? snapshot.options : [])
      })
      .catch((requestError: unknown) => {
        if (!(requestError instanceof Error && requestError.name === 'AbortError')) {
          setProviderError(
            requestError instanceof Error ? requestError.message : '读取模型连接状态失败',
          )
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setProvidersLoading(false)
      })
    return () => controller.abort()
  }, [])

  function updateProviderModel(provider: AiProvider, model: string) {
    const options = providerOptions.find((item) => item.provider === provider)
    const modelOption = options?.models.find((item) => item.model === model)
    if (!modelOption) return
    setProviderDrafts((current) => {
      const currentEffort = current[provider]?.reasoningEffort ?? ''
      return {
        ...current,
        [provider]: {
          model,
          reasoningEffort: modelOption.reasoning_efforts.includes(currentEffort)
            ? currentEffort
            : modelOption.default_reasoning_effort || modelOption.reasoning_efforts[0] || '',
        },
      }
    })
  }

  function updateProviderEffort(provider: AiProvider, reasoningEffort: string) {
    setProviderDrafts((current) => ({
      ...current,
      [provider]: {
        model: current[provider]?.model ?? '',
        reasoningEffort,
      },
    }))
  }

  async function saveProviderPreference(provider: AiProvider) {
    const draft = providerDrafts[provider]
    if (!draft?.model || !draft.reasoningEffort) return
    setProviderSettingsBusy(provider)
    setProviderError('')
    try {
      const updated = await api.updateAiProviderPreference(provider, {
        model: draft.model,
        reasoning_effort: draft.reasoningEffort,
      })
      acceptProviderOptions(providerOptions.map((item) => (
        item.provider === provider ? updated : item
      )))
      setProviders(await api.getAiProviders())
      setNotice(`${provider === 'codex' ? 'Codex' : 'Gemini'} 模型设置已保存`)
    } catch (requestError) {
      setProviderError(requestError instanceof Error ? requestError.message : '保存模型设置失败')
    } finally {
      setProviderSettingsBusy('')
    }
  }

  function resetProviderDraft(provider: AiProvider) {
    const options = providerOptions.find((item) => item.provider === provider)
    if (!options) return
    setProviderDrafts((current) => ({
      ...current,
      [provider]: {
        model: options.default_model,
        reasoningEffort: options.default_reasoning_effort,
      },
    }))
  }

  useEffect(() => {
    if (manualPath === vaultPath) clearDraft(manualVaultDraftKey)
    else writeDraft(manualVaultDraftKey, vaultPath, manualPath)
  }, [manualPath, vaultPath])

  useEffect(() => {
    if (learnerProfile === savedLearnerProfile) clearDraft(learnerProfileDraftKey)
    else writeDraft(learnerProfileDraftKey, savedLearnerProfile, learnerProfile)
  }, [learnerProfile, savedLearnerProfile])

  async function saveLearnerProfile() {
    setProfileBusy(true)
    setError('')
    setNotice('')
    try {
      const settings = await api.updateLearnerProfile(learnerProfile)
      setLearnerProfile(settings.learner_profile)
      setSavedLearnerProfile(settings.learner_profile)
      clearDraft(learnerProfileDraftKey)
      setNotice('学习者背景已保存')
      return ''
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : '保存学习者背景失败'
      setError(message)
      return message
    } finally {
      setProfileBusy(false)
    }
  }

  async function refreshVaults(signal?: AbortSignal) {
    setLoadingVaults(true)
    setDiscoveryError('')
    try {
      const discovery = await api.discoverObsidianVaults(signal)
      setVaults(discovery.vaults)
      setBrowseSupported(discovery.browse_supported)
    } catch (requestError) {
      if (!(requestError instanceof Error && requestError.name === 'AbortError')) {
        setDiscoveryError(requestError instanceof Error ? requestError.message : '无法检测 Obsidian Vault')
      }
    } finally {
      if (!signal?.aborted) setLoadingVaults(false)
    }
  }

  async function browseVault() {
    setBrowsing(true)
    setError('')
    setNotice('')
    try {
      const result = await api.browseObsidianVault()
      if (result.vault) setPendingVault(result.vault)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '无法打开目录选择窗口')
    } finally {
      setBrowsing(false)
    }
  }

  async function saveVault(path: string) {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const settings = await api.updateObsidianVault(path)
      setVaultPath(settings.obsidian_vault_path)
      setManualPath(settings.obsidian_vault_path)
      setPendingVault(null)
      setNotice('Obsidian Vault 已保存')
      return ''
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : '保存设置失败'
      setError(message)
      return message
    } finally {
      setBusy(false)
    }
  }

  async function saveManualPath(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await saveVault(manualPath)
  }

  async function openExportDialog() {
    setExportOpen(true)
    setExportLoading(true)
    setExportError('')
    try {
      const courses = await api.listCourses()
      setExportCourses(courses)
      setSelectedCourseIds(courses.map((course) => course.id))
      setSelectedContentTypes(exportContentOptions
        .map((option) => option.value)
        .filter((contentType) => contentType !== 'notes' || Boolean(vaultPath)))
    } catch (requestError) {
      setExportError(requestError instanceof Error ? requestError.message : '读取课程失败')
    } finally {
      setExportLoading(false)
    }
  }

  function toggleExportCourse(courseId: number) {
    setSelectedCourseIds((current) => (
      current.includes(courseId)
        ? current.filter((selectedId) => selectedId !== courseId)
        : [...current, courseId]
    ))
  }

  function toggleExportContent(contentType: ExportContentType) {
    setSelectedContentTypes((current) => (
      current.includes(contentType)
        ? current.filter((selectedType) => selectedType !== contentType)
        : [...current, contentType]
    ))
  }

  async function exportArchive() {
    if (selectedCourseIds.length === 0) {
      setExportError('请至少选择一门课程')
      return
    }
    if (selectedContentTypes.length === 0) {
      setExportError('请至少选择一种导出内容')
      return
    }

    setExportBusy(true)
    setExportError('')
    try {
      const file = await api.exportMarkdownArchive({
        course_ids: selectedCourseIds,
        content_types: selectedContentTypes,
      })
      const downloadUrl = URL.createObjectURL(file.blob)
      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = file.filename
      document.body.append(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(downloadUrl)
      setExportOpen(false)
      setNotice('分层 Markdown 导出已生成')
    } catch (requestError) {
      setExportError(requestError instanceof Error ? requestError.message : '导出失败')
    } finally {
      setExportBusy(false)
    }
  }

  async function waitForProviderLogin(
    provider: AiProvider,
    loginId: string,
    signal?: AbortSignal,
    onProgress?: (detail: string) => void,
  ) {
    for (let attempt = 0; attempt < 300; attempt += 1) {
      const login = provider === 'codex'
        ? await api.getCodexLoginStatus(loginId, signal)
        : await api.getGeminiLoginStatus(loginId, signal)
      if (login.detail) onProgress?.(login.detail)
      if (login.status === 'succeeded') {
        setProviders(await api.getAiProviders())
        return
      }
      if (login.status === 'failed' || login.status === 'not_found') {
        throw new Error(login.error || `${provider === 'codex' ? 'Codex' : 'Antigravity'} 登录失败`)
      }
      await new Promise<void>((resolve, reject) => {
        const timer = window.setTimeout(resolve, 1000)
        signal?.addEventListener('abort', () => {
          window.clearTimeout(timer)
          reject(new DOMException('登录已取消', 'AbortError'))
        }, { once: true })
      })
    }
    throw new Error('登录等待超时，请重新连接。')
  }

  async function connectCodex() {
    const loginWindow = window.open('', '_blank')
    let loginPageOpened = false
    setProviderBusy('codex')
    setProviderError('')
    try {
      const login = await api.startCodexLogin()
      if (loginWindow) {
        loginWindow.location.href = login.auth_url
      } else {
        window.open(login.auth_url, '_blank', 'noopener,noreferrer')
      }
      loginPageOpened = true
      await waitForProviderLogin('codex', login.login_id)
      setNotice('Codex 已连接')
    } catch (requestError) {
      if (!loginPageOpened) loginWindow?.close()
      setProviderError(requestError instanceof Error ? requestError.message : '启动 Codex 登录失败')
    } finally {
      setProviderBusy('')
    }
  }

  async function disconnectCodex() {
    setProviderBusy('codex')
    setProviderError('')
    try {
      await api.logoutCodex()
      await refreshProviders()
      setNotice('Codex 已断开')
    } catch (requestError) {
      setProviderError(requestError instanceof Error ? requestError.message : '断开 Codex 失败')
    } finally {
      setProviderBusy('')
    }
  }

  async function connectGemini() {
    let controller: AbortController | null = null
    setProviderBusy('gemini')
    setProviderError('')
    try {
      await api.enableGemini()
      const refreshed = await api.getAiProviders()
      setProviders(refreshed)
      if (refreshed.find((provider) => provider.provider === 'gemini')?.connected) {
        setNotice('Antigravity 已重新连接')
        return
      }
      controller = new AbortController()
      geminiLoginControllerRef.current = controller
      setGeminiLogin({
        open: true,
        loginId: '',
        phase: 'starting',
        detail: '正在打开 Antigravity 登录窗口',
        error: '',
      })
      const login = await api.startGeminiLogin()
      setGeminiLogin((current) => ({
        ...current,
        loginId: login.login_id,
        phase: 'waiting',
        detail: '请在弹出的窗口中完成 Google 登录',
      }))
      await waitForProviderLogin('gemini', login.login_id, controller.signal, (detail) => {
        setGeminiLogin((current) => ({ ...current, detail }))
      })
      setGeminiLogin(emptyGeminiLogin)
      setNotice('Antigravity 已连接')
    } catch (requestError) {
      if (!(requestError instanceof Error && requestError.name === 'AbortError')) {
        const message = requestError instanceof Error ? requestError.message : '启动 Antigravity 登录失败'
        setGeminiLogin((current) => ({
          ...current,
          open: true,
          phase: 'failed',
          error: message,
          detail: '',
        }))
      }
    } finally {
      if (controller && geminiLoginControllerRef.current === controller) {
        geminiLoginControllerRef.current = null
      }
      setProviderBusy('')
    }
  }

  async function disconnectGemini() {
    setProviderBusy('gemini')
    setGeminiDisconnectError('')
    try {
      await api.disconnectGemini()
      await refreshProviders()
      setGeminiDisconnectOpen(false)
      setNotice('Antigravity 已从本工具断开')
    } catch (requestError) {
      setGeminiDisconnectError(
        requestError instanceof Error ? requestError.message : '断开 Antigravity 失败',
      )
    } finally {
      setProviderBusy('')
    }
  }

  async function cancelGeminiLogin() {
    const loginId = geminiLogin.loginId
    setGeminiLogin((current) => ({ ...current, phase: 'cancelling', detail: '正在取消连接' }))
    geminiLoginControllerRef.current?.abort()
    try {
      if (loginId) await api.cancelGeminiLogin(loginId)
      setGeminiLogin(emptyGeminiLogin)
    } catch (requestError) {
      setGeminiLogin((current) => ({
        ...current,
        phase: 'failed',
        error: requestError instanceof Error ? requestError.message : '取消连接失败',
        detail: '',
      }))
    }
  }

  function providerDotClass(provider: AiProviderStatus) {
    if (provider.state === 'model_unavailable') return ' provider-dot--warning'
    if (provider.state === 'launch_blocked' || provider.state === 'error') return ' provider-dot--error'
    return provider.connected ? ' provider-dot--connected' : ''
  }

  function providerModelLabel(provider: AiProviderStatus) {
    const embeddedEffort = provider.preferred_model.match(/\s*\((medium|high)\)$/i)?.[1] ?? ''
    const model = provider.preferred_model.replace(/\s*\((medium|high)\)$/i, '')
    const effort = provider.reasoning_effort || embeddedEffort
    const effortLabel = effort ? `${effort.charAt(0).toUpperCase()}${effort.slice(1).toLowerCase()}` : ''
    const availability = provider.model_available === true
      ? '可用'
      : provider.model_available === false
        ? '不可用'
        : ''
    return [model, effortLabel, availability].filter(Boolean).join(' · ')
  }

  if (serviceStopped) {
    return (
      <main className="content content--workspace settings-page">
        <header className="page-heading">
          <p className="eyebrow">本地服务</p>
          <h1>服务正在关闭</h1>
          <p className="page-summary">学习内容已保留。现在可以关闭这个浏览器页面，下次双击 Lumina 图标即可重新启动。</p>
        </header>
      </main>
    )
  }

  return (
    <main className="content content--workspace settings-page">
      <header className="page-heading">
        <p className="eyebrow">本地配置</p>
        <h1>设置</h1>
        <p className="page-summary">调整 Lumina 的阅读体验和本地笔记保存位置。</p>
      </header>
      {error && <p className="error-banner" role="alert">{error}</p>}
      {notice && <p className="notice-banner" role="status">{notice}</p>}

      <section className="settings-section settings-section--first" aria-labelledby="ai-settings-title">
        <div className="settings-section__heading"><Bot size={19} aria-hidden="true" /><h2 id="ai-settings-title">模型连接</h2></div>
        <p className="settings-section__description">连接后，学习流程会调用相应模型完成评阅、练习、批改和笔记整理。账号、模型与可用状态见下方。</p>
        {providerError && <p className="inline-error" role="alert">{providerError}</p>}
        {providersLoading && <p className="muted">正在读取连接状态...</p>}
        <div className="provider-list">
          {providers.map((provider) => {
            const options = providerOptions.find((item) => item.provider === provider.provider)
            const draft = providerDrafts[provider.provider]
            const selectedOption = options?.models.find((item) => item.model === draft?.model)
            const settingsChanged = Boolean(options && draft && (
              options.selected_model !== draft.model
              || options.selected_reasoning_effort !== draft.reasoningEffort
            ))
            const controlsDisabled = !provider.connected || !options || options.models.length === 0
            return (
              <div className="provider-row" key={provider.provider}>
                <div className="provider-row__summary">
                  <div className="provider-row__identity">
                    <span className={`provider-dot${providerDotClass(provider)}`} />
                    <div>
                      <strong>{provider.provider === 'codex' ? 'Codex' : 'Gemini · Antigravity'}</strong>
                      <span>{provider.detail}</span>
                      {provider.connected && (
                        <small>
                          {provider.account
                            ? `${provider.account}${provider.plan ? ` · ${provider.plan}` : ''}`
                            : provider.provider === 'gemini'
                              ? '账号已连接，CLI 暂未返回账号标识'
                              : '账号已连接'}
                        </small>
                      )}
                      {provider.preferred_model && <small>{providerModelLabel(provider)}</small>}
                      {provider.active_model && <small>最近使用 {provider.active_model}</small>}
                      {provider.version && <small>CLI {provider.version.replace(/^codex-cli\s+/i, '')}</small>}
                    </div>
                  </div>
                  {provider.provider === 'codex' && (
                    provider.connected
                      ? <button className="secondary-button" type="button" disabled={Boolean(providerBusy)} onClick={() => void disconnectCodex()}><LogOut size={15} />断开</button>
                      : <button className="primary-button" type="button" disabled={Boolean(providerBusy) || !provider.installed} onClick={() => void connectCodex()}><ExternalLink size={15} />{providerBusy === 'codex' ? '等待登录' : '连接 Codex'}</button>
                  )}
                  {provider.provider === 'gemini' && (
                    provider.connected
                      ? <button
                          className="secondary-button"
                          type="button"
                          disabled={Boolean(providerBusy)}
                          onClick={(event) => {
                            setGeminiDisconnectError('')
                            setGeminiDisconnectTrigger(event.currentTarget)
                            setGeminiDisconnectOpen(true)
                          }}
                        ><LogOut size={15} />断开</button>
                      : <button className="primary-button" type="button" disabled={Boolean(providerBusy) || !provider.installed} onClick={() => void connectGemini()}>
                          <ExternalLink size={15} />
                          {providerBusy === 'gemini' ? '正在连接' : '连接 Antigravity'}
                        </button>
                  )}
                </div>
                <div className="provider-model-controls" aria-label={`${provider.provider === 'codex' ? 'Codex' : 'Gemini'} 模型设置`}>
                  <label>
                    <span>模型</span>
                    <select
                      aria-label={`${provider.provider === 'codex' ? 'Codex' : 'Gemini'} 模型`}
                      value={draft?.model ?? ''}
                      disabled={controlsDisabled || Boolean(providerSettingsBusy)}
                      onChange={(event) => updateProviderModel(provider.provider, event.target.value)}
                    >
                      {options?.models.map((model) => (
                        <option key={model.model} value={model.model}>{model.display_name}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span>思考强度</span>
                    <select
                      aria-label={`${provider.provider === 'codex' ? 'Codex' : 'Gemini'} 思考强度`}
                      value={draft?.reasoningEffort ?? ''}
                      disabled={controlsDisabled || Boolean(providerSettingsBusy)}
                      onChange={(event) => updateProviderEffort(provider.provider, event.target.value)}
                    >
                      {selectedOption?.reasoning_efforts.map((effort) => (
                        <option key={effort} value={effort}>{effort.charAt(0).toUpperCase() + effort.slice(1)}</option>
                      ))}
                    </select>
                  </label>
                  <div className="provider-model-controls__actions">
                    <button
                      className="text-button"
                      type="button"
                      disabled={controlsDisabled || Boolean(providerSettingsBusy)}
                      onClick={() => resetProviderDraft(provider.provider)}
                    ><RotateCcw size={14} />恢复默认</button>
                    <button
                      className="secondary-button"
                      type="button"
                      disabled={!settingsChanged || Boolean(providerSettingsBusy)}
                      onClick={() => void saveProviderPreference(provider.provider)}
                    >{providerSettingsBusy === provider.provider ? '应用中' : '应用'}</button>
                  </div>
                  {options?.error && <p className="provider-model-controls__error">模型列表暂不可用：{options.error}</p>}
                </div>
              </div>
            )
          })}
        </div>
        <button className="text-button settings-reset" type="button" disabled={providersLoading || Boolean(providerBusy) || Boolean(providerSettingsBusy)} onClick={() => void refreshProviders()}>
          <RefreshCw size={15} aria-hidden="true" />
          刷新连接与模型列表
        </button>
      </section>

      <AppDialog
        open={geminiLogin.open}
        title="连接 Antigravity"
        description="登录完成后，Lumina 会自动检查账号和首选模型。"
        closeOnBackdrop={false}
        showCloseButton={false}
        busy={geminiLogin.phase === 'cancelling'}
        onClose={() => {
          if (geminiLogin.phase === 'failed') setGeminiLogin(emptyGeminiLogin)
        }}
        footer={geminiLogin.phase === 'failed' ? (
          <button className="primary-button" type="button" onClick={() => setGeminiLogin(emptyGeminiLogin)}>关闭</button>
        ) : (
          <button className="secondary-button" type="button" disabled={geminiLogin.phase === 'cancelling'} onClick={() => void cancelGeminiLogin()}>
            {geminiLogin.phase === 'cancelling' ? '正在取消' : '取消连接'}
          </button>
        )}
      >
        {geminiLogin.phase === 'failed' ? (
          <p className="provider-login-error" role="alert">{geminiLogin.error}</p>
        ) : (
          <div className="provider-login-progress" role="status" aria-live="polite">
            <LoaderCircle size={20} aria-hidden="true" />
            <div>
              <strong>{geminiLogin.phase === 'starting' ? '正在启动' : geminiLogin.phase === 'cancelling' ? '正在取消' : '等待登录'}</strong>
              <span>{geminiLogin.detail}</span>
            </div>
          </div>
        )}
      </AppDialog>

      <ConfirmDialog
        open={geminiDisconnectOpen}
        title="断开 Antigravity？"
        description="Lumina 将停止调用 Gemini，但不会删除 Antigravity 官方客户端中的 Google 登录。之后可以直接重新连接。"
        confirmLabel="断开"
        variant="warning"
        busy={providerBusy === 'gemini'}
        error={geminiDisconnectError}
        returnFocusTo={geminiDisconnectTrigger}
        onCancel={() => {
          if (providerBusy === 'gemini') return
          setGeminiDisconnectError('')
          setGeminiDisconnectOpen(false)
        }}
        onConfirm={disconnectGemini}
      />

      <MaterialLibraryDialog
        open={materialDialogOpen}
        returnFocusTo={materialDialogTrigger}
        onClose={() => {
          const next = new URLSearchParams(searchParams)
          next.delete('dialog')
          setSearchParams(next, { replace: true })
        }}
      />

      <section className="settings-section" aria-labelledby="learner-settings-title">
        <div className="settings-section__heading"><UserRound size={19} aria-hidden="true" /><h2 id="learner-settings-title">学习者背景</h2></div>
        <p className="settings-section__description">描述已有基础和能力边界。该内容只保存在本机，并作为各学习节点的共同上下文。</p>
        <label className="settings-profile-field">
          <span>我的学习背景</span>
          <textarea
            rows={5}
            value={learnerProfile}
            placeholder="例如：我的专业背景、已经学过的课程和熟悉的工具。"
            onChange={(event) => setLearnerProfile(event.target.value)}
          />
        </label>
        <div className="settings-profile-actions">
          <DraftStatus dirtyCount={learnerProfile !== savedLearnerProfile ? 1 : 0} />
          <button
            className="primary-button"
            type="button"
            disabled={profileBusy || learnerProfile === savedLearnerProfile}
            onClick={() => void saveLearnerProfile()}
          >
            <Save size={15} />{profileBusy ? '正在保存' : '保存背景'}
          </button>
        </div>
      </section>

      <section className="settings-section" aria-labelledby="material-settings-title">
        <div className="settings-section__heading"><Library size={19} aria-hidden="true" /><h2 id="material-settings-title">材料库</h2></div>
        <p className="settings-section__description">统一查看和管理本机保存的 PDF 与 URL 快照，也可以调整材料归属。</p>
        <div className="settings-action-row">
          <div><strong>本地参考材料</strong><span>查看解析状态、刷新 URL 快照或删除材料。</span></div>
          <button
            className="secondary-button"
            type="button"
            onClick={(event) => {
              setMaterialDialogTrigger(event.currentTarget)
              const next = new URLSearchParams(searchParams)
              next.set('dialog', 'materials')
              setSearchParams(next, { replace: true })
            }}
          >
            <Library size={16} />打开材料库
          </button>
        </div>
        <div className="settings-action-row">
          <div>
            <strong><Database size={15} aria-hidden="true" />混合检索</strong>
            <span>
              全文检索始终启用。语义检索使用本机多语言模型（{materialSearch.model_size}），
              {materialSearch.semantic_enabled && materialSearch.model_ready
                ? '当前已启用。'
                : materialSearch.semantic_enabled
                  ? '模型文件缺失，需要重新下载后才会启用。'
                  : '仅在确认后下载并启用。'}
            </span>
            {materialSearchError && <span className="inline-error" role="alert">{materialSearchError}</span>}
          </div>
          <button
            className="secondary-button"
            type="button"
            disabled={materialSearchBusy}
            onClick={() => void toggleSemanticSearch()}
          >
            <Database size={16} aria-hidden="true" />
            {materialSearchBusy
              ? '正在准备'
              : materialSearch.semantic_enabled && materialSearch.model_ready
                ? '关闭语义检索'
                : materialSearch.semantic_enabled ? '重新下载模型' : '下载并启用'}
          </button>
        </div>
      </section>

      <section className="settings-section" aria-labelledby="appearance-settings-title">
        <div className="settings-section__heading"><Type size={19} aria-hidden="true" /><h2 id="appearance-settings-title">外观</h2></div>
        <div className="settings-controls">
          <SizeControl
            label="界面字号"
            value={appearance.uiFontSize}
            onChange={(uiFontSize) => onAppearanceChange((current) => ({ ...current, uiFontSize }))}
          />
          <SizeControl
            label="笔记编辑字号"
            value={appearance.editorFontSize}
            onChange={(editorFontSize) => onAppearanceChange((current) => ({ ...current, editorFontSize }))}
          />
          <label className="settings-control-row settings-toggle-row">
            <div>
              <strong>减少动效</strong>
              <span>关闭侧栏和完成状态的过渡动画</span>
            </div>
            <input
              type="checkbox"
              checked={appearance.reduceMotion}
              onChange={(event) => onAppearanceChange((current) => ({ ...current, reduceMotion: event.target.checked }))}
            />
          </label>
        </div>
        <button className="text-button settings-reset" type="button" onClick={() => onAppearanceChange(defaultAppearancePreferences)}>
          <RotateCcw size={15} aria-hidden="true" />
          恢复默认外观
        </button>
      </section>

      <section className="settings-section" aria-labelledby="obsidian-settings-title">
        <div className="settings-section__heading"><FolderCog size={19} aria-hidden="true" /><h2 id="obsidian-settings-title">Obsidian</h2></div>
        {vaultPath && (
          <div className="current-vault">
            <span>当前 Vault</span>
            <strong>{vaultPath}</strong>
          </div>
        )}

        <div className="vault-toolbar">
          <div>
            <strong>自动检测</strong>
            <span>读取 Obsidian 已登记的 Vault，不扫描磁盘。</span>
          </div>
          <div className="header-actions">
            <button className="icon-button" type="button" title="重新检测" aria-label="重新检测 Vault" disabled={loadingVaults} onClick={() => void refreshVaults()}>
              <RefreshCw size={16} aria-hidden="true" />
            </button>
            <button className="secondary-button" type="button" disabled={!browseSupported || browsing} onClick={() => void browseVault()}>
              <FolderOpen size={16} aria-hidden="true" />
              {browsing ? '等待选择' : '浏览文件夹'}
            </button>
          </div>
        </div>

        {loadingVaults && <p className="muted">正在检测 Obsidian Vault...</p>}
        {discoveryError && <p className="inline-error" role="alert">{discoveryError}</p>}
        {!loadingVaults && !discoveryError && vaults.length === 0 && <p className="muted">没有检测到已登记的 Vault，可以浏览文件夹或手动输入路径。</p>}
        <div className="vault-list">
          {vaults.map((vault) => {
            const selected = vault.path === vaultPath
            return (
              <div className={`vault-option${selected ? ' vault-option--selected' : ''}`} key={vault.path}>
                <div>
                  <strong>{vault.name}</strong>
                  <span>{vault.path}</span>
                </div>
                <button className="secondary-button" type="button" disabled={selected} onClick={() => setPendingVault(vault)}>
                  {selected ? '正在使用' : '选择'}
                </button>
              </div>
            )
          })}
        </div>

        <details
          className="manual-path-details"
          open={manualPathOpen}
          onToggle={(event) => setManualPathOpen(event.currentTarget.open)}
        >
          <summary>手动指定路径</summary>
          <DraftStatus
            dirtyCount={manualPath === vaultPath ? 0 : 1}
            recoveredLabel={restoredManualPath === null ? undefined : '已恢复上次路径草稿'}
          />
          <form className="stack-form" onSubmit={saveManualPath}>
            <label>Vault 绝对路径<input required value={manualPath} onChange={(event) => setManualPath(event.target.value)} placeholder="D:\\Notes\\My Vault" /></label>
            <div className="form-actions"><button className="primary-button" type="submit" disabled={busy}><Save size={15} aria-hidden="true" />{busy ? '保存中' : '保存路径'}</button></div>
          </form>
        </details>
      </section>

      <section className="settings-section" aria-labelledby="export-settings-title">
        <div className="settings-section__heading"><Download size={19} aria-hidden="true" /><h2 id="export-settings-title">导出</h2></div>
        <div className="settings-action-row">
          <div>
            <strong>Markdown 导出</strong>
            <span>选择课程和内容，导出 Markdown 文件。</span>
          </div>
          <button className="secondary-button" type="button" onClick={() => void openExportDialog()}>
            <Download size={16} aria-hidden="true" />
            选择并导出
          </button>
        </div>
      </section>

      <section
        id="local-service"
        className="settings-section"
        aria-labelledby="service-settings-title"
      >
        <div className="settings-section__heading"><Power size={19} aria-hidden="true" /><h2 id="service-settings-title">本地服务与运行状态</h2></div>
        <div className="settings-action-row service-status-row" aria-live="polite">
          <div>
            <strong>
              {routeData.settings
                ? <CircleCheck className="service-status-icon service-status-icon--online" size={17} aria-hidden="true" />
                : <CircleAlert className="service-status-icon service-status-icon--offline" size={17} aria-hidden="true" />}
              {routeData.settings ? 'Lumina 本地服务已连接' : 'Lumina 本地服务未连接'}
            </strong>
            <span>
              {routeData.settings
                ? `v${routeData.settings.service_version || '版本暂不可用'} · 本地数据服务运行正常`
                : '请重新启动 Lumina 后刷新此页面。'}
            </span>
          </div>
        </div>
        {routeData.settings && (
          <div className="settings-action-row">
            <div>
              <strong>{desktopLaunch ? '桌面启动器正在管理服务' : '当前由诊断终端运行'}</strong>
              <span>{desktopLaunch ? '关闭后，下次双击 Lumina 图标即可重新启动。' : '请在启动服务的终端中按 Ctrl+C 停止。'}</span>
            </div>
            {desktopLaunch && (
              <button className="secondary-button" type="button" onClick={() => setShutdownOpen(true)}>
                <Power size={16} aria-hidden="true" />关闭服务
              </button>
            )}
          </div>
        )}
      </section>

      <ConfirmDialog
        open={shutdownOpen}
        title="关闭本地服务？"
        description="页面将无法继续使用，正在运行的生成任务也会被中断。已经保存的学习内容不会受影响。"
        confirmLabel="关闭服务"
        variant="warning"
        busy={shutdownBusy}
        error={shutdownError}
        closeOnBackdrop={false}
        showCloseButton={false}
        onCancel={() => {
          if (shutdownBusy) return
          setShutdownError('')
          setShutdownOpen(false)
        }}
        onConfirm={shutdownLocalService}
      />

      <AppDialog
        open={exportOpen}
        title="导出 Markdown"
        description="选择需要导出的课程和内容。"
        size="medium"
        busy={exportBusy}
        onClose={() => setExportOpen(false)}
        footer={(
          <>
            <button className="secondary-button" type="button" disabled={exportBusy} onClick={() => setExportOpen(false)}>取消</button>
            <button className="primary-button" type="button" disabled={exportBusy || exportLoading || exportCourses.length === 0} onClick={() => void exportArchive()}>
              <Download size={16} aria-hidden="true" />
              {exportBusy ? '生成中' : '导出'}
            </button>
          </>
        )}
      >
        {exportError && <p className="dialog-error" role="alert">{exportError}</p>}
        {exportLoading && <p className="muted">正在读取课程...</p>}
        {!exportLoading && exportCourses.length === 0 && !exportError && <p className="muted">当前没有可导出的课程。</p>}
        {!exportLoading && exportCourses.length > 0 && (
          <>
            <div className="export-dialog-grid">
              <section className="export-choice-section" aria-labelledby="export-course-title">
                <div className="export-choice-heading">
                  <h3 id="export-course-title">课程范围</h3>
                  <div>
                    <button className="text-button" type="button" onClick={() => setSelectedCourseIds(exportCourses.map((course) => course.id))}>全选</button>
                    <button className="text-button" type="button" onClick={() => setSelectedCourseIds([])}>清空</button>
                  </div>
                </div>
                <div className="export-choice-list">
                  {exportCourses.map((course) => (
                    <label className="export-checkbox-row" key={course.id}>
                      <input type="checkbox" checked={selectedCourseIds.includes(course.id)} onChange={() => toggleExportCourse(course.id)} />
                      <span>{course.name}</span>
                    </label>
                  ))}
                </div>
              </section>
              <section className="export-choice-section" aria-labelledby="export-content-title">
                <div className="export-choice-heading">
                  <h3 id="export-content-title">导出内容</h3>
                  <div>
                    <button className="text-button" type="button" onClick={() => setSelectedContentTypes(exportContentOptions.map((option) => option.value).filter((contentType) => contentType !== 'notes' || Boolean(vaultPath)))}>全选</button>
                    <button className="text-button" type="button" onClick={() => setSelectedContentTypes([])}>清空</button>
                  </div>
                </div>
                <div className="export-choice-list">
                  {exportContentOptions.map((option) => {
                    const disabled = option.value === 'notes' && !vaultPath
                    return (
                      <label className={`export-checkbox-row${disabled ? ' export-checkbox-row--disabled' : ''}`} key={option.value}>
                        <input type="checkbox" disabled={disabled} checked={selectedContentTypes.includes(option.value)} onChange={() => toggleExportContent(option.value)} />
                        <span>{option.label}{disabled ? '（未配置 Vault）' : ''}</span>
                      </label>
                    )
                  })}
                </div>
              </section>
            </div>
            <p className="export-selection-summary">已选择 {selectedCourseIds.length} 门课程，{selectedContentTypes.length} 类内容</p>
          </>
        )}
      </AppDialog>

      <AppDialog
        open={pendingVault !== null}
        title="确认 Obsidian Vault"
        description="确认后，后续小节笔记将保存到这个 Vault。"
        busy={busy}
        onClose={() => setPendingVault(null)}
        footer={(
          <>
            <button className="secondary-button" type="button" disabled={busy} onClick={() => setPendingVault(null)}>取消</button>
            <button className="primary-button" type="button" disabled={busy || !pendingVault} onClick={() => pendingVault && void saveVault(pendingVault.path)}>
              {busy ? '保存中' : '确认使用'}
            </button>
          </>
        )}
      >
        {pendingVault && (
          <div className="vault-confirmation">
            {error && <p className="dialog-error" role="alert">{error}</p>}
            <strong>{pendingVault.name}</strong>
            <code>{pendingVault.path}</code>
            <dl>
              <div><dt>Obsidian 配置</dt><dd>{pendingVault.has_obsidian_directory ? '已检测到' : '未检测到'}</dd></div>
              <div><dt>目录写入</dt><dd>{pendingVault.writable ? '可写' : '不可写或无法确认'}</dd></div>
            </dl>
            {!pendingVault.has_obsidian_directory && <p className="dialog-warning">所选目录中没有检测到 `.obsidian`，请确认它确实是 Vault 根目录。</p>}
          </div>
        )}
      </AppDialog>
      <UnsavedChangesGuard
        dirty={hasUnsavedSettings}
        onDiscard={() => {
          clearDraft(manualVaultDraftKey)
          clearDraft(learnerProfileDraftKey)
        }}
        onSave={async () => {
          if (manualPath !== vaultPath) {
            const saveError = await saveVault(manualPath)
            if (saveError) throw new Error(saveError)
          }
          if (learnerProfile !== savedLearnerProfile) {
            const saveError = await saveLearnerProfile()
            if (saveError) throw new Error(saveError)
          }
        }}
      />
    </main>
  )
}

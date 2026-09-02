import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type PointerEvent as ReactPointerEvent,
} from 'react'
import { BookX, Library, NotebookPen, PanelLeftClose, PanelLeftOpen, Settings } from 'lucide-react'
import { Link, NavLink, Outlet, useLocation, useNavigation, useNavigationType } from 'react-router-dom'
import './App.css'
import {
  applyAppearancePreferences,
  readAppearancePreferences,
  saveAppearancePreferences,
} from './preferences'
import { UnsavedChangesProvider } from './components/UnsavedChangesGuard'

const sidebarPreferenceKey = 'learning-flow-coach.sidebar-collapsed'
const sidebarWidthPreferenceKey = 'learning-flow-coach.sidebar-width'
const courseRoutePreferenceKey = 'learning-flow-coach.last-course-route'
const routeProgressDelayMs = 150
const sidebarMinWidth = 144
const sidebarCompactThreshold = 168
const sidebarMaxWidth = 236

function clampSidebarWidth(value: number) {
  return Math.min(sidebarMaxWidth, Math.max(sidebarMinWidth, Math.round(value)))
}

function readSidebarWidth() {
  const savedWidth = Number(localStorage.getItem(sidebarWidthPreferenceKey))
  return Number.isFinite(savedWidth) && savedWidth > 0
    ? clampSidebarWidth(savedWidth)
    : sidebarMaxWidth
}

function isCourseDataPath(pathname: string) {
  return pathname === '/courses'
    || /^\/courses\/\d+$/.test(pathname)
    || /^\/courses\/\d+\/memory$/.test(pathname)
    || /^\/daily-records\/\d+(?:\/note)?$/.test(pathname)
}

function isCourseWorkspacePath(pathname: string) {
  return pathname === '/example' || isCourseDataPath(pathname)
}

function readLastCourseRoute() {
  const savedRoute = sessionStorage.getItem(courseRoutePreferenceKey) ?? ''
  return isCourseDataPath(savedRoute) ? savedRoute : '/courses'
}

export interface AppOutletContext {
  appearance: ReturnType<typeof readAppearancePreferences>
  onAppearanceChange: React.Dispatch<React.SetStateAction<ReturnType<typeof readAppearancePreferences>>>
}

function RouteProgress() {
  const navigation = useNavigation()

  if (navigation.state === 'idle') return null
  return <DelayedRouteProgress />
}

function DelayedRouteProgress() {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const timer = window.setTimeout(() => setVisible(true), routeProgressDelayMs)
    return () => window.clearTimeout(timer)
  }, [])

  return <span className={`route-progress${visible ? ' route-progress--visible' : ''}`} aria-hidden="true" />
}

function App() {
  const location = useLocation()
  const navigationType = useNavigationType()
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => localStorage.getItem(sidebarPreferenceKey) === 'true',
  )
  const [sidebarWidth, setSidebarWidth] = useState(readSidebarWidth)
  const [sidebarResizing, setSidebarResizing] = useState(false)
  const sidebarWidthRef = useRef(sidebarWidth)
  const sidebarResizingRef = useRef(false)
  const appShellRef = useRef<HTMLDivElement>(null)
  const [appearance, setAppearance] = useState(readAppearancePreferences)
  const inCourseWorkspace = isCourseWorkspacePath(location.pathname)
  const savedCourseRoute = readLastCourseRoute()
  const courseNavTarget = inCourseWorkspace ? '/courses' : savedCourseRoute
  const courseNavTitle = inCourseWorkspace && location.pathname !== '/courses'
    ? '返回全部课程'
    : !inCourseWorkspace && savedCourseRoute !== '/courses'
      ? '返回上次课程位置'
      : sidebarCollapsed ? '课程' : undefined

  useEffect(() => {
    localStorage.setItem(sidebarPreferenceKey, String(sidebarCollapsed))
  }, [sidebarCollapsed])

  useLayoutEffect(() => {
    if (navigationType === 'POP' || location.hash) return
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
  }, [location.pathname, location.hash, navigationType])

  function updateSidebarWidth(value: number) {
    const nextWidth = clampSidebarWidth(value)
    sidebarWidthRef.current = nextWidth
    setSidebarWidth(nextWidth)
  }

  function persistSidebarWidth() {
    localStorage.setItem(sidebarWidthPreferenceKey, String(sidebarWidthRef.current))
  }

  function handleSidebarResizeStart(event: ReactPointerEvent<HTMLDivElement>) {
    if (sidebarCollapsed || event.button !== 0) return
    sidebarResizingRef.current = true
    setSidebarResizing(true)
  }

  useEffect(() => {
    if (!sidebarResizing) return

    function handleSidebarResize(event: globalThis.PointerEvent) {
      if (!sidebarResizingRef.current) return
      const shellLeft = appShellRef.current?.getBoundingClientRect().left ?? 0
      const nextWidth = clampSidebarWidth(event.clientX - shellLeft)
      sidebarWidthRef.current = nextWidth
      setSidebarWidth(nextWidth)
    }

    function handleSidebarResizeEnd() {
      if (!sidebarResizingRef.current) return
      sidebarResizingRef.current = false
      setSidebarResizing(false)
      localStorage.setItem(sidebarWidthPreferenceKey, String(sidebarWidthRef.current))
    }

    window.addEventListener('pointermove', handleSidebarResize)
    window.addEventListener('pointerup', handleSidebarResizeEnd)
    window.addEventListener('pointercancel', handleSidebarResizeEnd)

    return () => {
      window.removeEventListener('pointermove', handleSidebarResize)
      window.removeEventListener('pointerup', handleSidebarResizeEnd)
      window.removeEventListener('pointercancel', handleSidebarResizeEnd)
    }
  }, [sidebarResizing])

  function handleSidebarResizeKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const keyWidths: Partial<Record<string, number>> = {
      ArrowLeft: sidebarWidth - 8,
      ArrowRight: sidebarWidth + 8,
      Home: sidebarMinWidth,
      End: sidebarMaxWidth,
    }
    const nextWidth = keyWidths[event.key]
    if (nextWidth === undefined) return
    event.preventDefault()
    updateSidebarWidth(nextWidth)
    window.setTimeout(persistSidebarWidth, 0)
  }

  useEffect(() => {
    applyAppearancePreferences(appearance)
    saveAppearancePreferences(appearance)
  }, [appearance])

  useEffect(() => {
    if (!isCourseDataPath(location.pathname)) return
    sessionStorage.setItem(courseRoutePreferenceKey, location.pathname)
  }, [location.pathname])

  return (
    <UnsavedChangesProvider>
    <div
      ref={appShellRef}
      className={`app-shell${sidebarCollapsed ? ' app-shell--sidebar-collapsed' : ''}${!sidebarCollapsed && sidebarWidth <= sidebarCompactThreshold ? ' app-shell--sidebar-compact' : ''}${sidebarResizing ? ' app-shell--sidebar-resizing' : ''}`}
      style={{ '--sidebar-expanded-width': `${sidebarWidth}px` } as CSSProperties}
    >
      <RouteProgress />
      <aside className="sidebar" aria-label="Lumina 应用侧栏">
        <div className="sidebar-header">
          <div className="brand">
          <span className="brand-mark"><img src="/favicon-192.png" alt="" aria-hidden="true" /></span>
            <span className="brand-label">Lumina</span>
          </div>
          <button
            className="icon-button sidebar-toggle"
            type="button"
            aria-label={sidebarCollapsed ? '展开侧栏' : '收起侧栏'}
            aria-expanded={!sidebarCollapsed}
            title={sidebarCollapsed ? '展开侧栏' : '收起侧栏'}
            onClick={() => setSidebarCollapsed((collapsed) => !collapsed)}
          >
            {sidebarCollapsed
              ? <PanelLeftOpen size={18} aria-hidden="true" />
              : <PanelLeftClose size={18} aria-hidden="true" />}
          </button>
        </div>
        <nav aria-label="主导航">
          <Link
            className={`nav-link${inCourseWorkspace ? ' active' : ''}`}
            to={courseNavTarget}
            title={courseNavTitle}
            aria-current={inCourseWorkspace ? 'page' : undefined}
          >
            <Library size={18} aria-hidden="true" />
            <span className="nav-label">课程</span>
          </Link>
          <NavLink className="nav-link" to="/mistakes" title={sidebarCollapsed ? '错题' : undefined}>
            <BookX size={18} aria-hidden="true" />
            <span className="nav-label">错题</span>
          </NavLink>
          <NavLink className="nav-link" to="/notes" title={sidebarCollapsed ? '笔记' : undefined}>
            <NotebookPen size={18} aria-hidden="true" />
            <span className="nav-label">笔记</span>
          </NavLink>
          <NavLink className="nav-link" to="/settings" title={sidebarCollapsed ? '设置' : undefined}>
            <Settings size={18} aria-hidden="true" />
            <span className="nav-label">设置</span>
          </NavLink>
        </nav>
        <p className="sidebar-footnote">本地学习工作台</p>
        <div
          className="sidebar-resizer"
          role="separator"
          aria-label="调整侧栏宽度"
          aria-orientation="vertical"
          aria-valuemin={sidebarMinWidth}
          aria-valuemax={sidebarMaxWidth}
          aria-valuenow={sidebarWidth}
          aria-valuetext={`${sidebarWidth} 像素`}
          tabIndex={sidebarCollapsed ? -1 : 0}
          onPointerDown={handleSidebarResizeStart}
          onKeyDown={handleSidebarResizeKeyDown}
        />
      </aside>

      <Outlet context={{ appearance, onAppearanceChange: setAppearance } satisfies AppOutletContext} />
    </div>
    </UnsavedChangesProvider>
  )
}

export default App

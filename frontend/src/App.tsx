import { useEffect, useState } from 'react'
import { BookX, Library, NotebookPen, PanelLeftClose, PanelLeftOpen, Settings } from 'lucide-react'
import { Link, NavLink, Outlet, useLocation, useNavigation } from 'react-router-dom'
import './App.css'
import {
  applyAppearancePreferences,
  readAppearancePreferences,
  saveAppearancePreferences,
} from './preferences'
import { UnsavedChangesProvider } from './components/UnsavedChangesGuard'

const sidebarPreferenceKey = 'learning-flow-coach.sidebar-collapsed'
const courseRoutePreferenceKey = 'learning-flow-coach.last-course-route'
const routeProgressDelayMs = 150

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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => localStorage.getItem(sidebarPreferenceKey) === 'true',
  )
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
    <div className={`app-shell${sidebarCollapsed ? ' app-shell--sidebar-collapsed' : ''}`}>
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
      </aside>

      <Outlet context={{ appearance, onAppearanceChange: setAppearance } satisfies AppOutletContext} />
    </div>
    </UnsavedChangesProvider>
  )
}

export default App

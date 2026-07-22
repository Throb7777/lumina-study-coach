import { Check, CircleAlert, Server } from 'lucide-react'
import { useLoaderData } from 'react-router-dom'
import type { StatusRouteData } from '../routeData'

export function StatusPage() {
  const { health } = useLoaderData() as StatusRouteData
  const healthState = health ? 'online' : 'offline'

  const statusContent = {
    online: {
      icon: <Check className="status-icon" aria-hidden="true" />,
      title: '后端已连接',
      detail: health ? `Lumina 本地服务 · v${health.version}` : '本地服务运行正常。',
    },
    offline: {
      icon: <CircleAlert className="status-icon" aria-hidden="true" />,
      title: '后端未连接',
      detail: '请先启动 FastAPI，再刷新此页面。',
    },
  }[healthState]

  return (
    <main className="content content--workspace">
      <header className="page-heading">
        <p className="eyebrow">本地应用</p>
        <h1>运行状态</h1>
        <p className="page-summary">检查前端、后端与本地数据服务是否正常连接。</p>
      </header>
      <section className={`status-panel status-panel--${healthState}`} aria-live="polite">
        <div className="status-mark">{statusContent.icon}</div>
        <div>
          <h2>{statusContent.title}</h2>
          <p>{statusContent.detail}</p>
        </div>
      </section>
      <section className="foundation" aria-labelledby="foundation-title">
        <div className="section-heading">
          <Server size={18} aria-hidden="true" />
          <h2 id="foundation-title">基础环境</h2>
        </div>
        <ul>
          <li><Check size={16} aria-hidden="true" /> React 单页应用</li>
          <li><Check size={16} aria-hidden="true" /> FastAPI 本地服务</li>
          <li><Check size={16} aria-hidden="true" /> SQLite 数据存储</li>
        </ul>
      </section>
    </main>
  )
}

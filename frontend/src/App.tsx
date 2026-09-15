import { useEffect, useMemo, useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import { MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import {
  Activity, BatteryCharging, ChevronRight, CircleAlert, Clock3, Crosshair,
  Gauge, LocateFixed, MapPin, Radio, RefreshCw, Search, ShieldCheck, Wifi,
  WifiOff, X,
} from 'lucide-react'
import 'leaflet/dist/leaflet.css'
import './App.css'

type DeviceStatus = 'active' | 'idle' | 'maintenance' | 'offline' | 'error'
type Device = {
  device_id: string
  status: DeviceStatus
  latitude: number | null
  longitude: number | null
  battery_level: number | null
  sensor_timestamp: string | null
  updated_at: string | null
}
type FleetResponse = { total: number; items: Device[] }

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const WS_URL = API_URL.replace(/^http/, 'ws')
const statusLabels: Record<DeviceStatus, string> = { active: 'Ativo', idle: 'Parado', maintenance: 'Manutenção', offline: 'Offline', error: 'Atenção' }
const markerColors: Record<DeviceStatus, string> = { active: '#1f9d72', idle: '#d18d24', maintenance: '#3f77c5', offline: '#83909b', error: '#d6534b' }

function markerIcon(status: DeviceStatus) {
  return L.divIcon({ className: 'device-marker-wrap', html: `<span class="device-marker" style="--marker-color: ${markerColors[status]}"><span></span></span>`, iconSize: [32, 40], iconAnchor: [16, 40] })
}

function MapRecenter({ device }: { device: Device | null }) {
  const map = useMap()
  useEffect(() => {
    if (device && device.latitude !== null && device.longitude !== null) map.flyTo([device.latitude, device.longitude], 13, { duration: 0.7 })
  }, [device, map])
  return null
}

function formatTime(timestamp: string | null) {
  if (!timestamp) return 'Sem leitura'
  return new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' }).format(new Date(timestamp))
}

function formatRelativeTime(timestamp: string | null) {
  if (!timestamp) return 'sem dados'
  const minutes = Math.max(0, Math.round((Date.now() - new Date(timestamp).getTime()) / 60000))
  if (minutes < 1) return 'agora'
  return `há ${minutes} min`
}

function App() {
  const [devices, setDevices] = useState<Device[]>([])
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<DeviceStatus | 'all'>('all')
  const [apiConnected, setApiConnected] = useState(false)
  const [socketConnected, setSocketConnected] = useState(false)
  const [loading, setLoading] = useState(true)
  const [lastSync, setLastSync] = useState<Date | null>(null)

  const loadDevices = async (showLoading = true) => {
    if (showLoading) setLoading(true)
    try {
      const response = await fetch(`${API_URL}/devices?limit=100`)
      if (!response.ok) throw new Error('Falha ao carregar a frota')
      const data = (await response.json()) as FleetResponse
      setDevices(data.items); setApiConnected(true); setLastSync(new Date())
    } catch { setApiConnected(false) } finally { setLoading(false) }
  }

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void loadDevices(false), 0)
    return () => window.clearTimeout(initialLoad)
  }, [])

  useEffect(() => {
    let socket: WebSocket | null = null
    let retryTimer: number | undefined
    let stopped = false
    const connect = () => {
      socket = new WebSocket(`${WS_URL}/ws/fleet`)
      socket.onopen = () => setSocketConnected(true)
      socket.onclose = () => { setSocketConnected(false); if (!stopped) retryTimer = window.setTimeout(connect, 3000) }
      socket.onerror = () => setSocketConnected(false)
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as { type: 'snapshot' | 'telemetry_update'; data: Device[] | Device }
          if (message.type === 'snapshot') { setDevices(message.data as Device[]); setLastSync(new Date()) }
          if (message.type === 'telemetry_update') {
            const update = message.data as Device
            setDevices((current) => current.some((device) => device.device_id === update.device_id) ? current.map((device) => device.device_id === update.device_id ? update : device) : [...current, update])
            setSelectedDevice((current) => current?.device_id === update.device_id ? update : current); setLastSync(new Date())
          }
        } catch { /* Ignora mensagens fora do contrato do painel. */ }
      }
    }
    connect()
    return () => { stopped = true; if (retryTimer) window.clearTimeout(retryTimer); socket?.close() }
  }, [])

  const filteredDevices = useMemo(() => devices.filter((device) => device.device_id.toLowerCase().includes(search.toLowerCase()) && (statusFilter === 'all' || device.status === statusFilter)), [devices, search, statusFilter])
  const counts = useMemo(() => devices.reduce((summary, device) => { summary[device.status] += 1; return summary }, { active: 0, idle: 0, maintenance: 0, offline: 0, error: 0 } as Record<DeviceStatus, number>), [devices])

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-lockup"><div className="brand-mark"><Radio size={18} /></div><div><strong>FleetPulse</strong><span>Command center</span></div></div>
        <div className="topbar-actions">
          <div className={`connection-pill ${apiConnected ? 'is-online' : ''}`}>{apiConnected ? <Wifi size={14} /> : <WifiOff size={14} />}<span>API {apiConnected ? 'online' : 'indisponível'}</span></div>
          <div className={`connection-pill ${socketConnected ? 'is-online' : ''}`}><span className="pulse-dot" /><span>Realtime {socketConnected ? 'conectado' : 'reconectando'}</span></div>
          <button className="icon-button" onClick={() => void loadDevices()} title="Atualizar frota"><RefreshCw size={17} /></button>
        </div>
      </header>

      <section className="page-heading"><div><p className="eyebrow">Operações / Visão geral</p><h1>Mapa da frota</h1><p className="heading-copy">Acompanhe os ativos em campo e responda antes que um sinal vire incidente.</p></div><div className="sync-note"><Clock3 size={15} /><span>Sincronizado {lastSync ? formatTime(lastSync.toISOString()) : 'aguardando'}</span></div></section>

      <section className="metric-grid" aria-label="Resumo da frota">
        <MetricCard icon={<Gauge size={18} />} label="Total em campo" value={devices.length} tone="ink" />
        <MetricCard icon={<Activity size={18} />} label="Ativos" value={counts.active} tone="green" />
        <MetricCard icon={<Clock3 size={18} />} label="Parados" value={counts.idle} tone="amber" />
        <MetricCard icon={<CircleAlert size={18} />} label="Atenção" value={counts.error + counts.offline} tone="red" />
      </section>

      <section className="workspace-grid">
        <div className="map-panel"><div className="panel-heading map-heading"><div><span className="section-kicker"><MapPin size={13} /> Posicionamento ao vivo</span><h2>Ativos em campo</h2></div><div className="map-legend"><span><i className="legend-dot active" /> Ativo</span><span><i className="legend-dot warning" /> Parado</span></div></div>
          <div className="map-frame"><MapContainer center={[-23.55, -46.63]} zoom={11} zoomControl={false} scrollWheelZoom><TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" /><MapRecenter device={selectedDevice} />{devices.map((device) => device.latitude !== null && device.longitude !== null ? <Marker key={device.device_id} position={[device.latitude, device.longitude]} icon={markerIcon(device.status)} eventHandlers={{ click: () => setSelectedDevice(device) }}><Popup><strong>{device.device_id}</strong><br />{statusLabels[device.status]} · {device.battery_level ?? '--'}% bateria</Popup></Marker> : null)}</MapContainer>
            {devices.length === 0 && !loading && <div className="map-empty"><div className="empty-icon"><LocateFixed size={20} /></div><strong>Nenhum ativo localizado</strong><span>Aguardando a primeira telemetria da frota.</span></div>}{loading && <div className="map-loading"><RefreshCw size={18} className="spin" /> Carregando mapa</div>}<div className="map-control"><Crosshair size={17} /></div>
          </div>
        </div>

        <aside className="fleet-panel"><div className="panel-heading"><div><span className="section-kicker"><ShieldCheck size={13} /> Inventário</span><h2>Dispositivos</h2></div><span className="count-badge">{filteredDevices.length}</span></div><div className="search-field"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar dispositivo" /></div><div className="filter-row">{(['all', 'active', 'idle', 'error'] as const).map((filter) => <button className={statusFilter === filter ? 'filter-chip selected' : 'filter-chip'} key={filter} onClick={() => setStatusFilter(filter)}>{filter === 'all' ? 'Todos' : statusLabels[filter]}</button>)}</div><div className="device-list">{filteredDevices.length > 0 ? filteredDevices.map((device) => <button className={`device-row ${selectedDevice?.device_id === device.device_id ? 'selected' : ''}`} key={device.device_id} onClick={() => setSelectedDevice(device)}><span className="device-avatar" style={{ '--avatar-color': markerColors[device.status] } as CSSProperties}><Radio size={16} /></span><span className="device-info"><strong>{device.device_id}</strong><span><i className={`status-dot ${device.status}`} /> {statusLabels[device.status]} · {formatRelativeTime(device.updated_at)}</span></span><ChevronRight size={16} className="row-arrow" /></button>) : <div className="list-empty"><Search size={19} /><strong>{devices.length ? 'Nenhum resultado' : 'Frota vazia'}</strong><span>{devices.length ? 'Tente outro identificador ou status.' : 'Os dispositivos aparecerão após a primeira telemetria.'}</span></div>}</div></aside>
      </section>
      {selectedDevice && <DeviceDrawer device={selectedDevice} onClose={() => setSelectedDevice(null)} />}
    </main>
  )
}

function MetricCard({ icon, label, value, tone }: { icon: ReactNode; label: string; value: number; tone: string }) { return <div className="metric-card"><span className={`metric-icon ${tone}`}>{icon}</span><span className="metric-label">{label}</span><strong>{value.toString().padStart(2, '0')}</strong></div> }
function DeviceDrawer({ device, onClose }: { device: Device; onClose: () => void }) { return <div className="drawer-backdrop" onClick={onClose}><aside className="device-drawer" onClick={(event) => event.stopPropagation()}><div className="drawer-topline"><span className="section-kicker"><Radio size={13} /> Unidade selecionada</span><button className="icon-button" onClick={onClose} title="Fechar detalhes"><X size={18} /></button></div><div className="drawer-title"><span className="large-device-icon" style={{ '--avatar-color': markerColors[device.status] } as CSSProperties}><Radio size={22} /></span><div><h2>{device.device_id}</h2><span className={`status-label ${device.status}`}><i className="status-dot" /> {statusLabels[device.status]}</span></div></div><div className="detail-grid"><Detail label="Bateria" value={`${device.battery_level ?? '--'}%`} icon={<BatteryCharging size={16} />} /><Detail label="Última leitura" value={formatTime(device.sensor_timestamp)} icon={<Clock3 size={16} />} /><Detail label="Latitude" value={device.latitude?.toFixed(5) ?? '--'} icon={<MapPin size={16} />} /><Detail label="Longitude" value={device.longitude?.toFixed(5) ?? '--'} icon={<MapPin size={16} />} /></div><div className="drawer-footer"><span>Estado consolidado pelo FleetPulse</span><span>{formatRelativeTime(device.updated_at)}</span></div></aside></div> }
function Detail({ label, value, icon }: { label: string; value: string; icon: ReactNode }) { return <div className="detail-item"><span>{icon}{label}</span><strong>{value}</strong></div> }

export default App

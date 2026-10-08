'use client'

import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js'
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'

/**
 * Agentic Factory — Interactive 3D Machine
 *
 * A short-video factory that AI agents build, as one machine you can spin:
 * order → script → video → post → payment across five stations on a metal plate.
 * Four modes (Assembled, Cutaway, Stations, One order), five cameras, hover and
 * click stations. Procedural three.js: no models, no images.
 *
 * Built by OpenAI Codex (GPT-6 Astra) from a single prompt; ported to React by Claude.
 * Live demo: https://agentic-factory-3d.vercel.app · Next.js template: https://github.com/eugeneshilow/agentic-3d-templates
 * Made with AI agents · https://vibecoding.tech
 */

export type AgenticFactory3DProps = {
  height?: number | string
  className?: string
  embed?: boolean
  onStation?: (id: StationId) => void
  onReady?: () => void
}

export default function AgenticFactory3D({
  height = '100vh',
  className,
  embed = false,
  onStation,
  onReady,
}: AgenticFactory3DProps) {
  const rootRef = useRef<HTMLDivElement>(null)
  const handlers = useRef({ onStation, onReady })
  useEffect(() => {
    handlers.current = { onStation, onReady }
  }, [onStation, onReady])

  useEffect(() => {
    const root = rootRef.current
    if (!root) return
    let dispose: (() => void) | undefined
    let cancelled = false
    document.fonts.ready.then(() => {
      if (cancelled) return
      dispose = initMachineScene(root, getComputedStyle(root).fontFamily, {
        embedded: embed,
        onStation: (id) => handlers.current.onStation?.(id),
        onReady: () => handlers.current.onReady?.(),
      })
    })
    return () => {
      cancelled = true
      dispose?.()
    }
  }, [embed])

  return (
    <div
      ref={rootRef}
      className={['agentic-factory-3d', embed && 'embed', className].filter(Boolean).join(' ')}
      style={{ height }}
    >
      <style dangerouslySetInnerHTML={{ __html: STYLES }} />
      <div
        id="scene"
        role="img"
        aria-label="Interactive 3D machine with five stations: Engine, Admin, Storefront, Cabinet and Checkout. Drag to rotate, scroll or pinch to zoom. Hover or tap a station to take a closer look."
      />
      <div className="vignette" />
      <header className="topbar debug-ui">
        <div className="identity">
          <div className="mark">
            <svg width="17" height="17" viewBox="0 0 20 20" fill="none">
              <path
                d="M3 5l7 11 7-11M7 5l3 5 3-5"
                stroke="currentColor"
                strokeWidth="1.7"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <div>
            <strong>Agentic Factory</strong>
            <small>Interactive workshop</small>
          </div>
        </div>
        <div className="status" id="status">
          <i />
          <span id="status-text">Machine running</span>
          <span>SERIES 001</span>
        </div>
      </header>
      <div className="scene-heading debug-ui">
        The machine you will build <span className="index">5 MODULES / 1 SYSTEM</span>
      </div>
      <div className="coordinates debug-ui">PROTOTYPE 01 — FROM IDEA TO PAYMENT</div>
      <div id="journey" className="debug-ui">
        <div className="journey-icon">
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
            <path d="M3 4h10v9H3zM6 4V2h4v2m-5 4h6" stroke="currentColor" strokeLinejoin="round" />
          </svg>
        </div>
        <div>
          <strong id="journey-title">New order</strong>
          <small id="journey-detail">Cabinet · an order from Anna</small>
        </div>
        <div className="track">
          <i id="journey-progress" />
        </div>
      </div>
      <div id="labels" />
      <div id="tooltip" role="tooltip">
        <strong />
        <p />
      </div>
      <div className="controls debug-ui">
        <nav className="mode-bar" aria-label="Machine mode">
          <button data-mode="assembled" aria-pressed="true">
            <svg viewBox="0 0 16 16" fill="none">
              <path
                d="M8 1.5l6 3.3v6.4l-6 3.3-6-3.3V4.8L8 1.5zM2 4.8l6 3.4 6-3.4M8 8.2v6.3"
                stroke="currentColor"
                strokeLinejoin="round"
              />
            </svg>
            Assembled
          </button>
          <button data-mode="cutaway" aria-pressed="false">
            <svg viewBox="0 0 16 16" fill="none">
              <path
                d="M3 2h10v12H3zM8 2v12M10.5 4l2.5 2.5m-2.5 0L13 9m-2.5 0 2.5 2.5"
                stroke="currentColor"
                strokeLinejoin="round"
              />
            </svg>
            Cutaway
          </button>
          <button data-mode="stations" aria-pressed="false">
            <svg viewBox="0 0 16 16" fill="none">
              <path
                d="M8 1.5l6 3-6 3-6-3 6-3zM2 8l6 3 6-3M2 11.5l6 3 6-3"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            Stations
          </button>
          <button data-mode="order" aria-pressed="false">
            <svg viewBox="0 0 16 16" fill="none">
              <path d="M5 2.5l8 5.5-8 5.5v-11z" stroke="currentColor" strokeLinejoin="round" />
            </svg>
            One order
          </button>
        </nav>
        <nav className="camera-row" aria-label="Camera">
          <span className="caption">VIEW</span>
          <button data-camera="overview" aria-pressed="true">Overview</button>
          <button data-camera="side" aria-pressed="false">Side</button>
          <button data-camera="top" aria-pressed="false">Top</button>
          <button data-camera="station" aria-pressed="false">Station</button>
          <button data-camera="flight" aria-pressed="false">Flight</button>
          <span className="divider" />
          <button id="play" aria-label="Pause the animation" aria-pressed="false">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
              <rect x="2" y="1" width="2.5" height="10" rx=".5" />
              <rect x="7.5" y="1" width="2.5" height="10" rx=".5" />
            </svg>
          </button>
        </nav>
      </div>
      <footer className="footer">
        <a className="wordmark" href="https://vibecoding.tech" target="_blank" rel="noopener">
          made with AI agents · <span>vibecoding.tech</span>
        </a>
        <span className="footer-center debug-ui">DESIGNED BY YOU</span>
        <span className="hint debug-ui">
          <svg width="13" height="16" viewBox="0 0 13 16" fill="none">
            <rect x="2" y="1" width="9" height="14" rx="4.5" stroke="currentColor" />
            <path d="M6.5 4v3" stroke="currentColor" strokeLinecap="round" />
          </svg>
          Rotate. Zoom. Explore.
        </span>
      </footer>
      <div id="loading">
        <i />
        <span>Assembling your machine</span>
      </div>
      <div id="error" role="alert">
        <strong>Could not start the 3D scene</strong>
        <p>Check that WebGL is turned on in your browser.</p>
        <button onClick={() => location.reload()}>Try again</button>
      </div>
    </div>
  )
}


export type MachineMode = 'assembled' | 'cutaway' | 'stations' | 'order'
export type MachineCamera = 'overview' | 'side' | 'top' | 'station' | 'flight'
export type StationId = 'engine' | 'admin' | 'storefront' | 'cabinet' | 'cashdesk'

export type MachineApi = {
  setMode: (name: string) => boolean
  focusStation: (id: string) => boolean
  setCamera: (name: string) => boolean
  play: () => boolean
  pause: () => boolean
}

declare global {
  interface Window {
    __machine?: MachineApi
    __machineDebug?: { getState: () => Record<string, unknown> }
  }
}

export type MachineSceneOptions = {
  embedded: boolean
  onStation?: (id: StationId) => void
  onReady?: () => void
}

function initMachineScene(
  root: HTMLElement,
  fontFamily: string,
  options: MachineSceneOptions
): () => void {
  const cleanups: Array<() => void> = []
  const frameWidth = () => root.clientWidth
  const frameHeight = () => root.clientHeight
  const listen = (target: EventTarget, type: string, handler: (event: never) => void) => {
    const fn = handler as unknown as EventListener
    target.addEventListener(type, fn)
    cleanups.push(() => target.removeEventListener(type, fn))
  }
  function $<T extends HTMLElement = HTMLElement>(id: string): T {
    const el = root.querySelector<T>(`#${id}`)
    if (!el) throw new Error(`Scene markup is missing #${id}`)
    return el
  }
  function showError(message?: string) {
    $('loading').classList.add('done')
    $('error').style.display = 'block'
    if (message) $('error').querySelector('p')!.textContent = message
  }
  const dispose = () => {
    for (const fn of cleanups.reverse()) fn()
    cleanups.length = 0
  }
  try {
    const TAU = Math.PI * 2
    const embedded = options.embedded
    const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches
    const palette = { amber: 0xff7a1a, white: 0xf4f1ea, dark: 0x171b21, steel: 0x59616b }
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(33, frameWidth() / frameHeight(), 0.1, 150)
    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,
        powerPreference: 'high-performance',
      })
    } catch (e) {
      showError('WebGL is not available. Turn on hardware acceleration in your browser settings and reload the page.')
      throw e
    }
    renderer.setClearColor(0x000000, 0)
    renderer.setPixelRatio(Math.min(devicePixelRatio, frameWidth() < 900 ? 1.5 : 1.75))
    renderer.setSize(frameWidth(), frameHeight())
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.12
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFShadowMap
    renderer.localClippingEnabled = true
    $('scene').appendChild(renderer.domElement)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.065
    controls.enablePan = false
    controls.minDistance = 7
    controls.maxDistance = 55
    controls.minPolarAngle = 0.09
    controls.maxPolarAngle = Math.PI * 0.475
    controls.rotateSpeed = 0.48
    controls.zoomSpeed = 0.7
    if (embedded) {
      controls.enableZoom = false
      if (matchMedia('(pointer:coarse)').matches) controls.enableRotate = false
    }
    const pmrem = new THREE.PMREMGenerator(renderer), room = new RoomEnvironment()
    const env = pmrem.fromScene(room, 0.04)
    scene.environment = env.texture
    scene.environmentIntensity = 0.62
    room.dispose()
    pmrem.dispose()
    scene.add(new THREE.HemisphereLight(0xdbe5f4, 0x29211a, 2))
    const key = new THREE.DirectionalLight(0xfff1d8, 4.2)
    key.position.set(-4, 12, 7)
    key.castShadow = true
    key.shadow.mapSize.set(2048, 2048)
    Object.assign(key.shadow.camera, { left: -10, right: 10, top: 9, bottom: -9, near: 0.5, far: 35 })
    key.shadow.normalBias = 0.035
    key.shadow.bias = -0.0002
    key.shadow.radius = 4
    scene.add(key)
    const rim = new THREE.DirectionalLight(0xc4d4ed, 3.1)
    rim.position.set(3, 7, -8)
    scene.add(rim)
    const warm = new THREE.PointLight(0xffbd42, 28, 20, 2)
    warm.position.set(-4, 5, 3)
    scene.add(warm)
    const front = new THREE.DirectionalLight(0xffffff, 1)
    front.position.set(5, 3, 10)
    scene.add(front)

    const mat = (color: number, metalness = 0.1, roughness = 0.4, extra: THREE.MeshStandardMaterialParameters = {}) =>
      new THREE.MeshStandardMaterial({ color, metalness, roughness, ...extra })
    const M = {
      body: mat(0x30363f, 0.75, 0.29),
      base: mat(0x292f37, 0.85, 0.32),
      edge: mat(0x707986, 0.85, 0.24),
      chrome: mat(0xc3cad0, 0.92, 0.18),
      dark: mat(0x12171d, 0.45, 0.38),
      rubber: mat(0x0b1015, 0.1, 0.6),
      amber: mat(palette.amber, 0.52, 0.28),
      ivory: mat(0xe0ded4, 0.48, 0.26),
      copper: mat(0xc57e45, 0.85, 0.3),
      black: mat(0x050909, 0, 0.6),
      light: mat(0xff7a1a, 0.2, 0.25, { emissive: 0xff7a1a, emissiveIntensity: 1.5 }),
      whiteLight: mat(0xfff3d7, 0.1, 0.3, { emissive: 0xfff0d0, emissiveIntensity: 1.8 }),
      green: mat(0xc6d9a1, 0.1, 0.3, { emissive: 0x91b364, emissiveIntensity: 0.7 }),
      glass: mat(0x81949e, 0.45, 0.16, { transparent: true, opacity: 0.19, depthWrite: false }),
      paper: mat(0xf4f1ea, 0, 0.85),
    }
    type Vec3 = [number, number, number]
    type Material = THREE.Material
    const geometries = new Map<string, THREE.BufferGeometry>()
    function boxGeo(w: number, h: number, d: number, r = 0.04) {
      const k = `b${w},${h},${d},${r}`
      if (!geometries.has(k))
        geometries.set(k, r ? new RoundedBoxGeometry(w, h, d, 2, Math.min(r, w / 3, h / 3, d / 3)) : new THREE.BoxGeometry(w, h, d))
      return geometries.get(k)!
    }
    function box(parent: THREE.Object3D, w: number, h: number, d: number, x: number, y: number, z: number, m: Material = M.body, r = 0.04) {
      const o = new THREE.Mesh(boxGeo(w, h, d, r), m)
      o.position.set(x, y, z)
      o.castShadow = true
      o.receiveShadow = true
      parent.add(o)
      return o
    }
    function cyl(parent: THREE.Object3D, r: number, h: number, x: number, y: number, z: number, m: Material = M.chrome, r2: number = r, segments = 24) {
      const k = `c${r},${r2},${h},${segments}`
      if (!geometries.has(k)) geometries.set(k, new THREE.CylinderGeometry(r, r2, h, segments))
      const o = new THREE.Mesh(geometries.get(k)!, m)
      o.position.set(x, y, z)
      o.castShadow = true
      o.receiveShadow = true
      parent.add(o)
      return o
    }
    function ball(parent: THREE.Object3D, r: number, x: number, y: number, z: number, m: Material = M.chrome) {
      const k = `s${r}`
      if (!geometries.has(k)) geometries.set(k, new THREE.SphereGeometry(r, 12, 8))
      const o = new THREE.Mesh(geometries.get(k)!, m)
      o.position.set(x, y, z)
      parent.add(o)
      return o
    }
    function tube(parent: THREE.Object3D, pts: Vec3[], r: number, m: Material = M.chrome) {
      const curve = new THREE.CatmullRomCurve3(pts.map((p) => new THREE.Vector3(...p)))
      const o = new THREE.Mesh(new THREE.TubeGeometry(curve, Math.max(12, pts.length * 7), r, 8, false), m)
      o.castShadow = true
      parent.add(o)
      return o
    }
    function screw(parent: THREE.Object3D, x: number, y: number, z: number) {
      cyl(parent, 0.055, 0.026, x, y, z, M.chrome, undefined, 12)
      box(parent, 0.068, 0.005, 0.009, x, y + 0.014, z, M.dark, 0)
    }
    type Draw = (ctx: CanvasRenderingContext2D, w: number, h: number) => void
    function canvasTexture(w: number, h: number, draw: Draw) {
      const c = document.createElement('canvas')
      c.width = w
      c.height = h
      const ctx = c.getContext('2d')!
      draw(ctx, w, h)
      const t = new THREE.CanvasTexture(c)
      t.colorSpace = THREE.SRGBColorSpace
      t.anisotropy = Math.min(4, renderer.capabilities.getMaxAnisotropy())
      return { texture: t, canvas: c, ctx }
    }
    function print(ctx: CanvasRenderingContext2D, txt: string, x: number, y: number, size = 20, color = '#f4f1ea', weight = 500) {
      ctx.fillStyle = color
      ctx.font = `${weight} ${size}px ${fontFamily}`
      ctx.fillText(txt, x, y)
    }
    function screenMaterial(texture: THREE.Texture) {
      return new THREE.MeshBasicMaterial({ map: texture, toneMapped: false })
    }
    type Painted = THREE.Texture | { texture: THREE.Texture }
    function screen(parent: THREE.Object3D, w: number, h: number, x: number, y: number, z: number, tex: Painted) {
      const map = 'texture' in tex ? tex.texture : tex
      const o = new THREE.Mesh(new THREE.PlaneGeometry(w, h), screenMaterial(map))
      o.position.set(x, y, z)
      parent.add(o)
      return o
    }
    const machine = new THREE.Group()
    scene.add(machine)
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(70, 70), new THREE.ShadowMaterial({ opacity: 0.23 }))
    floor.rotation.x = -Math.PI / 2
    floor.position.y = -0.43
    floor.receiveShadow = true
    scene.add(floor)
    const shadow = canvasTexture(128, 128, (c, w, h) => {
      const g = c.createRadialGradient(64, 64, 12, 64, 64, 64)
      g.addColorStop(0, 'rgba(0,0,0,.8)')
      g.addColorStop(0.55, 'rgba(0,0,0,.45)')
      g.addColorStop(1, 'rgba(0,0,0,0)')
      c.fillStyle = g
      c.fillRect(0, 0, w, h)
    })
    const contact = new THREE.Mesh(
      new THREE.PlaneGeometry(18, 13),
      new THREE.MeshBasicMaterial({ map: shadow.texture, transparent: true, depthWrite: false, opacity: 0.65 })
    )
    contact.rotation.x = -Math.PI / 2
    contact.position.y = -0.415
    scene.add(contact)
    box(machine, 12.8, 0.38, 8.25, 0, -0.09, 0, M.base, 0.17)
    box(machine, 12.6, 0.055, 8.08, 0, 0.13, 0, M.edge, 0.11)
    box(machine, 12.49, 0.09, 7.96, 0, 0.19, 0, M.body, 0.1)
    box(machine, 12.55, 0.027, 8.02, 0, -0.19, 0, M.dark, 0.06)
    box(machine, 11.9, 0.026, 0.032, 0, -0.17, 4.115, M.light, 0.01)
    for (const x of [-5.6, 5.6])
      for (const z of [-3.35, 3.35]) {
        cyl(machine, 0.39, 0.25, x, -0.31, z, M.rubber)
        cyl(machine, 0.29, 0.09, x, -0.4, z, M.dark)
        screw(machine, x, 0.253, z)
      }
    for (const x of [-6.02, 6.02]) for (const z of [-3.73, 3.73]) screw(machine, x, 0.255, z)
    const engraving = canvasTexture(1536, 176, (c, w, h) => {
      c.fillStyle = '#252b32'
      c.fillRect(0, 0, w, h)
      c.strokeStyle = '#4d545c'
      c.lineWidth = 2
      c.strokeRect(2, 2, w - 4, h - 4)
      print(c, 'STARTER', 45, 79, 40, '#d9d8cd', 650)
      print(c, '·  site  ·  database  ·  admin in 35 minutes', 285, 79, 34, '#b8bdc1', 450)
      print(c, 'AGENTIC ENGINEERING    /    YOUR FIRST PRODUCT', 47, 133, 19, '#737e88', 500)
      print(c, 'No. 001', 1360, 130, 23, '#c57e45')
    })
    const plate = screen(machine, 7.35, 0.84, -0.4, 0.25, 3.51, engraving)
    plate.rotation.x = -Math.PI / 2
    for (let i = 0; i < 16; i++)
      box(machine, 0.015, 0.009, 0.11 + (i % 4) * 0.035, -5.6 + i * 0.09, 0.249, 3.5, M.edge, 0)
    const drafting = new THREE.Group()
    scene.add(drafting)
    const lineMat = new THREE.LineBasicMaterial({ color: 0x69717a, transparent: true, opacity: 0.12 })
    const draftingPoints = []
    for (const r of [7.5, 8.1])
      for (let i = 0; i < 120; i++)
        for (const j of [i, i + 1]) {
          const a = (j / 120) * TAU
          draftingPoints.push(new THREE.Vector3(Math.cos(a) * r, -0.4, Math.sin(a) * r * 0.72))
        }
    for (let i = 0; i < 52; i++) {
      const a = (i / 52) * TAU, r = 8.1
      draftingPoints.push(
        new THREE.Vector3(Math.cos(a) * r, -0.395, Math.sin(a) * r * 0.72),
        new THREE.Vector3(Math.cos(a) * (r + (i % 4 === 0 ? 0.16 : 0.07)), -0.395, Math.sin(a) * (r + (i % 4 === 0 ? 0.16 : 0.07)) * 0.72)
      )
    }
    drafting.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(draftingPoints), lineMat))

    type StationDef = { id: StationId; name: string; step: number; output: string; pos: Vec3; desc: string }
    type Station = StationDef & { group: THREE.Group; base: THREE.Vector3; glowMat: THREE.MeshStandardMaterial; label: HTMLDivElement; index: number; anchor: THREE.Vector3 }
    const definitions: StationDef[] = [
      { id: 'engine', name: 'Engine', step: 2, output: 'script', pos: [-4.15, 0.29, -0.65], desc: 'Script, voice, subtitles, and a finished video.' },
      { id: 'admin', name: 'Admin', step: 3, output: 'video', pos: [-1.65, 0.29, -2.03], desc: 'The video queue and control over the whole system.' },
      { id: 'storefront', name: 'Storefront', step: 4, output: 'post', pos: [1.5, 0.29, -2.08], desc: 'The finished video becomes part of the product.' },
      { id: 'cabinet', name: 'Cabinet', step: 1, output: 'order', pos: [4.03, 0.29, 0.12], desc: 'Customers, new orders and the work history.' },
      { id: 'cashdesk', name: 'Checkout', step: 5, output: 'payment', pos: [0.93, 0.29, 1.85], desc: 'Payment received. Receipt printed. The machine runs.' },
    ]
    const stations: Station[] = [], cutPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 10), shellMaterials: THREE.Material[] = []
    function shell<T extends THREE.Material>(m: T): T {
      const s = m.clone() as T
      s.clippingPlanes = [cutPlane]
      s.clipShadows = true
      s.side = THREE.DoubleSide
      shellMaterials.push(s)
      return s
    }
    const S = { body: shell(M.body), ivory: shell(M.ivory), amber: shell(M.amber), edge: shell(M.edge) }
    const gears: Array<{ g: THREE.Group; vertical: boolean }> = []
    function gear(parent: THREE.Object3D, x: number, y: number, z: number, r = 0.3, vertical = false) {
      const g = new THREE.Group()
      g.position.set(x, y, z)
      if (vertical) g.rotation.x = Math.PI / 2
      parent.add(g)
      cyl(g, r, 0.09, 0, 0, 0, M.copper)
      cyl(g, r * 0.66, 0.105, 0, 0, 0, M.dark)
      cyl(g, r * 0.22, 0.14, 0, 0, 0, M.chrome)
      for (let i = 0; i < 12; i++) {
        const a = (i / 12) * TAU, b = box(g, r * 0.26, 0.085, r * 0.2, Math.cos(a) * r, 0, Math.sin(a) * r, M.copper, 0.008)
        b.rotation.y = -a
      }
      g.userData.moving = true
      gears.push({ g, vertical })
      return g
    }
    definitions.forEach((d, i) => {
      const group = new THREE.Group()
      group.position.fromArray(d.pos)
      machine.add(group)
      const glowMat = M.light.clone()
      glowMat.emissiveIntensity = 0.5
      box(group, 2.05, 0.12, 1.78, 0, 0.03, 0, M.dark, 0.1)
      box(group, 1.97, 0.03, 1.7, 0, 0.12, 0, glowMat, 0.09)
      box(group, 2.03, 0.17, 1.75, 0, 0.215, 0, M.body, 0.1)
      for (const x of [-0.85, 0.85]) for (const z of [-0.7, 0.7]) screw(group, x, 0.311, z)
      gear(group, -0.35, 0.45, 0, 0.27)
      gear(group, 0.22, 0.45, 0.12, 0.21)
      box(group, 0.6, 0.15, 0.36, 0.52, 0.47, -0.33, M.dark)
      for (let j = 0; j < 6; j++) box(group, 0.025, 0.16, 0.37, 0.3 + j * 0.08, 0.47, -0.33, M.edge, 0.004)
      tube(group, [[-0.7, 0.4, -0.4], [-0.55, 0.48, 0.4], [0.35, 0.45, 0.6], [0.7, 0.58, 0.23]], 0.023, M.light)
      const plaque = canvasTexture(512, 116, (c, w, h) => {
        c.fillStyle = '#151a20'
        c.fillRect(0, 0, w, h)
        print(c, String(i + 1).padStart(2, '0'), 24, 76, 42, '#ff7a1a', 550)
        print(c, d.name.toUpperCase(), 111, 73, 35, '#d7d9d7', 550)
      })
      screen(group, 1.54, 0.345, 0, 0.27, 0.891, plaque)
      const label = document.createElement('div')
      label.className = 'station-label'
      label.innerHTML = `<div class="stem"></div><div class="label-card"><div class="label-title"><span>${String(i + 1).padStart(2, '0')}</span>${d.name}</div><div class="label-meta">Step ${d.step} · ${d.output}</div></div>`
      $('labels').appendChild(label)
      cleanups.push(() => label.remove())

      stations.push({ ...d, group, base: new THREE.Vector3(...d.pos), glowMat, label, index: i, anchor: new THREE.Vector3(0, 2.5, 0) })
    })

    const engine = stations[0].group
    box(engine, 1.74, 0.62, 1.33, 0, 0.65, -0.05, S.ivory, 0.13)
    box(engine, 1.5, 0.1, 1.16, 0, 0.99, -0.04, S.body, 0.025)
    for (const x of [-0.68, 0.68]) {
      cyl(engine, 0.065, 1.73, x, 1.35, -0.18, M.chrome)
      box(engine, 0.22, 1.8, 0.22, x, 1.37, -0.44, S.ivory, 0.035)
    }
    box(engine, 1.82, 0.27, 0.4, 0, 2.28, -0.35, S.amber, 0.045)
    box(engine, 1.55, 0.06, 0.06, 0, 2.13, -0.115, M.chrome, 0.01)
    const printhead = new THREE.Group()
    engine.add(printhead)
    printhead.position.set(0, 1.9, -0.08)
    printhead.userData.moving = true
    box(printhead, 0.45, 0.36, 0.44, 0, 0, 0, M.body, 0.05)
    cyl(printhead, 0.11, 0.13, 0, -0.24, 0.03, M.chrome, 0.04)
    box(printhead, 0.24, 0.045, 0.022, 0, 0.09, 0.23, M.light, 0.01)
    tube(engine, [[-0.68, 2.1, -0.35], [-0.42, 2.52, -0.4], [0.25, 2.5, -0.4], [0.35, 2.01, -0.12]], 0.032, M.dark)
    const reels: THREE.Group[] = []
    for (const [x, y] of [[-1.03, 1.82], [-0.94, 2.78]]) {
      const reel = new THREE.Group()
      reel.position.set(x, y, -0.48)
      engine.add(reel)
      reel.userData.moving = true
      const core = cyl(reel, 0.4, 0.22, 0, 0, 0, M.dark)
      core.rotation.x = Math.PI / 2
      for (const z of [-0.14, 0.14]) {
        const disc = cyl(reel, 0.46, 0.045, 0, 0, z, M.chrome)
        disc.rotation.x = Math.PI / 2
        for (let j = 0; j < 6; j++) {
          const a = (j / 6) * TAU
          const hole = cyl(reel, 0.1, 0.006, Math.cos(a) * 0.29, Math.sin(a) * 0.29, z + (z > 0 ? 0.026 : -0.026), M.dark, undefined, 14)
          hole.rotation.x = Math.PI / 2
        }
      }
      const axle = cyl(reel, 0.095, 0.37, 0, 0, 0, M.amber)
      axle.rotation.x = Math.PI / 2
      reels.push(reel)
    }
    tube(engine, [[-1.36, 2.66, -0.48], [-1.5, 2.34, -0.48], [-1.34, 1.92, -0.48]], 0.045, M.dark)
    const videoTexture = canvasTexture(384, 640, () => {})
    function drawVideo(t: number) {
      const c = videoTexture.ctx, w = 384, h = 640
      c.fillStyle = '#ff7a1a'
      c.fillRect(0, 0, w, h)
      c.fillStyle = '#c57e45'
      c.beginPath()
      c.arc(330, 205, 210, 0, TAU)
      c.fill()
      c.strokeStyle = '#171b20'
      c.lineWidth = 13
      for (let i = 0; i < 3; i++) {
        c.beginPath()
        c.ellipse(194, 270, 90 - i * 21, 111, Math.sin(t * 0.25) * 0.3 + 0.4, 0, TAU)
        c.stroke()
      }
      print(c, 'MADE', 28, 57, 24, '#242320', 650)
      print(c, 'BY YOU.', 24, 103, 42, '#242320', 700)
      c.fillStyle = '#171b20'
      c.beginPath()
      c.roundRect(25, 465, 334, 123, 12)
      c.fill()
      const texts = ['From an idea —', 'to a real product.', 'Your agent', 'is already at work.']
      const n = Math.floor(t * 0.7) % 4
      print(c, texts[n], 45, 505, 25, '#f4f1ea', 550)
      print(c, texts[(n + 1) % 4], 45, 547, 25, '#f4f1ea', 550)
      c.fillStyle = '#fff7d4'
      c.fillRect(27, 615, Math.max(10, ((t * 0.13) % 1) * 330), 5)
      videoTexture.texture.needsUpdate = true
    }
    drawVideo(0)
    const outputVideo = new THREE.Group()
    outputVideo.userData.moving = true
    engine.add(outputVideo)
    box(outputVideo, 0.62, 1.08, 0.055, 0, 1.36, 0.61, M.dark, 0.035)
    screen(outputVideo, 0.56, 0.98, 0, 1.36, 0.641, videoTexture)
    box(engine, 1.14, 0.12, 0.2, 0, 0.83, 0.66, M.dark, 0.025)
    for (const x of [-0.42, 0.42]) {
      const r = cyl(engine, 0.115, 0.18, x, 0.92, 0.6, M.chrome)
      r.rotation.z = Math.PI / 2
    }
    for (let i = 0; i < 5; i++) box(engine, 0.08, 0.03, 0.22, -0.38 + i * 0.19, 1.011, -0.02, M.edge, 0.005)

    const admin = stations[1].group
    box(admin, 1.9, 0.66, 1.36, 0, 0.67, -0.04, S.body, 0.11)
    const consoleTop = new THREE.Group()
    consoleTop.position.set(0, 1.01, -0.08)
    consoleTop.rotation.x = -0.32
    admin.add(consoleTop)
    box(consoleTop, 1.76, 0.12, 1.27, 0, 0, 0, S.ivory, 0.04)
    const queue = canvasTexture(640, 340, () => {})
    function drawQueue(t: number) {
      const c = queue.ctx
      c.fillStyle = '#111b20'
      c.fillRect(0, 0, 640, 340)
      print(c, 'VIDEO QUEUE', 25, 45, 21, '#acb9b8', 550)
      print(c, '03 / 08', 497, 45, 20, '#ff7a1a', 500)
      for (let i = 0; i < 3; i++) {
        const y = 74 + i * 76
        c.fillStyle = '#202c30'
        c.beginPath()
        c.roundRect(21, y, 598, 61, 6)
        c.fill()
        c.fillStyle = i === 0 ? '#c57e45' : '#626f69'
        c.fillRect(34, y + 10, 27, 41)
        print(c, ['Product overview', 'Brand story', 'New collection'][i], 77, y + 29, 19, '#d4d8cc')
        print(c, i === 0 ? 'RENDERING' : 'QUEUED', 77, y + 49, 11, i === 0 ? '#c57e45' : '#81948f')
        c.fillStyle = '#334348'
        c.fillRect(377, y + 26, 214, 7)
        c.fillStyle = i === 0 ? '#ff7a1a' : '#607475'
        c.fillRect(377, y + 26, i === 0 ? ((t * 0.15) % 1) * 214 : 41 + i * 27, 7)
      }
    }
    drawQueue(0)
    const qs = screen(consoleTop, 1.53, 0.79, 0, 0.067, -0.17, queue)
    qs.rotation.x = -Math.PI / 2
    const toggles: THREE.Mesh[] = []
    for (let i = 0; i < 4; i++) {
      const x = -0.57 + i * 0.38
      cyl(consoleTop, 0.074, 0.035, x, 0.1, 0.45, M.dark)
      const t = cyl(consoleTop, 0.025, 0.15, x, 0.19, 0.45, M.chrome)
      t.rotation.x = -0.4
      t.userData.moving = true
      toggles.push(t)
      ball(consoleTop, 0.04, x, 0.275, 0.421, M.ivory)
    }
    cyl(admin, 0.075, 0.06, 0.77, 1.05, -0.62, M.green)
    for (let i = 0; i < 7; i++) box(admin, 0.55, 0.027, 0.02, 0, 0.46 + i * 0.05, 0.655, M.dark, 0.003)

    const storefront = stations[2].group
    box(storefront, 1.35, 0.18, 0.88, 0, 0.44, 0, S.ivory, 0.045)
    cyl(storefront, 0.095, 1.04, 0, 0.93, -0.31, M.chrome)
    box(storefront, 0.56, 0.91, 0.14, 0, 0.99, -0.34, S.body, 0.04)
    box(storefront, 2.42, 1.72, 0.2, 0, 1.94, -0.17, S.ivory, 0.08)
    box(storefront, 2.28, 1.59, 0.1, 0, 1.94, -0.044, M.dark, 0.045)
    const webTexture = canvasTexture(896, 592, (c, w, h) => {
      c.fillStyle = '#edece3'
      c.fillRect(0, 0, w, h)
      c.fillStyle = '#dedfd7'
      c.fillRect(0, 0, w, 56)
      c.fillStyle = '#adaeaa'
      for (let i = 0; i < 3; i++) {
        c.beginPath()
        c.arc(26 + i * 19, 27, 4, 0, TAU)
        c.fill()
      }
      print(c, 'YOUR PRODUCT', 33, 100, 22, '#22282b', 650)
      print(c, 'Home    Catalog    Account', 535, 98, 14, '#6a7271')
      c.fillStyle = '#ff7a1a'
      c.beginPath()
      c.roundRect(32, 131, 287, 401, 10)
      c.fill()
      c.strokeStyle = '#242827'
      c.lineWidth = 8
      for (let i = 0; i < 3; i++) {
        c.beginPath()
        c.ellipse(175, 320, 75 - i * 17, 94, 0.4, 0, TAU)
        c.stroke()
      }
      print(c, 'FROM IDEA', 52, 181, 29, '#242827', 700)
      print(c, 'TO PRODUCT.', 52, 220, 29, '#242827', 700)
      print(c, 'Your idea.', 359, 197, 41, '#22282b', 600)
      print(c, 'Already live.', 359, 252, 41, '#22282b', 600)
      print(c, 'A video that tells people', 362, 300, 19, '#77807b')
      print(c, 'what matters most.', 362, 329, 19, '#77807b')
      for (let i = 0; i < 3; i++) {
        c.fillStyle = '#d1d5cd'
        c.fillRect(362, 363 + i * 16, 400 - i * 43, 5)
      }
      c.fillStyle = '#232a2b'
      c.beginPath()
      c.roundRect(359, 447, 279, 62, 7)
      c.fill()
      print(c, 'Order a video  ↗', 390, 486, 22, '#f4f1ea', 500)
      print(c, 'BUILT BY YOUR AGENTS', 33, 571, 12, '#879088')
    })
    screen(storefront, 2.16, 1.43, 0, 1.95, 0.011, webTexture)
    ball(storefront, 0.024, 0, 2.747, -0.05, M.dark)
    box(storefront, 0.21, 0.019, 0.008, 0, 1.149, 0.013, M.light, 0.003)
    screen(storefront, 0.685, 0.96, -0.655, 1.86, 0.018, videoTexture)
    const flyPost = new THREE.Group()
    flyPost.userData.moving = true
    storefront.add(flyPost)
    box(flyPost, 0.59, 0.77, 0.045, 0.94, 0.81, 0.55, M.ivory, 0.025)
    const postTex = canvasTexture(220, 290, (c, w, h) => {
      c.fillStyle = '#f4f1ea'
      c.fillRect(0, 0, w, h)
      c.fillStyle = '#ff7a1a'
      c.fillRect(15, 16, 190, 168)
      c.fillStyle = '#272e30'
      c.beginPath()
      c.moveTo(94, 66)
      c.lineTo(140, 100)
      c.lineTo(94, 134)
      c.fill()
      print(c, 'CHANNEL', 17, 225, 23, '#283030', 600)
      c.fillStyle = '#b0b5b0'
      c.fillRect(17, 244, 153, 6)
      c.fillRect(17, 258, 104, 5)
    })
    screen(flyPost, 0.55, 0.72, 0.94, 0.81, 0.575, postTex)

    const cabinet = stations[3].group
    box(cabinet, 1.75, 1.77, 1.02, 0, 1.24, -0.13, S.body, 0.12)
    box(cabinet, 1.58, 0.13, 1.09, 0, 2.16, -0.13, S.amber, 0.04)
    box(cabinet, 1.47, 1.38, 0.055, 0, 1.31, 0.405, M.dark, 0.025)
    const orderTex = canvasTexture(480, 460, (c, w, h) => {
      c.fillStyle = '#172224'
      c.fillRect(0, 0, w, h)
      print(c, 'YOUR ORDERS', 30, 51, 27, '#e8e8d8', 550)
      print(c, 'Today · 3 new', 30, 81, 16, '#869991')
      ;['Anna', 'Michael', 'Maria'].forEach((n, i) => {
        const y = 110 + i * 100
        c.fillStyle = '#283839'
        c.beginPath()
        c.roundRect(22, y, 436, 83, 8)
        c.fill()
        c.fillStyle = ['#ff7a1a', '#bdbf9c', '#7d938e'][i]
        c.beginPath()
        c.arc(58, y + 40, 19, 0, TAU)
        c.fill()
        print(c, n[0], 49, y + 47, 20, '#1b2828', 600)
        print(c, n, 93, y + 33, 23, '#e6e8dc', 550)
        print(c, ['New order', 'In production', 'Video ready'][i], 93, y + 58, 15, '#94a59b')
        print(c, '↗', 410, y + 49, 25, '#c57e45')
      })
    })
    screen(cabinet, 1.31, 1.255, 0, 1.37, 0.44, orderTex)
    box(cabinet, 1.27, 0.075, 0.29, 0, 0.57, 0.55, M.chrome, 0.02)
    for (let i = 0; i < 3; i++) box(cabinet, 1.15, 0.021, 0.12, 0, 0.58 + i * 0.15, -0.35, M.copper, 0.006)
    tube(cabinet, [[0.69, 0.43, -0.2], [0.89, 0.65, -0.2], [0.89, 1.8, -0.2], [0.65, 1.99, -0.2]], 0.033, M.chrome)
    const incoming = new THREE.Group()
    incoming.userData.moving = true
    cabinet.add(incoming)
    box(incoming, 0.86, 0.42, 0.043, 0, 0, 0, M.light, 0.035)
    const nameTex = canvasTexture(432, 204, (c, w, h) => {
      c.fillStyle = '#ff7a1a'
      c.fillRect(0, 0, w, h)
      c.fillStyle = '#2a2e26'
      c.beginPath()
      c.arc(58, 98, 32, 0, TAU)
      c.fill()
      print(c, 'A', 42, 112, 34, '#ff7a1a', 550)
      print(c, 'Anna', 108, 91, 38, '#222822', 600)
      print(c, 'New order  +', 108, 138, 23, '#5b4c22', 500)
    })
    screen(incoming, 0.82, 0.39, 0, 0, 0.026, nameTex)

    const cashdesk = stations[4].group
    box(cashdesk, 1.91, 0.63, 1.32, 0, 0.65, -0.06, S.ivory, 0.12)
    box(cashdesk, 1.96, 0.19, 1.38, 0, 0.42, -0.04, S.body, 0.04)
    box(cashdesk, 1.37, 0.09, 0.038, 0, 0.44, 0.66, M.dark, 0.01)
    box(cashdesk, 0.37, 0.042, 0.03, 0, 0.45, 0.687, M.chrome, 0.009)
    box(cashdesk, 1.02, 0.25, 0.91, -0.33, 1.04, -0.03, S.body, 0.045)
    for (let row = 0; row < 3; row++)
      for (let col = 0; col < 3; col++)
        box(cashdesk, 0.19, 0.085, 0.17, -0.62 + col * 0.27, 1.21, 0.27 - row * 0.24, col === 2 && row === 2 ? M.amber : M.ivory, 0.022)
    box(cashdesk, 0.64, 0.6, 0.52, 0.58, 1.04, -0.15, S.body, 0.045)
    box(cashdesk, 0.48, 0.07, 0.09, 0.59, 1.37, -0.1, M.dark, 0.01)
    cyl(cashdesk, 0.06, 0.65, -0.35, 1.6, -0.56, M.chrome)
    box(cashdesk, 1.13, 0.46, 0.19, -0.35, 1.98, -0.56, S.body, 0.045)
    const cashTex = canvasTexture(512, 176, () => {})
    function drawCash() {
      const c = cashTex.ctx
      c.fillStyle = '#12231e'
      c.fillRect(0, 0, 512, 176)
      print(c, 'PAYMENT RECEIVED', 22, 44, 23, '#9cae91', 500)
      print(c, '+ $29', 26, 131, 66, '#ecedc7', 500)
    }
    drawCash()
    screen(cashdesk, 1.015, 0.349, -0.35, 1.98, -0.459, cashTex)
    const receipt = new THREE.Group()
    receipt.position.set(0.59, 1.37, -0.1)
    receipt.userData.moving = true
    cashdesk.add(receipt)
    const receiptTex = canvasTexture(280, 540, (c, w, h) => {
      c.fillStyle = '#f4f1ea'
      c.fillRect(0, 0, w, h)
      print(c, 'YOUR PRODUCT', 25, 52, 24, '#333d36', 650)
      print(c, 'SALES RECEIPT', 32, 87, 19, '#566059')
      c.strokeStyle = '#8a9189'
      c.setLineDash([5, 6])
      c.beginPath()
      c.moveTo(22, 115)
      c.lineTo(258, 115)
      c.stroke()
      print(c, 'Video', 25, 154, 22, '#333d36')
      print(c, '1 × $29', 25, 190, 21, '#333d36')
      print(c, 'PAID', 25, 263, 31, '#333d36', 650)
      print(c, 'Thank you!', 25, 317, 24, '#687067')
      for (let i = 0; i < 44; i++) {
        c.fillStyle = '#333d36'
        c.fillRect(25 + i * 5, 370, 1 + (i % 3), 83)
      }
      print(c, 'No. 0001', 81, 496, 17, '#59635b')
    })
    const rp = screen(receipt, 0.41, 0.83, 0, 0.415, 0.01, receiptTex)
    rp.material.side = THREE.DoubleSide
    receipt.rotation.x = -0.16
    const coin = new THREE.Group()
    coin.userData.moving = true
    cashdesk.add(coin)
    const coinDisc = cyl(coin, 0.22, 0.065, 0, 0, 0, M.amber, undefined, 32)
    coinDisc.rotation.x = Math.PI / 2
    const coinRing = new THREE.Mesh(new THREE.TorusGeometry(0.174, 0.014, 6, 32), M.light)
    coinRing.position.z = 0.037
    coin.add(coinRing)
    const rubleTex = canvasTexture(128, 128, (c, w, h) => {
      c.clearRect(0, 0, w, h)
      c.textAlign = 'center'
      print(c, '$', 64, 95, 91, '#80561c', 650)
    })
    const ruble = screen(coin, 0.28, 0.28, 0, 0, 0.04, rubleTex)
    ruble.material.transparent = true
    cyl(cashdesk, 0.33, 0.09, 1.04, 0.39, 0.55, M.dark)
    cyl(cashdesk, 0.26, 0.025, 1.04, 0.445, 0.55, M.copper)

    const path = new THREE.CatmullRomCurve3(
      [
        [-3.95, 0.84, 0.65], [-3.1, 0.84, -0.12], [-1.45, 0.84, -0.79], [1.32, 0.84, -0.8],
        [3.3, 0.84, 0.19], [3.43, 0.84, 1.21], [1.35, 0.84, 2.7], [-1.4, 0.84, 2.52], [-3.54, 0.84, 1.65]
      ].map((p) => new THREE.Vector3(...p)),
      true, 'catmullrom', 0.25
    )
    const belt = new THREE.Group()
    machine.add(belt)
    const frameMesh = new THREE.Mesh(new THREE.TubeGeometry(path, 150, 0.35, 8, true), M.dark)
    frameMesh.scale.y = 0.3
    frameMesh.position.y = 0.51
    belt.add(frameMesh)
    const beltCount = 148, beltSlats = new THREE.InstancedMesh(boxGeo(0.135, 0.065, 0.63, 0.012), M.body, beltCount)
    beltSlats.receiveShadow = true
    beltSlats.castShadow = false
    belt.add(beltSlats)
    beltSlats.instanceMatrix.setUsage(THREE.DynamicDrawUsage)
    const dummy = new THREE.Object3D(), pVec = new THREE.Vector3(), tVec = new THREE.Vector3()
    function updateBelt(t: number) {
      for (let i = 0; i < beltCount; i++) {
        const u = (i / beltCount + t * 0.012) % 1
        path.getPointAt(u, pVec)
        path.getTangentAt(u, tVec)
        dummy.position.copy(pVec)
        dummy.rotation.set(0, -Math.atan2(tVec.z, tVec.x), 0)
        dummy.updateMatrix()
        beltSlats.setMatrixAt(i, dummy.matrix)
      }
      beltSlats.instanceMatrix.needsUpdate = true
    }
    updateBelt(0)
    for (const side of [-1, 1]) {
      const pts = []
      for (let i = 0; i <= 160; i++) {
        path.getPointAt(i / 160, pVec)
        path.getTangentAt(i / 160, tVec)
        pts.push(pVec.clone().add(new THREE.Vector3(-tVec.z * 0.36 * side, 0.09, tVec.x * 0.36 * side)))
      }
      const railPath = new THREE.CatmullRomCurve3(pts)
      belt.add(new THREE.Mesh(new THREE.TubeGeometry(railPath, 160, 0.028, 6, false), M.chrome))
    }
    for (let i = 0; i < 16; i++) {
      const p = path.getPointAt(i / 16)
      cyl(belt, 0.045, 0.43, p.x, 0.53, p.z, M.chrome)
    }
    const pipes = new THREE.Group()
    machine.add(pipes)
    const connectors = []
    for (let i = 0; i < 4; i++) {
      const a = stations[i].base, b = stations[i + 1].base
      const points = [
        a.clone().add(new THREE.Vector3(0.4, 0.12, 0)),
        a.clone().lerp(b, 0.35).add(new THREE.Vector3(0, 0.1, -0.6)),
        a.clone().lerp(b, 0.65).add(new THREE.Vector3(0, 0.1, -0.6)),
        b.clone().add(new THREE.Vector3(-0.4, 0.12, 0)),
      ]
      const curve = new THREE.CatmullRomCurve3(points)
      const mesh = new THREE.Mesh(new THREE.TubeGeometry(curve, 30, 0.054, 8, false), M.copper)
      pipes.add(mesh)
      connectors.push({ mesh, a: i, b: i + 1 })
    }
    const scriptTex = canvasTexture(256, 352, (c, w, h) => {
      c.fillStyle = '#eeeae0'
      c.fillRect(0, 0, w, h)
      print(c, 'SCRIPT', 24, 47, 22, '#3b403a', 650)
      print(c, '01 / Opening', 24, 85, 15, '#8b8d80')
      for (let i = 0; i < 9; i++) {
        c.fillStyle = i === 4 ? '#c57e45' : '#aeb2a5'
        c.fillRect(24, 111 + i * 21, 190 - (i % 3) * 24, 6)
      }
      print(c, 'DONE  ✓', 24, 327, 17, '#786124', 600)
    })
    const orderCardTex = canvasTexture(256, 352, (c, w, h) => {
      c.fillStyle = '#c57e45'
      c.fillRect(0, 0, w, h)
      print(c, 'NEW', 21, 48, 24, '#30362d', 650)
      print(c, 'ORDER', 21, 79, 24, '#30362d', 650)
      c.strokeStyle = '#716431'
      c.lineWidth = 2
      c.strokeRect(23, 112, 210, 139)
      print(c, 'Anna', 42, 190, 37, '#30362d', 550)
      print(c, 'VIDEO / 01', 23, 320, 17, '#635728')
    })
    const packetTextures = [orderCardTex, scriptTex, videoTexture, postTex, receiptTex]
    const packets: Array<{ group: THREE.Group; faces: THREE.Mesh<THREE.PlaneGeometry, THREE.MeshBasicMaterial>[]; halo: THREE.Mesh; stage: number; phase: number }> = []
    for (let i = 0; i < 6; i++) {
      const g = new THREE.Group()
      g.userData.moving = true
      machine.add(g)
      box(g, 0.47, 0.71, 0.04, 0, 0, 0, M.ivory, 0.022)
      const faces = packetTextures.map((tex) => {
        const s = screen(g, 0.43, 0.665, 0, 0, 0.024, tex)
        s.material.side = THREE.DoubleSide
        s.visible = false
        return s
      })
      const halo = new THREE.Mesh(
        new THREE.RingGeometry(0.4, 0.414, 40),
        new THREE.MeshBasicMaterial({ color: 0xff7a1a, transparent: true, opacity: 0.8, side: THREE.DoubleSide, depthWrite: false })
      )
      halo.rotation.x = -Math.PI / 2
      halo.position.y = -0.37
      g.add(halo)
      halo.visible = false
      packets.push({ group: g, faces, halo, stage: -1, phase: 0 })
    }
    let adminU = nearestPort(-1.65, -0.7), storeU = nearestPort(1.5, -0.7), cashU = nearestPort(0.93, 2.65)
    function nearestPort(x: number, z: number) {
      let best = 0, dist = Infinity
      for (let i = 0; i < 300; i++) {
        const p = path.getPointAt(i / 300), d = (p.x - x) ** 2 + (p.z - z) ** 2
        if (d < dist) { dist = d; best = i / 300 }
      }
      return best
    }

    function compact(group: THREE.Object3D) {
      for (const child of [...group.children]) if ((child as THREE.Group).isGroup) compact(child)
      const buckets = new Map<string, THREE.Mesh<THREE.BufferGeometry, THREE.Material>[]>()
      for (const object of group.children) {
        const child = object as THREE.Mesh<THREE.BufferGeometry, THREE.Material> & { isInstancedMesh?: boolean }
        if (!child.isMesh || child.isInstancedMesh || child.userData.moving || Array.isArray(child.material)) continue
        const key = child.material.uuid
        if (!buckets.has(key)) buckets.set(key, [])
        buckets.get(key)!.push(child)
      }
      for (const list of buckets.values()) {
        if (list.length < 2) continue
        const geos = list.map((m) => {
          m.updateMatrix()
          const g = m.geometry.index ? m.geometry.toNonIndexed() : m.geometry.clone()
          return g.applyMatrix4(m.matrix)
        })
        const merged = mergeGeometries(geos, false)
        for (const geo of geos) geo.dispose()
        if (!merged) continue
        const mesh = new THREE.Mesh(merged, list[0].material)
        mesh.castShadow = list.some((x) => x.castShadow)
        mesh.receiveShadow = list.some((x) => x.receiveShadow)
        for (const m of list) group.remove(m)
        group.add(mesh)
      }
    }
    ;[incoming, receipt, coin, outputVideo, flyPost, printhead, ...reels].forEach((g) => (g.userData.moving = true))
    compact(machine)
    stations.forEach((s) => s.group.traverse((o) => { o.userData.station = s.id }))
    const pickables = stations.map((s) => s.group)

    let mode: MachineMode = 'assembled', cameraMode: MachineCamera = 'overview', playing = !reduceMotion
    let simTime = 0, spread = 0, selected: string = 'engine', hovered: string | null = null
    let width = frameWidth(), height = frameHeight(), mobile = width <= 900
    let lastInteraction = performance.now(), dragging = false, wasDragged = false, downX = 0, downY = 0
    let cameraAnimating = true, flightTime = 0, lastDraw = -1, visible = true, contextLost = false
    const desiredPosition = new THREE.Vector3(), desiredTarget = new THREE.Vector3(0, 1, 0)
    const viewDirection = new THREE.Vector3(10.5, 10.8, 17).normalize()
    let baseDistance = 25, sized = false, readySent = false

    function layoutCamera() {
      if (!frameWidth() || !frameHeight()) return
      const first = !sized
      sized = true
      width = frameWidth()
      height = frameHeight()
      mobile = width <= 900
      renderer.setSize(width, height)
      camera.aspect = width / height
      camera.setViewOffset(width, height, mobile || !embedded ? 0 : -width * 0.21, mobile || embedded ? 0 : height * 0.025, width, height)
      const aspect = width / height
      const availableWidth = mobile ? 0.91 : Math.min(0.55, aspect > 2 ? 0.54 : 0.57)
      const horizontalFit = 17.3 / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * aspect * availableWidth)
      const verticalFit = 11.5 / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * (embedded ? 0.85 : 0.62))
      baseDistance = (Math.max(horizontalFit, verticalFit) * (mobile ? 0.97 : 1)) / (embedded ? (mobile ? 1.15 : 1.45) : 1)
      controls.maxDistance = Math.max(55, baseDistance * 1.6)
      camera.updateProjectionMatrix()
      setCameraGoal()
      cameraAnimating = true
      if (first) {
        camera.position.copy(desiredPosition)
        controls.target.copy(desiredTarget)
        controls.update()
        cameraAnimating = false
      }
    }
    function setCameraGoal() {
      const expand = mode === 'stations' ? 1.2 : 1
      if (cameraMode === 'station') {
        const s = stations.find((s) => s.id === selected)!
        desiredTarget.copy(s.group.position).add(new THREE.Vector3(0, 1.25, 0))
        desiredPosition.copy(desiredTarget).addScaledVector(viewDirection, mobile ? 9 : 12)
      } else {
        desiredTarget.set(0, 1, 0)
        const distance = baseDistance * expand
        if (cameraMode === 'side') desiredPosition.set(13, 5, 20).normalize().multiplyScalar(distance).add(desiredTarget)
        else if (cameraMode === 'top') desiredPosition.set(0.01, distance, 0.8).add(desiredTarget)
        else desiredPosition.copy(viewDirection).multiplyScalar(distance).add(desiredTarget)
      }
    }
    function syncButtons() {
      root.querySelectorAll<HTMLElement>('[data-mode]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.mode === mode)))
      root.querySelectorAll<HTMLElement>('[data-camera]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.camera === cameraMode)))
      $('journey').classList.toggle('visible', mode === 'order')
    }
    const modeAliases: Record<string, MachineMode> = { Assembled: 'assembled', Cutaway: 'cutaway', Stations: 'stations', 'One order': 'order', assembled: 'assembled', cutaway: 'cutaway', stations: 'stations', order: 'order' }
    const cameraAliases: Record<string, MachineCamera> = { Overview: 'overview', Side: 'side', Top: 'top', Station: 'station', Flight: 'flight', overview: 'overview', side: 'side', top: 'top', station: 'station', flight: 'flight' }
    function setMode(name: string) {
      if (!Object.hasOwn(modeAliases, name)) return false
      mode = modeAliases[name]
      lastInteraction = performance.now()
      if (mode === 'order') { simTime = 0; lastDraw = -1; play(); cameraMode = 'overview' }
      else if (cameraMode === 'station') cameraMode = 'overview'
      setCameraGoal()
      cameraAnimating = true
      syncButtons()
      return true
    }
    function focusStation(id: string) {
      const s = stations.find((s) => s.id === id)
      if (!s) return false
      selected = id
      if (mode === 'order') mode = 'assembled'
      cameraMode = 'station'
      lastInteraction = performance.now()
      setCameraGoal()
      cameraAnimating = true
      syncButtons()
      return true
    }
    function setCamera(name: string) {
      if (!Object.hasOwn(cameraAliases, name)) return false
      cameraMode = cameraAliases[name]
      if (mode === 'order') mode = 'assembled'
      lastInteraction = performance.now()
      flightTime = 0
      setCameraGoal()
      cameraAnimating = true
      syncButtons()
      return true
    }
    function syncPlayback() {
      const b = $('play')
      b.setAttribute('aria-label', playing ? 'Pause the animation' : 'Resume the animation')
      b.setAttribute('aria-pressed', String(!playing))
      b.innerHTML = playing
        ? '<svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor"><rect x="2" y="1" width="2.5" height="10" rx=".5"/><rect x="7.5" y="1" width="2.5" height="10" rx=".5"/></svg>'
        : '<svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor"><path d="M3 1l8 5-8 5z"/></svg>'
      $('status').classList.toggle('paused', !playing)
      $('status-text').textContent = playing ? 'Machine running' : 'Machine paused'
    }
    function play() { playing = true; syncPlayback(); return true }
    function pause() { playing = false; syncPlayback(); return true }
    const api: MachineApi = { setMode, focusStation, setCamera, play, pause }
    window.__machine = api
    cleanups.push(() => { if (window.__machine === api) delete window.__machine })
    root.querySelectorAll<HTMLElement>('[data-mode]').forEach((b) => listen(b, 'click', () => setMode(b.dataset.mode ?? '')))
    root.querySelectorAll<HTMLElement>('[data-camera]').forEach((b) => listen(b, 'click', () => setCamera(b.dataset.camera ?? '')))
    listen($('play'), 'click', () => (playing ? pause() : play()))
    syncPlayback()
    layoutCamera()
    camera.position.copy(desiredPosition)
    controls.target.copy(desiredTarget)
    controls.update()
    cameraAnimating = false
    listen(window, 'resize', layoutCamera)
    const resizeObserver = new ResizeObserver(() => layoutCamera())
    resizeObserver.observe(root)
    cleanups.push(() => resizeObserver.disconnect())
    controls.addEventListener('start', () => { dragging = true; cameraAnimating = false; lastInteraction = performance.now() })
    controls.addEventListener('end', () => { dragging = false; lastInteraction = performance.now() })
    controls.addEventListener('change', () => { if (dragging) lastInteraction = performance.now() })
    const raycaster = new THREE.Raycaster(), pointer = new THREE.Vector2(), tooltip = $('tooltip')
    function hitStation(x: number, y: number) {
      pointer.set((x / width) * 2 - 1, (-y / height) * 2 + 1)
      raycaster.setFromCamera(pointer, camera)
      const hits = raycaster.intersectObjects(pickables, true)
      return hits.length ? stations.find((s) => s.id === hits[0].object.userData.station) : null
    }
    listen(renderer.domElement, 'pointermove', (e: PointerEvent) => {
      if (Math.hypot((e.clientX - root.getBoundingClientRect().left) - downX, (e.clientY - root.getBoundingClientRect().top) - downY) > 5) wasDragged = true
      if (dragging) return
      const s = hitStation((e.clientX - root.getBoundingClientRect().left), (e.clientY - root.getBoundingClientRect().top))
      hovered = s ? s.id : null
      renderer.domElement.style.cursor = s ? 'pointer' : 'grab'
      tooltip.classList.toggle('visible', !!s)
      if (s) {
        tooltip.querySelector('strong')!.innerHTML = `<span>${String(s.index + 1).padStart(2, '0')}</span>${s.name}`
        tooltip.querySelector('p')!.textContent = s.desc
        tooltip.style.left = Math.min(width - 255, Math.max(10, (e.clientX - root.getBoundingClientRect().left) + 16)) + 'px'
        tooltip.style.top = Math.max(10, Math.min(height - 95, (e.clientY - root.getBoundingClientRect().top) - 65)) + 'px'
      }
    })
    listen(renderer.domElement, 'pointerleave', () => { hovered = null; tooltip.classList.remove('visible') })
    listen(renderer.domElement, 'pointerdown', (e: PointerEvent) => {
      downX = (e.clientX - root.getBoundingClientRect().left)
      downY = (e.clientY - root.getBoundingClientRect().top)
      wasDragged = false
      tooltip.classList.remove('visible')
    })
    listen(renderer.domElement, 'pointerup', (e: PointerEvent) => {
      if (wasDragged) return
      const s = hitStation((e.clientX - root.getBoundingClientRect().left), (e.clientY - root.getBoundingClientRect().top))
      if (!s) return
      focusStation(s.id)
      options.onStation?.(s.id as StationId)
    })
    listen(document, 'visibilitychange', () => { visible = !document.hidden; lastFrame = performance.now() })
    const observer = new IntersectionObserver((entries) => { visible = entries[0].isIntersecting && !document.hidden; lastFrame = performance.now() }, { threshold: 0.01 })
    observer.observe(renderer.domElement)
    cleanups.push(() => observer.disconnect())
    listen(renderer.domElement, 'webglcontextlost', (e: Event) => {
      e.preventDefault()
      contextLost = true
      showError('The graphics context was interrupted. The scene comes back on its own once WebGL is available again.')
    })
    listen(renderer.domElement, 'webglcontextrestored', () => { contextLost = false; $('error').style.display = 'none'; lastFrame = performance.now() })

    const scratch = new THREE.Vector3(), anchor = new THREE.Vector3()
    const journeySteps = [
      ['New order', 'Cabinet · an order from Anna'],
      ['Writing the script', 'Engine · the idea becomes a story'],
      ['Assembling the video', 'Admin · voice, video and subtitles'],
      ['Publishing the product', 'Storefront · the video on your page'],
      ['Payment received', 'Checkout · receipt printed, coin in'],
    ]
    let prevJourney = -1, lastFrame = performance.now(), frameCount = 0, measureTime = 0, pixelRatio = renderer.getPixelRatio(), rafId = 0

    function animate(now: number) {
      rafId = requestAnimationFrame(animate)
      const dt = Math.max(0, Math.min((now - lastFrame) / 1000, 0.045))
      lastFrame = now
      if (!visible || contextLost) return
      if (playing) { simTime += dt; flightTime += dt }
      const t = simTime, beat = (t / 4) % 1, tact = (t * TAU) / 4, smooth = 1 - Math.exp(-dt * 5)
      spread = THREE.MathUtils.lerp(spread, mode === 'stations' ? 1 : 0, smooth)
      cutPlane.constant = THREE.MathUtils.lerp(cutPlane.constant, mode === 'cutaway' ? 0.99 : 10, smooth)
      stations.forEach((s, i) => {
        s.group.position.copy(s.base)
        s.group.position.x *= 1 + spread * 0.29
        s.group.position.z *= 1 + spread * 0.37
        s.group.position.y += spread * (i % 2 ? 0.32 : 0.55)
        const pulse = Math.pow(Math.max(0, Math.sin(tact - i * 0.9)), 7)
        s.glowMat.emissiveIntensity = THREE.MathUtils.lerp(s.glowMat.emissiveIntensity, hovered === s.id || (cameraMode === 'station' && selected === s.id) ? 3.5 : 0.55 + pulse * 0.65, smooth)
      })
      belt.scale.set(1 + spread * 0.12, 1, 1 + spread * 0.15)
      pipes.scale.set(1 + spread * 0.25, 1, 1 + spread * 0.3)
      gears.forEach(({ g, vertical }, i) => {
        if (vertical) g.rotation.z = t * (i % 2 ? -1 : 1) * 1.1
        else g.rotation.y = t * (i % 2 ? -1 : 1) * 1.1
      })
      reels.forEach((r, i) => (r.rotation.z = -t * (i ? 0.65 : 0.85)))
      printhead.position.x = Math.sin(tact) * 0.42
      printhead.position.y = 1.91 + Math.sin(tact * 2) * 0.055
      outputVideo.position.y = beat * 0.25
      flyPost.position.y = Math.sin(tact) * 0.04
      const orderPhase = (t / 24) % 1, cashBeat = mode === 'order' ? THREE.MathUtils.clamp((orderPhase - 0.88) / 0.12, 0, 1) : beat
      receipt.visible = coin.visible = mode !== 'order' || orderPhase > 0.88
      receipt.scale.y = 0.2 + Math.min(1, cashBeat * 1.5) * 0.8
      coin.position.set(1.04, 2.7 - Math.min(1, cashBeat * 1.7) ** 2 * 2.17, 0.55)
      coin.rotation.y = t * 3.5
      coin.scale.setScalar(cashBeat > 0.9 ? 1 - (cashBeat - 0.9) * 8 : 1)
      const incomingBeat = mode === 'order' ? Math.min(1, orderPhase / 0.15) : beat
      incoming.visible = mode !== 'order' || orderPhase < 0.15
      incoming.position.set(Math.sin(incomingBeat * Math.PI) * 0.24, 2.9 - incomingBeat * 1.9, 1.1 - incomingBeat * 0.55)
      incoming.rotation.z = Math.sin(incomingBeat * Math.PI) * -0.14
      incoming.scale.setScalar(Math.min(1, incomingBeat * 8 + 0.15, (1 - incomingBeat) * 7 + 0.1))
      toggles.forEach((o, i) => (o.rotation.x = Math.sin(tact + i) > 0 ? -0.4 : 0.4))
      if (t - lastDraw > 1 / 18 || lastDraw < 0) {
        drawVideo(t)
        drawQueue(t)
        queue.texture.needsUpdate = true
        updateBelt(t)
        lastDraw = t
      }
      packets.forEach((packet, i) => {
        const phase = (t / 24 + i / 6) % 1
        packet.phase = phase
        let stage
        if (phase < 0.15) {
          stage = 0
          const f = phase / 0.15
          packet.group.position.copy(stations[3].group.position).add(new THREE.Vector3(0, 1.6, 0.6))
          scratch.copy(stations[0].group.position).add(new THREE.Vector3(0, 1.3, 0.65))
          packet.group.position.lerp(scratch, f)
          packet.group.position.y += Math.sin(f * Math.PI) * 2
          packet.group.rotation.set(0, Math.sin(f * Math.PI) * 0.28, Math.sin(f * Math.PI) * -0.1)
        } else {
          const u = ((phase - 0.15) / 0.85) * cashU
          path.getPointAt(u, packet.group.position)
          packet.group.position.x *= 1 + spread * 0.12
          packet.group.position.z *= 1 + spread * 0.15
          packet.group.position.y += 0.43
          packet.group.rotation.set(0, 0.18, 0)
          stage = u < adminU * 0.7 ? 1 : u < storeU * 0.96 ? 2 : u < cashU * 0.83 ? 3 : 4
        }
        if (packet.stage !== stage) {
          packet.faces.forEach((f, j) => (f.visible = j === stage))
          packet.stage = stage
        }
        packet.group.visible = mode !== 'order' || i === 0
        packet.halo.visible = mode === 'order' && i === 0
        packet.group.scale.setScalar(mode === 'order' ? 1.35 : 1)
        if (phase > 0.94) packet.group.scale.multiplyScalar(Math.max(0.05, (1 - phase) / 0.06))
      })
      if (mode === 'order') {
        const packet = packets[0], step = packet.stage
        if (step !== prevJourney) {
          $('journey-title').textContent = journeySteps[step][0]
          $('journey-detail').textContent = journeySteps[step][1]
          prevJourney = step
        }
        $('journey-progress').style.width = packet.phase * 100 + '%'
        if (!dragging && playing) {
          desiredTarget.copy(packet.group.position)
          desiredPosition.copy(desiredTarget).addScaledVector(viewDirection, mobile ? 10 : 15)
          cameraAnimating = true
        }
      } else if (cameraMode === 'flight' && playing && !dragging) {
        const a = flightTime * 0.12, d = baseDistance * (mode === 'stations' ? 1.2 : 1)
        desiredTarget.set(0, 1, 0)
        desiredPosition.set(Math.sin(a + 0.55) * d * 0.83, d * (0.5 + Math.sin(a * 0.7) * 0.09), Math.cos(a + 0.55) * d * 0.83).add(desiredTarget)
        cameraAnimating = true
      } else if (cameraMode === 'station' && cameraAnimating) setCameraGoal()
      if (cameraAnimating && !dragging) {
        const speed = 1 - Math.exp(-dt * (mode === 'order' ? 2.2 : 3))
        camera.position.lerp(desiredPosition, speed)
        controls.target.lerp(desiredTarget, speed)
        if (cameraMode !== 'flight' && mode !== 'order' && camera.position.distanceTo(desiredPosition) < 0.015 && controls.target.distanceTo(desiredTarget) < 0.015) {
          cameraAnimating = false
        }
      }
      controls.autoRotate = playing && !reduceMotion && !dragging && !cameraAnimating && mode !== 'order' && cameraMode === 'overview' && now - lastInteraction > 6500
      controls.autoRotateSpeed = 0.24
      controls.update(dt)
      stations.forEach((s, i) => {
        const show = mode === 'stations'
        s.label.classList.toggle('visible', show)
        if (!show) return
        anchor.copy(s.group.position).add(s.anchor).project(camera)
        const offsets = mobile ? [[-30, 25], [-27, -50], [15, -65], [16, -1], [-5, 52]] : [[-48, -14], [-8, -64], [30, -12], [30, 20], [-12, 40]]
        let x = (anchor.x * 0.5 + 0.5) * width - 40 + offsets[i][0]
        let y = (-anchor.y * 0.5 + 0.5) * height - 52 + offsets[i][1]
        x = THREE.MathUtils.clamp(x, mobile || !embedded ? 9 : width * 0.425, width - (mobile ? 123 : 165))
        y = THREE.MathUtils.clamp(y, 130, height - 200)
        s.label.style.transform = `translate(${x}px,${y}px)`
      })
      renderer.render(scene, camera)
      if (!readySent && sized) {
        readySent = true
        options.onReady?.()
      }
      if (playing) {
        frameCount++
        measureTime += dt
        if (measureTime > 4) {
          if (frameCount / measureTime < 43 && pixelRatio > 1) {
            pixelRatio = Math.max(1, pixelRatio - 0.25)
            renderer.setPixelRatio(pixelRatio)
          }
          frameCount = 0
          measureTime = 0
        }
      }
    }
    rafId = requestAnimationFrame(animate)
    cleanups.push(() => {
      cancelAnimationFrame(rafId)
      controls.dispose()
      const textures = new Set<THREE.Texture>()
      scene.traverse((object) => {
        const mesh = object as THREE.Mesh
        if (mesh.geometry) mesh.geometry.dispose()
        const list = mesh.material ? (Array.isArray(mesh.material) ? mesh.material : [mesh.material]) : []
        for (const material of list) {
          for (const value of Object.values(material)) if (value instanceof THREE.Texture) textures.add(value)
          material.dispose()
        }
      })
      geometries.forEach((g) => g.dispose())
      textures.forEach((t) => t.dispose())
      env.dispose()
      renderer.dispose()
      renderer.forceContextLoss()
      renderer.domElement.remove()
    })
    renderer.compile(scene, camera)

    $('loading').classList.add('done')
    $('error').style.display = 'none'
    Object.defineProperty(window, '__machineDebug', {
      value: {
        getState: () => ({
          mode, camera: cameraMode, playing, time: simTime, spread, cutHeight: cutPlane.constant, width, height, embedded, drawCalls: renderer.info.render.calls, triangles: renderer.info.render.triangles, pixelRatio: renderer.getPixelRatio(),
          stations: stations.map((s) => {
            const p = s.group.position.clone().add(new THREE.Vector3(0, 1, 0)).project(camera)
            return { id: s.id, x: (p.x * 0.5 + 0.5) * width, y: (-0.5 * p.y + 0.5) * height }
          }),
        }),
      },
      configurable: true,
    })
    cleanups.push(() => { delete window.__machineDebug })
  } catch (error) {
    console.error('Machine: failed to start', error)
    showError()
  }
  return dispose
}

const STYLES = String.raw`
.agentic-factory-3d {
  width: 100%;
  contain: layout;
  color-scheme: dark;
  --bg: #000000;
  --white: #f4f1ea;
  --amber: #ff7a1a;
  --muted: #81848b;
  --line: rgba(244, 241, 234, 0.11);
  box-sizing: border-box;
  margin: 0;
  height: 100%;
  overflow: hidden;
  background: var(--bg);
  font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  color: var(--white);
  font-size: 13px;
  -webkit-font-smoothing: antialiased;
  position: relative;
}
.agentic-factory-3d * {
  box-sizing: border-box;
}
.agentic-factory-3d button,
.agentic-factory-3d a {
  -webkit-tap-highlight-color: transparent;
}
.agentic-factory-3d button {
  font: inherit;
  color: inherit;
  cursor: pointer;
}
.agentic-factory-3d button:focus-visible,
.agentic-factory-3d a:focus-visible {
  outline: 2px solid var(--amber);
  outline-offset: 5px;
}
.agentic-factory-3d #scene {
  position: absolute;
  inset: 0;
  touch-action: none;
  outline: none;
}
.agentic-factory-3d #scene canvas {
  display: block;
  width: 100%;
  height: 100%;
}
.agentic-factory-3d .vignette {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(ellipse at 50% 48%, transparent 30%, rgba(0, 0, 0, 0.12) 64%, rgba(0, 0, 0, 0.65) 100%);
}
.agentic-factory-3d .topbar {
  position: absolute;
  inset: 28px 32px auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  pointer-events: none;
}
.agentic-factory-3d .identity {
  display: flex;
  gap: 13px;
  align-items: center;
}
.agentic-factory-3d .mark {
  width: 30px;
  height: 30px;
  border: 1px solid #55502f;
  border-radius: 9px;
  display: grid;
  place-items: center;
  color: var(--amber);
  background: #1c1b14;
}
.agentic-factory-3d .identity strong {
  display: block;
  font-weight: 550;
  letter-spacing: -0.2px;
  font-size: 13px;
}
.agentic-factory-3d .identity small {
  display: block;
  margin-top: 5px;
  font-size: 9px;
  letter-spacing: 1.55px;
  color: #73777f;
  text-transform: uppercase;
}
.agentic-factory-3d .status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 10px;
  letter-spacing: 0.1px;
  color: #a6a79f;
}
.agentic-factory-3d .status i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--amber);
  box-shadow: 0 0 10px #ff7a1a60;
}
.agentic-factory-3d .status.paused i {
  background: #777;
  box-shadow: none;
}
.agentic-factory-3d .status span:last-child {
  font-variant-numeric: tabular-nums;
  color: #646971;
  margin-left: 12px;
}
.agentic-factory-3d .scene-heading {
  position: absolute;
  top: 110px;
  left: 24%;
  right: 24%;
  pointer-events: none;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 9px;
  letter-spacing: 1.8px;
  color: #959790;
  text-transform: uppercase;
}
.agentic-factory-3d .scene-heading:before {
  content: '';
  width: 22px;
  height: 1px;
  background: var(--amber);
}
.agentic-factory-3d .scene-heading .index {
  margin-left: auto;
  color: #4e535b;
  font-size: 9px;
  letter-spacing: 1px;
}
.agentic-factory-3d .coordinates {
  position: absolute;
  top: 150px;
  right: 33px;
  color: #52575f;
  writing-mode: vertical-rl;
  font: 9px ui-monospace, Menlo, SFMono-Regular, monospace;
  letter-spacing: 1.5px;
  pointer-events: none;
}
.agentic-factory-3d .controls {
  position: absolute;
  bottom: 79px;
  left: 26px;
  right: 26px;
  display: flex;
  align-items: center;
  flex-direction: column;
  gap: 16px;
  z-index: 5;
}
.agentic-factory-3d .mode-bar {
  display: flex;
  gap: 3px;
  align-items: center;
  padding: 5px;
  border: 1px solid #ffffff13;
  border-radius: 12px;
  background: rgba(25, 28, 32, 0.87);
  box-shadow: 0 8px 30px #0003, inset 0 1px 0 #ffffff03;
  backdrop-filter: blur(16px);
}
.agentic-factory-3d .mode-bar button {
  border: 0;
  background: none;
  color: #a2a4a8;
  white-space: nowrap;
  padding: 11px 15px;
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 11px;
  font-weight: 500;
  border-radius: 8px;
  transition: background 0.2s, color 0.2s;
}
.agentic-factory-3d .mode-bar button:hover {
  background: #ffffff08;
  color: var(--white);
}
.agentic-factory-3d .mode-bar button[aria-pressed='true'] {
  background: var(--amber);
  color: #211c0d;
  box-shadow: 0 2px 12px #ff7a1a12;
}
.agentic-factory-3d svg {
  flex-shrink: 0;
  display: block;
}
.agentic-factory-3d .mode-bar svg {
  width: 14px;
  height: 14px;
}
.agentic-factory-3d .camera-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}
.agentic-factory-3d .camera-row .caption {
  font-size: 9px;
  letter-spacing: 1.4px;
  color: #555b65;
  margin-right: 9px;
}
.agentic-factory-3d .camera-row button {
  border: 0;
  background: transparent;
  color: #6e747e;
  padding: 5px 9px;
  font-size: 10px;
  transition: color 0.2s;
}
.agentic-factory-3d .camera-row button:hover,
.agentic-factory-3d .camera-row button[aria-pressed='true'] {
  color: var(--white);
}
.agentic-factory-3d .camera-row button[aria-pressed='true']:after {
  content: '';
  display: block;
  width: 3px;
  height: 3px;
  background: var(--amber);
  border-radius: 50%;
  margin: 5px auto -8px;
}
.agentic-factory-3d .camera-row .divider {
  width: 1px;
  height: 13px;
  background: var(--line);
  margin: 0 8px;
}
.agentic-factory-3d .camera-row #play {
  padding: 5px;
  width: 25px;
  height: 25px;
  display: grid;
  place-items: center;
}
.agentic-factory-3d .footer {
  position: absolute;
  bottom: 25px;
  left: 32px;
  right: 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  pointer-events: none;
}
.agentic-factory-3d .wordmark {
  font-size: 11px;
  letter-spacing: -0.1px;
  color: #6d7178;
  text-decoration: none;
  pointer-events: auto;
}
.agentic-factory-3d .wordmark span {
  color: #a1a49f;
}
.agentic-factory-3d .hint {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #636972;
  font-size: 10px;
}
.agentic-factory-3d .hint svg {
  color: #8c8f91;
}
.agentic-factory-3d .footer-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  font: 9px ui-monospace, Menlo, SFMono-Regular, monospace;
  letter-spacing: 1.5px;
  color: #3f454d;
}
.agentic-factory-3d #labels {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}
.agentic-factory-3d .station-label {
  position: absolute;
  left: 0;
  top: 0;
  opacity: 0;
  transition: opacity 0.3s;
  will-change: transform;
  pointer-events: none;
  min-width: 138px;
}
.agentic-factory-3d .station-label.visible {
  opacity: 1;
}
.agentic-factory-3d .station-label .stem {
  height: 26px;
  width: 1px;
  background: linear-gradient(#ff7a1a00, #ff7a1a70);
  margin: 0 0 0 10px;
}
.agentic-factory-3d .station-label .label-card {
  background: #14171bee;
  backdrop-filter: blur(10px);
  border: 1px solid #ff7a1a40;
  border-radius: 6px;
  padding: 10px 13px;
  box-shadow: 0 4px 20px #0003;
}
.agentic-factory-3d .station-label .label-title {
  font-weight: 550;
  font-size: 12px;
  display: flex;
  gap: 10px;
  align-items: center;
  white-space: nowrap;
}
.agentic-factory-3d .station-label .label-title span {
  color: var(--amber);
  font: 9px ui-monospace, Menlo, monospace;
}
.agentic-factory-3d .station-label .label-meta {
  font-size: 9px;
  color: #8e939c;
  margin: 6px 0 0 24px;
  white-space: nowrap;
}
.agentic-factory-3d #tooltip {
  position: absolute;
  pointer-events: none;
  z-index: 10;
  opacity: 0;
  transition: opacity 0.15s;
  padding: 11px 14px;
  border: 1px solid #ffffff1a;
  background: #171a20ed;
  backdrop-filter: blur(12px);
  box-shadow: 0 8px 32px #0005;
  border-radius: 7px;
  max-width: 240px;
}
.agentic-factory-3d #tooltip.visible {
  opacity: 1;
}
.agentic-factory-3d #tooltip strong {
  font-size: 12px;
  font-weight: 550;
}
.agentic-factory-3d #tooltip strong span {
  font-size: 10px;
  color: var(--amber);
  margin-right: 8px;
}
.agentic-factory-3d #tooltip p {
  font-size: 10px;
  color: #9b9fa7;
  margin: 6px 0 0;
  line-height: 1.5;
}
.agentic-factory-3d #journey {
  position: absolute;
  left: 24%;
  right: 24%;
  top: 148px;
  opacity: 0;
  transform: translateY(-5px);
  transition: 0.4s;
  pointer-events: none;
  display: flex;
  align-items: center;
  gap: 13px;
}
.agentic-factory-3d #journey.visible {
  opacity: 1;
  transform: none;
}
.agentic-factory-3d .journey-icon {
  width: 28px;
  height: 28px;
  border: 1px solid #ff7a1a40;
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: var(--amber);
}
.agentic-factory-3d #journey strong {
  font-size: 11px;
  font-weight: 500;
}
.agentic-factory-3d #journey small {
  display: block;
  font-size: 9px;
  margin-top: 4px;
  color: #7e858d;
}
.agentic-factory-3d #journey .track {
  height: 2px;
  background: #ffffff0b;
  flex: 1;
  margin-left: 8px;
}
.agentic-factory-3d #journey .track i {
  display: block;
  height: 100%;
  background: var(--amber);
  width: 0;
}
.agentic-factory-3d #loading {
  position: absolute;
  left: 50%;
  top: 48%;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  gap: 12px;
  color: #8c8f95;
  font-size: 11px;
  transition: opacity 0.4s;
  z-index: 20;
}
.agentic-factory-3d #loading i {
  height: 18px;
  width: 18px;
  border-radius: 50%;
  border: 1px solid #ff7a1a22;
  border-top-color: var(--amber);
  animation: agentic-factory-3d-spin 1s linear infinite;
}
@keyframes agentic-factory-3d-spin {
  to {
    transform: rotate(360deg);
  }
}
.agentic-factory-3d #loading.done {
  opacity: 0;
  pointer-events: none;
}
.agentic-factory-3d #error {
  position: absolute;
  left: 27.5%;
  right: 27.5%;
  top: 40%;
  border: 1px solid #ff7a1a30;
  background: #191b1f;
  padding: 24px;
  border-radius: 12px;
  display: none;
  font-size: 13px;
  line-height: 1.7;
}
.agentic-factory-3d #error strong {
  color: var(--amber);
  font-weight: 500;
}
.agentic-factory-3d #error p {
  color: #9da1a8;
  margin: 8px 0 0;
}
.agentic-factory-3d #error button {
  border: 1px solid #ffffff22;
  background: #25292e;
  padding: 8px 14px;
  border-radius: 5px;
  margin-top: 14px;
}
.agentic-factory-3d.embed .debug-ui {
  display: none !important;
}
.agentic-factory-3d.embed .vignette {
  background: radial-gradient(ellipse at 71% 48%, transparent 30%, rgba(0, 0, 0, 0.1) 65%, rgba(0, 0, 0, 0.55));
}
.agentic-factory-3d.embed .footer {
  justify-content: flex-end;
}
.agentic-factory-3d.embed .wordmark {
  opacity: 0.65;
}
@media (min-width: 901px) {
  .agentic-factory-3d.embed #loading {
    left: 71%;
  }
  .agentic-factory-3d.embed #error {
    left: 48%;
    right: 7%;
  }
}
@media (min-width: 1600px) {
  .agentic-factory-3d .topbar {
    inset: 38px 46px auto;
  }
  .agentic-factory-3d .scene-heading {
    top: 142px;
  }
  .agentic-factory-3d .controls {
    bottom: 100px;
    gap: 20px;
  }
  .agentic-factory-3d .mode-bar button {
    padding: 13px 20px;
    font-size: 12px;
  }
  .agentic-factory-3d .camera-row button {
    font-size: 11px;
    padding: 5px 12px;
  }
  .agentic-factory-3d .footer {
    bottom: 35px;
    left: 46px;
    right: 46px;
  }
  .agentic-factory-3d #journey {
    top: 182px;
  }
  .agentic-factory-3d .coordinates {
    right: 47px;
    top: 185px;
  }
}
@media (max-width: 900px) {
  .agentic-factory-3d .topbar {
    inset: 24px 22px auto;
  }
  .agentic-factory-3d .identity strong {
    font-size: 12px;
  }
  .agentic-factory-3d .identity small {
    font-size: 8px;
    letter-spacing: 1.1px;
  }
  .agentic-factory-3d .status {
    font-size: 9px;
  }
  .agentic-factory-3d .status span:last-child {
    display: none;
  }
  .agentic-factory-3d .scene-heading {
    left: 22px;
    right: 22px;
    top: 105px;
    font-size: 8px;
    letter-spacing: 1.3px;
  }
  .agentic-factory-3d .coordinates {
    display: none;
  }
  .agentic-factory-3d .controls {
    left: 12px;
    right: 12px;
    bottom: 84px;
    gap: 18px;
  }
  .agentic-factory-3d .mode-bar {
    gap: 1px;
    padding: 4px;
    border-radius: 10px;
  }
  .agentic-factory-3d .mode-bar button {
    padding: 11px 10px;
    font-size: 10px;
    gap: 6px;
  }
  .agentic-factory-3d .mode-bar svg {
    width: 12px;
    height: 12px;
  }
  .agentic-factory-3d .camera-row {
    gap: 0;
  }
  .agentic-factory-3d .camera-row .caption {
    font-size: 8px;
    margin-right: 6px;
  }
  .agentic-factory-3d .camera-row button {
    padding: 5px 8px;
    font-size: 9px;
  }
  .agentic-factory-3d .camera-row .divider {
    margin: 0 5px;
  }
  .agentic-factory-3d .footer {
    bottom: 25px;
    left: 22px;
    right: 22px;
    align-items: flex-end;
  }
  .agentic-factory-3d .hint {
    font-size: 9px;
    max-width: 175px;
    line-height: 1.6;
  }
  .agentic-factory-3d .footer-center {
    display: none;
  }
  .agentic-factory-3d .vignette {
    background: radial-gradient(ellipse at 50% 47%, transparent 20%, #00000080 100%);
  }
  .agentic-factory-3d #loading {
    left: 50%;
  }
  .agentic-factory-3d #error {
    left: 7%;
    right: 7%;
    top: 35%;
  }
  .agentic-factory-3d #journey {
    left: 24px;
    right: 24px;
    top: 143px;
  }
  .agentic-factory-3d .station-label {
    min-width: 100px;
  }
  .agentic-factory-3d .station-label .label-card {
    padding: 7px 9px;
  }
  .agentic-factory-3d .station-label .label-title {
    font-size: 10px;
    gap: 7px;
  }
  .agentic-factory-3d .station-label .label-meta {
    font-size: 8px;
    margin-left: 0;
  }
  .agentic-factory-3d .station-label .stem {
    height: 17px;
  }
  .agentic-factory-3d.embed .vignette {
    background: radial-gradient(ellipse at center, transparent 30%, #00000060 100%);
  }
}
@media (max-width: 360px) {
  .agentic-factory-3d .mode-bar button {
    padding: 10px 7px;
  }
  .agentic-factory-3d .mode-bar svg {
    display: none;
  }
  .agentic-factory-3d .camera-row .caption {
    display: none;
  }
  .agentic-factory-3d .status {
    display: none;
  }
}
@media (max-height: 570px) {
  .agentic-factory-3d .topbar {
    top: 16px;
  }
  .agentic-factory-3d .scene-heading {
    top: 70px;
  }
  .agentic-factory-3d .controls {
    bottom: 50px;
    gap: 8px;
  }
  .agentic-factory-3d .footer {
    bottom: 14px;
  }
  .agentic-factory-3d #journey {
    top: 96px;
  }
  .agentic-factory-3d .mode-bar button {
    padding-top: 8px;
    padding-bottom: 8px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .agentic-factory-3d, .agentic-factory-3d * {
    transition: none !important;
  }
  .agentic-factory-3d #loading i {
    animation: none;
  }
}
`

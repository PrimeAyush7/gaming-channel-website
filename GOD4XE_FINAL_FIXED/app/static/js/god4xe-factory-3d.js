/**
 * GOD4XE GAMING - Interactive 3D Factory Engine
 * Procedural Three.js 3D Machine representing the 5 Core Stations of the GOD4XE Ecosystem:
 * 1. SENSITIVITY CALIBRATOR (DPI, Headshot Matrix, Scope tuning)
 * 2. ANTIBAN SHIELD KERNEL (OB55 Safe, Memory Hook Bypass)
 * 3. VIP GLITCH FORGE (Freestyle Bundle, Max Dress, Weapon Skins)
 * 4. CLOUD VAULT MIRROR (MediaFire & Google Drive fast cloud distribution)
 * 5. DIAMOND ARENA (Custom rooms, Tournaments & Diamond Payouts)
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';

export function initGod4xeFactory(rootId = 'god4xe-factory-root') {
  const root = document.getElementById(rootId);
  if (!root) return;

  const sceneContainer = root.querySelector('#factory-scene-canvas');
  if (!sceneContainer) return;

  const frameWidth = () => root.clientWidth || window.innerWidth;
  const frameHeight = () => root.clientHeight || 650;

  const cleanups = [];
  const listen = (target, type, handler) => {
    target.addEventListener(type, handler);
    cleanups.push(() => target.removeEventListener(type, handler));
  };

  const $ = (id) => root.querySelector(`#${id}`);

  function showError(msg) {
    const loader = $('factory-loading');
    if (loader) loader.classList.add('done');
    const err = $('factory-error');
    if (err) {
      err.style.display = 'block';
      if (msg) {
        const p = err.querySelector('p');
        if (p) p.textContent = msg;
      }
    }
  }

  try {
    const TAU = Math.PI * 2;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(33, frameWidth() / frameHeight(), 0.1, 150);

    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,
        powerPreference: 'high-performance'
      });
    } catch (e) {
      showError('WebGL is not available in your browser.');
      return;
    }

    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, frameWidth() < 900 ? 1.5 : 1.75));
    renderer.setSize(frameWidth(), frameHeight());
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.15;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFShadowMap;
    renderer.localClippingEnabled = true;

    sceneContainer.innerHTML = '';
    sceneContainer.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.065;
    controls.enablePan = false;
    controls.minDistance = 7;
    controls.maxDistance = 55;
    controls.minPolarAngle = 0.09;
    controls.maxPolarAngle = Math.PI * 0.475;
    controls.rotateSpeed = 0.48;
    controls.zoomSpeed = 0.7;

    const pmrem = new THREE.PMREMGenerator(renderer);
    const room = new RoomEnvironment();
    const env = pmrem.fromScene(room, 0.04);
    scene.environment = env.texture;
    scene.environmentIntensity = 0.65;
    room.dispose();
    pmrem.dispose();

    scene.add(new THREE.HemisphereLight(0x00f2fe, 0x1e1b4b, 2.2));

    const key = new THREE.DirectionalLight(0xffffff, 4.2);
    key.position.set(-4, 12, 7);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    key.shadow.bias = -0.0002;
    key.shadow.radius = 4;
    scene.add(key);

    const cyanRim = new THREE.DirectionalLight(0x00f2fe, 3.2);
    cyanRim.position.set(3, 7, -8);
    scene.add(cyanRim);

    const purpleWarm = new THREE.PointLight(0xa855f7, 30, 22, 2);
    purpleWarm.position.set(-4, 5, 3);
    scene.add(purpleWarm);

    const mat = (color, metalness = 0.2, roughness = 0.35, extra = {}) =>
      new THREE.MeshStandardMaterial({ color, metalness, roughness, ...extra });

    const M = {
      body: mat(0x181f2c, 0.8, 0.28),
      base: mat(0x0f1523, 0.88, 0.3),
      edge: mat(0x38bdf8, 0.85, 0.22),
      chrome: mat(0xcbd5e1, 0.92, 0.16),
      dark: mat(0x070b14, 0.6, 0.35),
      rubber: mat(0x020408, 0.1, 0.6),
      cyan: mat(0x00f2fe, 0.6, 0.25),
      purple: mat(0xa855f7, 0.6, 0.25),
      emerald: mat(0x10b981, 0.7, 0.25),
      amber: mat(0xf59e0b, 0.6, 0.25),
      ivory: mat(0xe2e8f0, 0.5, 0.25),
      copper: mat(0xc57e45, 0.85, 0.3),
      black: mat(0x030712, 0, 0.6),
      light: mat(0x00f2fe, 0.2, 0.25, { emissive: 0x00f2fe, emissiveIntensity: 1.6 }),
      purpleLight: mat(0xa855f7, 0.2, 0.25, { emissive: 0xa855f7, emissiveIntensity: 1.6 }),
      greenLight: mat(0x10b981, 0.2, 0.25, { emissive: 0x10b981, emissiveIntensity: 1.5 })
    };

    const geometries = new Map();
    function boxGeo(w, h, d, r = 0.04) {
      const k = `b${w},${h},${d},${r}`;
      if (!geometries.has(k)) {
        geometries.set(k, r ? new RoundedBoxGeometry(w, h, d, 2, Math.min(r, w / 3, h / 3, d / 3)) : new THREE.BoxGeometry(w, h, d));
      }
      return geometries.get(k);
    }

    function box(parent, w, h, d, x, y, z, m = M.body, r = 0.04) {
      const o = new THREE.Mesh(boxGeo(w, h, d, r), m);
      o.position.set(x, y, z);
      o.castShadow = true;
      o.receiveShadow = true;
      parent.add(o);
      return o;
    }

    function cyl(parent, r, h, x, y, z, m = M.chrome, r2 = r, segments = 24) {
      const k = `c${r},${r2},${h},${segments}`;
      if (!geometries.has(k)) geometries.set(k, new THREE.CylinderGeometry(r, r2, h, segments));
      const o = new THREE.Mesh(geometries.get(k), m);
      o.position.set(x, y, z);
      o.castShadow = true;
      o.receiveShadow = true;
      parent.add(o);
      return o;
    }

    function tube(parent, pts, r, m = M.chrome) {
      const curve = new THREE.CatmullRomCurve3(pts.map((p) => new THREE.Vector3(...p)));
      const o = new THREE.Mesh(new THREE.TubeGeometry(curve, Math.max(12, pts.length * 7), r, 8, false), m);
      o.castShadow = true;
      parent.add(o);
      return o;
    }

    function screw(parent, x, y, z) {
      cyl(parent, 0.055, 0.026, x, y, z, M.chrome, undefined, 12);
      box(parent, 0.068, 0.005, 0.009, x, y + 0.014, z, M.dark, 0);
    }

    function canvasTexture(w, h, draw) {
      const c = document.createElement('canvas');
      c.width = w;
      c.height = h;
      const ctx = c.getContext('2d');
      draw(ctx, w, h);
      const t = new THREE.CanvasTexture(c);
      t.colorSpace = THREE.SRGBColorSpace;
      t.anisotropy = Math.min(4, renderer.capabilities.getMaxAnisotropy());
      return { texture: t, canvas: c, ctx };
    }

    function print(ctx, txt, x, y, size = 20, color = '#f1f5f9', weight = 600) {
      ctx.fillStyle = color;
      ctx.font = `${weight} ${size}px 'Rajdhani', -apple-system, sans-serif`;
      ctx.fillText(txt, x, y);
    }

    function screen(parent, w, h, x, y, z, tex) {
      const map = 'texture' in tex ? tex.texture : tex;
      const o = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map, toneMapped: false }));
      o.position.set(x, y, z);
      parent.add(o);
      return o;
    }

    const machine = new THREE.Group();
    scene.add(machine);

    // Floor shadow
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(70, 70), new THREE.ShadowMaterial({ opacity: 0.25 }));
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -0.43;
    floor.receiveShadow = true;
    scene.add(floor);

    // Platform Base
    box(machine, 12.8, 0.38, 8.25, 0, -0.09, 0, M.base, 0.17);
    box(machine, 12.6, 0.055, 8.08, 0, 0.13, 0, M.edge, 0.11);
    box(machine, 12.49, 0.09, 7.96, 0, 0.19, 0, M.body, 0.1);
    box(machine, 12.55, 0.027, 8.02, 0, -0.19, 0, M.dark, 0.06);
    box(machine, 11.9, 0.026, 0.032, 0, -0.17, 4.115, M.light, 0.01);

    for (const x of [-5.6, 5.6]) {
      for (const z of [-3.35, 3.35]) {
        cyl(machine, 0.39, 0.25, x, -0.31, z, M.rubber);
        cyl(machine, 0.29, 0.09, x, -0.4, z, M.dark);
        screw(machine, x, 0.253, z);
      }
    }

    // Base Engraving (GOD4XE Ecosystem Plate)
    const engraving = canvasTexture(1536, 176, (c, w, h) => {
      c.fillStyle = '#060a12';
      c.fillRect(0, 0, w, h);
      c.strokeStyle = '#00f2fe';
      c.lineWidth = 3;
      c.strokeRect(3, 3, w - 6, h - 6);
      print(c, 'GOD4XE', 45, 80, 48, '#00f2fe', 900);
      print(c, '·  CALIBRATOR  ·  ANTIBAN  ·  VIP GLITCH  ·  TOURNAMENTS  ·  DIAMONDS', 255, 80, 27, '#f8fafc', 700);
      print(c, 'PROCEDURAL ESPORTS FACTORY ENGINE    //    THE GATEWAY TO GOD4XE ECOSYSTEM', 47, 134, 19, '#94a3b8', 600);
      print(c, 'CORE V4.5', 1330, 132, 22, '#c084fc', 800);
    });
    const plate = screen(machine, 7.35, 0.84, -0.4, 0.25, 3.51, engraving);
    plate.rotation.x = -Math.PI / 2;

    // 5 GOD4XE Ecosystem Stations
    const definitions = [
      {
        id: 'engine',
        name: 'Sensitivity Calibrator',
        step: 1,
        output: 'DPI Matrix',
        pos: [-4.15, 0.29, -0.65],
        desc: 'Precision headshot matrix: General 100, Red Dot 98, Scope 95, custom DPI calibration.'
      },
      {
        id: 'admin',
        name: 'Antiban Shield Kernel',
        step: 2,
        output: 'Safe Bypass',
        pos: [-1.65, 0.29, -2.03],
        desc: 'OB55 ban-safe memory protection, zero-recoil physics verification & signature patch.'
      },
      {
        id: 'storefront',
        name: 'VIP Glitch Forge',
        step: 3,
        output: 'VIP Config',
        pos: [1.5, 0.29, -2.08],
        desc: 'Freestyle bundle glitch, legendary weapon skins & direct emote injector assembly.'
      },
      {
        id: 'cabinet',
        name: 'Cloud Vault Mirror',
        step: 4,
        output: 'Fast Mirror',
        pos: [4.03, 0.29, 0.12],
        desc: 'Direct MediaFire & Google Drive high-speed verified cloud distribution servers.'
      },
      {
        id: 'cashdesk',
        name: 'Diamond Arena Payouts',
        step: 5,
        output: '💎 Payout',
        pos: [0.93, 0.29, 1.85],
        desc: 'Daily esports custom rooms, Battle Royale tournaments & instant diamond withdrawals.'
      }
    ];

    const stations = [];
    const cutPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 10);
    const shellMaterials = [];
    function shell(m) {
      const s = m.clone();
      s.clippingPlanes = [cutPlane];
      s.clipShadows = true;
      s.side = THREE.DoubleSide;
      shellMaterials.push(s);
      return s;
    }
    const S = { body: shell(M.body), ivory: shell(M.ivory), cyan: shell(M.cyan), purple: shell(M.purple), edge: shell(M.edge) };

    const gears = [];
    function gear(parent, x, y, z, r = 0.3, vertical = false) {
      const g = new THREE.Group();
      g.position.set(x, y, z);
      if (vertical) g.rotation.x = Math.PI / 2;
      parent.add(g);
      cyl(g, r, 0.09, 0, 0, 0, M.copper);
      cyl(g, r * 0.66, 0.105, 0, 0, 0, M.dark);
      cyl(g, r * 0.22, 0.14, 0, 0, 0, M.chrome);
      for (let i = 0; i < 12; i++) {
        const a = (i / 12) * TAU;
        const b = box(g, r * 0.26, 0.085, r * 0.2, Math.cos(a) * r, 0, Math.sin(a) * r, M.copper, 0.008);
        b.rotation.y = -a;
      }
      g.userData.moving = true;
      gears.push({ g, vertical });
      return g;
    }

    const labelsContainer = root.querySelector('#factory-labels');

    definitions.forEach((d, i) => {
      const group = new THREE.Group();
      group.position.fromArray(d.pos);
      machine.add(group);

      const glowMat = M.light.clone();
      glowMat.emissiveIntensity = 0.6;

      box(group, 2.05, 0.12, 1.78, 0, 0.03, 0, M.dark, 0.1);
      box(group, 1.97, 0.03, 1.7, 0, 0.12, 0, glowMat, 0.09);
      box(group, 2.03, 0.17, 1.75, 0, 0.215, 0, M.body, 0.1);
      for (const x of [-0.85, 0.85]) for (const z of [-0.7, 0.7]) screw(group, x, 0.311, z);

      gear(group, -0.35, 0.45, 0, 0.27);
      gear(group, 0.22, 0.45, 0.12, 0.21);
      box(group, 0.6, 0.15, 0.36, 0.52, 0.47, -0.33, M.dark);
      tube(group, [[-0.7, 0.4, -0.4], [-0.55, 0.48, 0.4], [0.35, 0.45, 0.6], [0.7, 0.58, 0.23]], 0.023, M.light);

      const plaque = canvasTexture(512, 116, (c, w, h) => {
        c.fillStyle = '#060a12';
        c.fillRect(0, 0, w, h);
        print(c, String(i + 1).padStart(2, '0'), 24, 76, 42, '#00f2fe', 800);
        print(c, d.name.toUpperCase(), 111, 73, 29, '#f8fafc', 700);
      });
      screen(group, 1.54, 0.345, 0, 0.27, 0.891, plaque);

      let labelEl = null;
      if (labelsContainer) {
        labelEl = document.createElement('div');
        labelEl.className = 'station-label';
        labelEl.innerHTML = `<div class="stem"></div><div class="label-card"><div class="label-title"><span>${String(i + 1).padStart(2, '0')}</span>${d.name}</div><div class="label-meta">Step ${d.step} · ${d.output}</div></div>`;
        labelsContainer.appendChild(labelEl);
        cleanups.push(() => labelEl.remove());
      }

      stations.push({
        ...d,
        group,
        base: new THREE.Vector3(...d.pos),
        glowMat,
        label: labelEl,
        index: i,
        anchor: new THREE.Vector3(0, 2.5, 0)
      });
    });

    // 1. Station Engine: SENSITIVITY CALIBRATOR
    const engine = stations[0].group;
    box(engine, 1.74, 0.62, 1.33, 0, 0.65, -0.05, S.ivory, 0.13);
    box(engine, 1.5, 0.1, 1.16, 0, 0.99, -0.04, S.body, 0.025);
    for (const x of [-0.68, 0.68]) {
      cyl(engine, 0.065, 1.73, x, 1.35, -0.18, M.chrome);
      box(engine, 0.22, 1.8, 0.22, x, 1.37, -0.44, S.ivory, 0.035);
    }
    box(engine, 1.82, 0.27, 0.4, 0, 2.28, -0.35, S.cyan, 0.045);

    const printhead = new THREE.Group();
    engine.add(printhead);
    printhead.position.set(0, 1.9, -0.08);
    printhead.userData.moving = true;
    box(printhead, 0.45, 0.36, 0.44, 0, 0, 0, M.body, 0.05);
    cyl(printhead, 0.11, 0.13, 0, -0.24, 0.03, M.chrome, 0.04);
    box(printhead, 0.24, 0.045, 0.022, 0, 0.09, 0.23, M.light, 0.01);

    const videoTexture = canvasTexture(384, 640, () => {});
    function drawVideo(t) {
      const c = videoTexture.ctx, w = 384, h = 640;
      c.fillStyle = '#060a12';
      c.fillRect(0, 0, w, h);
      c.fillStyle = '#00f2fe';
      c.beginPath();
      c.arc(330, 205, 210, 0, TAU);
      c.fill();
      c.strokeStyle = '#a855f7';
      c.lineWidth = 14;
      for (let i = 0; i < 3; i++) {
        c.beginPath();
        c.ellipse(194, 270, 90 - i * 21, 111, Math.sin(t * 0.25) * 0.3 + 0.4, 0, TAU);
        c.stroke();
      }
      print(c, 'GOD4XE', 28, 57, 26, '#00f2fe', 800);
      print(c, 'CALIBRATOR', 24, 103, 38, '#ffffff', 700);
      c.fillStyle = '#0f172a';
      c.beginPath();
      c.roundRect(25, 465, 334, 123, 12);
      c.fill();
      const texts = ['OB55 Antiban Active', 'Headshot Rate: 98.4%', 'Zero Recoil Synced', 'Verified Safe Mirror'];
      const n = Math.floor(t * 0.7) % 4;
      print(c, texts[n], 45, 505, 23, '#34d399', 700);
      print(c, texts[(n + 1) % 4], 45, 547, 23, '#c084fc', 600);
      c.fillStyle = '#00f2fe';
      c.fillRect(27, 615, Math.max(10, ((t * 0.13) % 1) * 330), 5);
      videoTexture.texture.needsUpdate = true;
    }
    drawVideo(0);

    const outputVideo = new THREE.Group();
    outputVideo.userData.moving = true;
    engine.add(outputVideo);
    box(outputVideo, 0.62, 1.08, 0.055, 0, 1.36, 0.61, M.dark, 0.035);
    screen(outputVideo, 0.56, 0.98, 0, 1.36, 0.641, videoTexture);

    // 2. Station Admin: ANTIBAN SHIELD KERNEL
    const admin = stations[1].group;
    box(admin, 1.9, 0.66, 1.36, 0, 0.67, -0.04, S.body, 0.11);
    const consoleTop = new THREE.Group();
    consoleTop.position.set(0, 1.01, -0.08);
    consoleTop.rotation.x = -0.32;
    admin.add(consoleTop);
    box(consoleTop, 1.76, 0.12, 1.27, 0, 0, 0, S.ivory, 0.04);

    const queue = canvasTexture(640, 340, () => {});
    function drawQueue(t) {
      const c = queue.ctx;
      c.fillStyle = '#060a12';
      c.fillRect(0, 0, 640, 340);
      print(c, 'SECURITY & BYPASS QUEUE', 25, 45, 22, '#34d399', 700);
      print(c, 'OB-55 ACTIVE', 460, 45, 18, '#00f2fe', 600);
      const items = ['OB55 Glitch Tool', 'Headshot DPI Macro', 'Freestyle Max Dress'];
      for (let i = 0; i < 3; i++) {
        const y = 74 + i * 76;
        c.fillStyle = '#0f172a';
        c.beginPath();
        c.roundRect(21, y, 598, 61, 6);
        c.fill();
        c.fillStyle = i === 0 ? '#10b981' : '#64748b';
        c.fillRect(34, y + 10, 27, 41);
        print(c, items[i], 77, y + 29, 20, '#ffffff', 600);
        print(c, i === 0 ? 'PROTECTED & SIGNED' : 'VERIFIED', 77, y + 49, 12, i === 0 ? '#34d399' : '#94a3b8');
        c.fillStyle = '#1e293b';
        c.fillRect(377, y + 26, 214, 7);
        c.fillStyle = i === 0 ? '#00f2fe' : '#a855f7';
        c.fillRect(377, y + 26, i === 0 ? ((t * 0.15) % 1) * 214 : 41 + i * 27, 7);
      }
    }
    drawQueue(0);
    const qs = screen(consoleTop, 1.53, 0.79, 0, 0.067, -0.17, queue);
    qs.rotation.x = -Math.PI / 2;

    // 3. Station Storefront: VIP GLITCH FORGE
    const storefront = stations[2].group;
    box(storefront, 1.35, 0.18, 0.88, 0, 0.44, 0, S.ivory, 0.045);
    cyl(storefront, 0.095, 1.04, 0, 0.93, -0.31, M.chrome);
    box(storefront, 2.42, 1.72, 0.2, 0, 1.94, -0.17, S.ivory, 0.08);

    const webTexture = canvasTexture(896, 592, (c, w, h) => {
      c.fillStyle = '#060a12';
      c.fillRect(0, 0, w, h);
      c.fillStyle = '#0f172a';
      c.fillRect(0, 0, w, 56);
      c.fillStyle = '#00f2fe';
      for (let i = 0; i < 3; i++) {
        c.beginPath();
        c.arc(26 + i * 19, 27, 4, 0, TAU);
        c.fill();
      }
      print(c, 'GOD4XE.ONRENDER.COM', 95, 34, 16, '#94a3b8', 600);
      print(c, 'GOD4XE VIP ASSETS', 33, 100, 22, '#00f2fe', 800);
      print(c, 'Guides    Sensitivity    Tournaments', 490, 98, 14, '#94a3b8');
      c.fillStyle = '#1e1b4b';
      c.beginPath();
      c.roundRect(32, 131, 287, 401, 10);
      c.fill();
      print(c, 'OB55 GLITCH', 52, 181, 29, '#00f2fe', 800);
      print(c, 'ANTIBAN SKIN', 52, 220, 29, '#ffffff', 700);
      print(c, 'VIP Config File', 359, 197, 36, '#ffffff', 700);
      print(c, 'Dominate every lobby with', 362, 250, 18, '#94a3b8');
      print(c, 'anti-ban protected configurations.', 362, 280, 18, '#94a3b8');
      c.fillStyle = '#00f2fe';
      c.beginPath();
      c.roundRect(359, 447, 279, 62, 7);
      c.fill();
      print(c, 'DOWNLOAD NOW ↗', 380, 486, 22, '#05070f', 800);
    });
    screen(storefront, 2.16, 1.43, 0, 1.95, 0.011, webTexture);

    // 4. Station Cabinet: CLOUD VAULT MIRROR
    const cabinet = stations[3].group;
    box(cabinet, 1.75, 1.77, 1.02, 0, 1.24, -0.13, S.body, 0.12);
    box(cabinet, 1.58, 0.13, 1.09, 0, 2.16, -0.13, S.purple, 0.04);

    const orderTex = canvasTexture(480, 460, (c, w, h) => {
      c.fillStyle = '#060a12';
      c.fillRect(0, 0, w, h);
      print(c, 'VERIFIED CLOUD MIRRORS', 30, 51, 24, '#00f2fe', 700);
      print(c, 'OB55 Live Updates · 3 Mirrors', 30, 81, 15, '#94a3b8');
      const files = ['OB55 Antiban Glitch', 'Headshot DPI Macro', 'CS 4v4 Tournament'];
      files.forEach((n, i) => {
        const y = 110 + i * 100;
        c.fillStyle = '#0f172a';
        c.beginPath();
        c.roundRect(22, y, 436, 83, 8);
        c.fill();
        c.fillStyle = ['#00f2fe', '#a855f7', '#10b981'][i];
        c.beginPath();
        c.arc(58, y + 40, 19, 0, TAU);
        c.fill();
        print(c, '⚡', 48, y + 47, 20, '#000', 800);
        print(c, n, 93, y + 33, 21, '#ffffff', 600);
        print(c, ['12.4 MB · MediaFire Mirror', '4.1 MB · Google Drive', '100% Ban-Safe Verified'][i], 93, y + 58, 14, '#94a3b8');
      });
    });
    screen(cabinet, 1.31, 1.255, 0, 1.37, 0.44, orderTex);

    // 5. Station Cashdesk: DIAMOND ARENA PAYOUTS
    const cashdesk = stations[4].group;
    box(cashdesk, 1.91, 0.63, 1.32, 0, 0.65, -0.06, S.ivory, 0.12);
    box(cashdesk, 1.13, 0.46, 0.19, -0.35, 1.98, -0.56, S.body, 0.045);

    const cashTex = canvasTexture(512, 176, () => {});
    function drawCash() {
      const c = cashTex.ctx;
      c.fillStyle = '#060a12';
      c.fillRect(0, 0, 512, 176);
      print(c, 'DIAMOND PRIZE CREDITED', 22, 44, 22, '#34d399', 700);
      print(c, '+ 500 💎', 26, 131, 66, '#00f2fe', 800);
    }
    drawCash();
    screen(cashdesk, 1.015, 0.349, -0.35, 1.98, -0.459, cashTex);

    const receipt = new THREE.Group();
    receipt.position.set(0.59, 1.37, -0.1);
    receipt.userData.moving = true;
    cashdesk.add(receipt);

    const receiptTex = canvasTexture(280, 540, (c, w, h) => {
      c.fillStyle = '#0f172a';
      c.fillRect(0, 0, w, h);
      print(c, 'GOD4XE ARENA', 25, 52, 24, '#00f2fe', 800);
      print(c, 'REWARD VOUCHER', 32, 87, 18, '#94a3b8');
      c.strokeStyle = '#334155';
      c.setLineDash([5, 6]);
      c.beginPath();
      c.moveTo(22, 115);
      c.lineTo(258, 115);
      c.stroke();
      print(c, 'Tournament: CS 4v4', 25, 154, 18, '#ffffff');
      print(c, 'Prize: 500 Diamonds', 25, 190, 18, '#34d399');
      print(c, 'STATUS: PAID ✓', 25, 263, 26, '#10b981', 800);
      print(c, 'Thank you player!', 25, 317, 20, '#94a3b8');
      for (let i = 0; i < 44; i++) {
        c.fillStyle = '#00f2fe';
        c.fillRect(25 + i * 5, 370, 1 + (i % 3), 83);
      }
      print(c, 'VOUCHER #0055', 70, 496, 16, '#64748b');
    });
    const rp = screen(receipt, 0.41, 0.83, 0, 0.415, 0.01, receiptTex);
    rp.material.side = THREE.DoubleSide;
    receipt.rotation.x = -0.16;

    // Conveyor Belt
    const path = new THREE.CatmullRomCurve3(
      [
        [-3.95, 0.84, 0.65], [-3.1, 0.84, -0.12], [-1.45, 0.84, -0.79], [1.32, 0.84, -0.8],
        [3.3, 0.84, 0.19], [3.43, 0.84, 1.21], [1.35, 0.84, 2.7], [-1.4, 0.84, 2.52], [-3.54, 0.84, 1.65]
      ].map((p) => new THREE.Vector3(...p)),
      true, 'catmullrom', 0.25
    );
    const belt = new THREE.Group();
    machine.add(belt);
    const frameMesh = new THREE.Mesh(new THREE.TubeGeometry(path, 150, 0.35, 8, true), M.dark);
    frameMesh.scale.y = 0.3;
    frameMesh.position.y = 0.51;
    belt.add(frameMesh);

    const beltCount = 148;
    const beltSlats = new THREE.InstancedMesh(boxGeo(0.135, 0.065, 0.63, 0.012), M.body, beltCount);
    beltSlats.receiveShadow = true;
    belt.add(beltSlats);
    const dummy = new THREE.Object3D(), pVec = new THREE.Vector3(), tVec = new THREE.Vector3();
    function updateBelt(t) {
      for (let i = 0; i < beltCount; i++) {
        const u = (i / beltCount + t * 0.012) % 1;
        path.getPointAt(u, pVec);
        path.getTangentAt(u, tVec);
        dummy.position.copy(pVec);
        dummy.rotation.set(0, -Math.atan2(tVec.z, tVec.x), 0);
        dummy.updateMatrix();
        beltSlats.setMatrixAt(i, dummy.matrix);
      }
      beltSlats.instanceMatrix.needsUpdate = true;
    }

    // Geometry optimization
    function compact(group) {
      for (const child of [...group.children]) if (child.isGroup) compact(child);
      const buckets = new Map();
      for (const object of group.children) {
        if (!object.isMesh || object.isInstancedMesh || object.userData.moving || Array.isArray(object.material)) continue;
        const key = object.material.uuid;
        if (!buckets.has(key)) buckets.set(key, []);
        buckets.get(key).push(object);
      }
      for (const list of buckets.values()) {
        if (list.length < 2) continue;
        const geos = list.map((m) => {
          m.updateMatrix();
          const g = m.geometry.index ? m.geometry.toNonIndexed() : m.geometry.clone();
          return g.applyMatrix4(m.matrix);
        });
        const merged = mergeGeometries(geos, false);
        for (const geo of geos) geo.dispose();
        if (!merged) continue;
        const mesh = new THREE.Mesh(merged, list[0].material);
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        for (const m of list) group.remove(m);
        group.add(mesh);
      }
    }
    compact(machine);

    stations.forEach((s) => s.group.traverse((o) => { o.userData.station = s.id; }));
    const pickables = stations.map((s) => s.group);

    let mode = 'assembled', cameraMode = 'overview', playing = true;
    let simTime = 0, spread = 0, selected = 'engine', hovered = null;
    let width = frameWidth(), height = frameHeight(), mobile = width <= 900;
    let lastInteraction = performance.now(), dragging = false, wasDragged = false, downX = 0, downY = 0;
    let cameraAnimating = true, flightTime = 0, lastDraw = -1;

    const desiredPosition = new THREE.Vector3(), desiredTarget = new THREE.Vector3(0, 1, 0);
    const viewDirection = new THREE.Vector3(10.5, 10.8, 17).normalize();
    let baseDistance = 25;

    function layoutCamera() {
      width = frameWidth();
      height = frameHeight();
      mobile = width <= 900;
      renderer.setSize(width, height);
      camera.aspect = width / height;
      baseDistance = mobile ? 28 : 23;
      controls.maxDistance = Math.max(55, baseDistance * 1.6);
      camera.updateProjectionMatrix();
      setCameraGoal();
    }

    function setCameraGoal() {
      const expand = mode === 'stations' ? 1.2 : 1;
      if (cameraMode === 'station') {
        const s = stations.find((st) => st.id === selected) || stations[0];
        desiredTarget.copy(s.group.position).add(new THREE.Vector3(0, 1.25, 0));
        desiredPosition.copy(desiredTarget).addScaledVector(viewDirection, mobile ? 10 : 13);
      } else if (cameraMode === 'side') {
        desiredPosition.set(13, 5, 20).normalize().multiplyScalar(baseDistance * expand).add(desiredTarget);
      } else if (cameraMode === 'top') {
        desiredPosition.set(0.01, baseDistance * expand, 0.8).add(desiredTarget);
      } else {
        desiredPosition.copy(viewDirection).multiplyScalar(baseDistance * expand).add(desiredTarget);
      }
      cameraAnimating = true;
    }

    function syncButtons() {
      root.querySelectorAll('[data-factory-mode]').forEach((b) => {
        b.classList.toggle('active', b.dataset.factoryMode === mode);
      });
      root.querySelectorAll('[data-factory-camera]').forEach((b) => {
        b.classList.toggle('active', b.dataset.factoryCamera === cameraMode);
      });
      const journey = $('factory-journey');
      if (journey) journey.classList.toggle('visible', mode === 'order');
    }

    function setMode(newMode) {
      mode = newMode;
      lastInteraction = performance.now();
      if (mode === 'order') { simTime = 0; lastDraw = -1; playing = true; cameraMode = 'overview'; }
      setCameraGoal();
      syncButtons();
    }

    function setCamera(newCam) {
      cameraMode = newCam;
      lastInteraction = performance.now();
      flightTime = 0;
      setCameraGoal();
      syncButtons();
    }

    // Attach UI listeners
    root.querySelectorAll('[data-factory-mode]').forEach((b) => {
      listen(b, 'click', () => setMode(b.dataset.factoryMode));
    });
    root.querySelectorAll('[data-factory-camera]').forEach((b) => {
      listen(b, 'click', () => setCamera(b.dataset.factoryCamera));
    });

    const playBtn = $('factory-play');
    if (playBtn) {
      listen(playBtn, 'click', () => {
        playing = !playing;
        playBtn.classList.toggle('active', !playing);
        playBtn.title = playing ? 'Pause Animation' : 'Play Animation';
      });
    }

    layoutCamera();
    camera.position.copy(desiredPosition);
    controls.target.copy(desiredTarget);
    controls.update();

    listen(window, 'resize', layoutCamera);

    // Raycaster hover & click
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const tooltip = $('factory-tooltip');

    function hitStation(x, y) {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.set(((x - rect.left) / width) * 2 - 1, -((y - rect.top) / height) * 2 + 1);
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects(pickables, true);
      return hits.length ? stations.find((s) => s.id === hits[0].object.userData.station) : null;
    }

    listen(renderer.domElement, 'pointermove', (e) => {
      const s = hitStation(e.clientX, e.clientY);
      hovered = s ? s.id : null;
      renderer.domElement.style.cursor = s ? 'pointer' : 'grab';
      if (tooltip) {
        tooltip.classList.toggle('visible', !!s);
        if (s) {
          const strong = tooltip.querySelector('strong');
          const p = tooltip.querySelector('p');
          if (strong) strong.innerHTML = `<span>${String(s.index + 1).padStart(2, '0')}</span>${s.name}`;
          if (p) p.textContent = s.desc;
          const rect = root.getBoundingClientRect();
          tooltip.style.left = Math.min(width - 250, Math.max(10, e.clientX - rect.left + 16)) + 'px';
          tooltip.style.top = Math.max(10, Math.min(height - 90, e.clientY - rect.top - 60)) + 'px';
        }
      }
    });

    listen(renderer.domElement, 'click', (e) => {
      const s = hitStation(e.clientX, e.clientY);
      if (s) {
        selected = s.id;
        cameraMode = 'station';
        setCameraGoal();
        syncButtons();
      }
    });

    let lastFrame = performance.now();
    function animate(now) {
      requestAnimationFrame(animate);
      const dt = Math.max(0, Math.min((now - lastFrame) / 1000, 0.045));
      lastFrame = now;

      if (playing) {
        simTime += dt;
        flightTime += dt;
      }
      const t = simTime;
      const smooth = 1 - Math.exp(-dt * 5);

      spread = THREE.MathUtils.lerp(spread, mode === 'stations' ? 1 : 0, smooth);
      cutPlane.constant = THREE.MathUtils.lerp(cutPlane.constant, mode === 'cutaway' ? 0.99 : 10, smooth);

      stations.forEach((s, i) => {
        s.group.position.copy(s.base);
        s.group.position.x *= 1 + spread * 0.29;
        s.group.position.z *= 1 + spread * 0.37;
        s.group.position.y += spread * (i % 2 ? 0.32 : 0.55);
        s.glowMat.emissiveIntensity = THREE.MathUtils.lerp(
          s.glowMat.emissiveIntensity,
          hovered === s.id || (cameraMode === 'station' && selected === s.id) ? 3.5 : 0.6,
          smooth
        );
      });

      gears.forEach(({ g, vertical }, i) => {
        if (vertical) g.rotation.z = t * (i % 2 ? -1 : 1) * 1.1;
        else g.rotation.y = t * (i % 2 ? -1 : 1) * 1.1;
      });

      printhead.position.x = Math.sin(t * 1.5) * 0.42;

      if (t - lastDraw > 1 / 18 || lastDraw < 0) {
        drawVideo(t);
        drawQueue(t);
        queue.texture.needsUpdate = true;
        updateBelt(t);
        lastDraw = t;
      }

      if (cameraAnimating && !dragging) {
        const speed = 1 - Math.exp(-dt * 3);
        camera.position.lerp(desiredPosition, speed);
        controls.target.lerp(desiredTarget, speed);
        if (camera.position.distanceTo(desiredPosition) < 0.02) cameraAnimating = false;
      }

      controls.autoRotate = playing && !dragging && !cameraAnimating && cameraMode === 'overview' && now - lastInteraction > 4000;
      controls.autoRotateSpeed = 0.35;
      controls.update();

      renderer.render(scene, camera);
    }
    requestAnimationFrame(animate);

    const loader = $('factory-loading');
    if (loader) loader.classList.add('done');

  } catch (err) {
    console.error('Factory 3D Engine failed to initialize:', err);
    showError();
  }
}

// Auto-boot on DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => initGod4xeFactory());
} else {
  initGod4xeFactory();
}

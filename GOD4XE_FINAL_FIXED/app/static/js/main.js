/**
 * GOD4XE GAMING - Master Script (v3.4.0 21st.dev Dimensional Field Engine)
 * - Three.js WebGL Simplex Noise Background Shader
 * - 4 Floating 3D Dark Glass Spheres with Fresnel Refraction
 * - Live Vector Coordinate Tracker (Mouse & Touch)
 * - Interactive Void / Aurora Real-time Shader Theme Switcher
 * - GSAP Masked-word Reveal Animations & Descend Looper
 * - Bulletproof Touch & Click HUD Quick Preview Popover Close Handlers
 * - Zero Layout Shift Mobile Overflow Protection
 */

document.addEventListener('DOMContentLoaded', () => {
  initCursorGlow();
  initMobileNav();
  initCardMotionAndLighting();
  initAnalyticsTracking();
  initAppleHardwareShowcase();
  initDimensionalWebGL();
  initDimensionalUI();
  initArticleSlideDrawer();
});

/* --------------------------------------------------------------------------
   CURSOR LIGHTING (DESKTOP ONLY)
   -------------------------------------------------------------------------- */
function initCursorGlow() {
  const isTouch = window.matchMedia('(pointer: coarse)').matches || ('ontouchstart' in window);
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  
  if (isTouch || prefersReducedMotion || window.innerWidth <= 1024) {
    const existing = document.getElementById('cursor-glow');
    if (existing) existing.remove();
    return;
  }

  let glowEl = document.getElementById('cursor-glow');
  if (!glowEl) {
    glowEl = document.createElement('div');
    glowEl.id = 'cursor-glow';
    document.body.appendChild(glowEl);
  }

  let mouseX = window.innerWidth / 2;
  let mouseY = window.innerHeight / 2;
  let currentX = mouseX;
  let currentY = mouseY;
  let fadeTimeout = null;

  document.addEventListener('mousemove', (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;
    glowEl.style.opacity = '1';
    clearTimeout(fadeTimeout);
    fadeTimeout = setTimeout(() => {
      glowEl.style.opacity = '0.3';
    }, 2500);
  }, { passive: true });

  document.addEventListener('mouseleave', () => {
    glowEl.style.opacity = '0';
  });

  function animateCursor() {
    currentX += (mouseX - currentX) * 0.16;
    currentY += (mouseY - currentY) * 0.16;
    
    glowEl.style.left = `${currentX}px`;
    glowEl.style.top = `${currentY}px`;
    
    requestAnimationFrame(animateCursor);
  }
  requestAnimationFrame(animateCursor);
}

/* --------------------------------------------------------------------------
   VANGUARD 3D DIMENSIONAL WEBGL ARCHITECTURE (21st.dev Engine)
   -------------------------------------------------------------------------- */
function initDimensionalWebGL() {
  const canvas = document.getElementById('webgl-canvas');
  if (!canvas || typeof THREE === 'undefined') return;

  const renderer = new THREE.WebGLRenderer({ 
    canvas, 
    alpha: true, 
    antialias: false,
    powerPreference: "high-performance"
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  const scene = new THREE.Scene();
  const parent = canvas.parentElement;
  const initialWidth = parent ? parent.clientWidth : window.innerWidth;
  const initialHeight = parent ? parent.clientHeight : window.innerHeight;
  const camera = new THREE.PerspectiveCamera(45, initialWidth / (initialHeight || 1), 0.1, 100);
  camera.position.z = 12;

  const uniforms = {
    u_time: { value: 0 },
    u_resolution: { value: new THREE.Vector2(initialWidth, initialHeight) },
    u_color1: { value: new THREE.Color(0.0, 0.8, 0.7) }, // Cyan
    u_color2: { value: new THREE.Color(0.4, 0.0, 0.9) }  // Deep Purple
  };

  const snoiseLogic = `
    vec3 permute(vec3 x) { return mod(((x*34.0)+1.0)*x, 289.0); }
    float snoise(vec2 v){
      const vec4 C = vec4(0.211324865405187, 0.366025403784439, -0.577350269189626, 0.024390243902439);
      vec2 i  = floor(v + dot(v, C.yy) );
      vec2 x0 = v -   i + dot(i, C.xx);
      vec2 i1;
      i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
      vec4 x12 = x0.xyxy + C.xxzz;
      x12.xy -= i1;
      i = mod(i, 289.0);
      vec3 p = permute( permute( i.y + vec3(0.0, i1.y, 1.0 )) + i.x + vec3(0.0, i1.x, 1.0 ));
      vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy), dot(x12.zw,x12.zw)), 0.0);
      m = m*m ; m = m*m ;
      vec3 x = 2.0 * fract(p * C.www) - 1.0;
      vec3 h = abs(x) - 0.5;
      vec3 ox = floor(x + 0.5);
      vec3 a0 = x - ox;
      m *= 1.79284291400159 - 0.85373472095314 * ( a0*a0 + h*h );
      vec3 g;
      g.x  = a0.x  * x0.x  + h.x  * x0.y;
      g.yz = a0.yz * x12.xz + h.yz * x12.yw;
      return 130.0 * dot(m, g);
    }
  `;

  // Background Shader Plane
  const bgMaterial = new THREE.ShaderMaterial({
    vertexShader: `void main() { gl_Position = vec4(position, 1.0); }`,
    fragmentShader: `
      uniform float u_time;
      uniform vec2 u_resolution;
      uniform vec3 u_color1;
      uniform vec3 u_color2;
      ${snoiseLogic}
      void main() {
        vec2 uv = gl_FragCoord.xy / u_resolution.xy;
        uv.x *= u_resolution.x / u_resolution.y;

        vec3 baseColor = vec3(0.02, 0.02, 0.03);
        vec2 st = uv * 0.5;
        st += vec2(snoise(st + u_time * 0.04), snoise(st - u_time * 0.04)) * 0.4;

        float beam = smoothstep(0.2, 0.9, snoise(vec2(st.x + st.y * 2.0 - u_time * 0.1, u_time * 0.03)));
        vec3 glow = mix(u_color1, u_color2, snoise(uv * 2.0 + u_time * 0.15) * 0.5 + 0.5);

        float dist = distance(gl_FragCoord.xy / u_resolution.xy, vec2(0.5));
        float vignette = smoothstep(1.5, 0.1, dist);
        
        vec3 edgeColor = vec3(0.01, 0.01, 0.015);
        vec3 colorGlow = mix(baseColor, glow, beam * 0.6);

        gl_FragColor = vec4(mix(edgeColor, colorGlow, vignette), 1.0);
      }
    `,
    uniforms,
    depthWrite: false,
    depthTest: false
  });

  const bgMesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), bgMaterial);
  bgMesh.position.z = -15;
  scene.add(bgMesh);

  // Dark Glass Sphere Shader with Fresnel
  const glassMaterial = new THREE.ShaderMaterial({
    vertexShader: `
      varying vec3 vNormal;
      void main() {
        vNormal = normalize(normalMatrix * normal);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform float u_time;
      uniform vec2 u_resolution;
      uniform vec3 u_color1;
      uniform vec3 u_color2;
      varying vec3 vNormal;
      ${snoiseLogic}
      void main() {
        vec2 uv = gl_FragCoord.xy / u_resolution.xy;
        uv += vNormal.xy * 0.2; 
        uv.x *= u_resolution.x / u_resolution.y;

        vec3 baseColor = vec3(0.04, 0.04, 0.06);
        vec2 st = uv * 0.6;
        st += vec2(snoise(st + u_time * 0.06), snoise(st - u_time * 0.06)) * 0.35;

        float beam = smoothstep(0.1, 0.9, snoise(vec2(st.x + st.y * 1.8 - u_time * 0.12, u_time * 0.02)));
        vec3 glow = mix(u_color1, u_color2, snoise(uv * 1.8 + u_time * 0.12) * 0.5 + 0.5);

        float fresnel = dot(vec3(0.0, 0.0, 1.0), vNormal);
        fresnel = clamp(1.0 - fresnel, 0.0, 1.0);
        fresnel = pow(fresnel, 2.5);

        vec3 finalColor = mix(baseColor, glow, clamp((beam * 0.5) + (fresnel * 0.8), 0.0, 1.0));
        gl_FragColor = vec4(finalColor, 0.95);
      }
    `,
    uniforms,
    transparent: true
  });

  const sphereGeo = new THREE.SphereGeometry(1, 48, 48);
  const spheres = [];

  const sphereData = [
    { scale: 3.6, x: 5.5, y: -1.2, z: -1.5, speed: 0.002 },   
    { scale: 1.8, x: -5.2, y: -3.5, z: 2.2, speed: 0.004 },  
    { scale: 1.1, x: -3.8, y: 3.6, z: -2.0, speed: 0.005 },  
    { scale: 0.75, x: 2.6, y: 4.8, z: 3.5, speed: 0.008 }      
  ];

  sphereData.forEach(data => {
    const mesh = new THREE.Mesh(sphereGeo, glassMaterial);
    mesh.scale.set(data.scale, data.scale, data.scale);
    mesh.position.set(data.x, data.y, data.z);
    scene.add(mesh);
    spheres.push({
      mesh,
      baseY: data.y,
      speed: data.speed,
      offset: Math.random() * Math.PI * 2
    });
  });

  let mouseX = 0, mouseY = 0;
  const coordDisplay = document.getElementById('coord-display');

  const updateCoordinates = (clientX, clientY) => {
    if (!parent) return;
    const heroRect = parent.getBoundingClientRect();
    mouseX = (clientX - (heroRect.left + heroRect.width / 2));
    mouseY = (clientY - (heroRect.top + heroRect.height / 2));
    if (coordDisplay) {
      coordDisplay.innerText = `${(clientX / window.innerWidth).toFixed(4)}, ${(clientY / window.innerHeight).toFixed(4)}`;
    }
  };

  document.addEventListener('mousemove', (e) => {
    updateCoordinates(e.clientX, e.clientY);
  }, { passive: true });

  document.addEventListener('touchmove', (e) => {
    if (e.touches && e.touches[0]) {
      updateCoordinates(e.touches[0].clientX, e.touches[0].clientY);
    }
  }, { passive: true });

  const resize = () => {
    if (!parent) return;
    const width = parent.clientWidth;
    const height = parent.clientHeight || 500;
    renderer.setSize(width, height);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();

    const dist = camera.position.z - bgMesh.position.z;
    const vFov = camera.fov * Math.PI / 180;
    const planeHeight = 2 * Math.tan(vFov / 2) * dist;
    bgMesh.scale.set(planeHeight * camera.aspect / 2, planeHeight / 2, 1);
    
    uniforms.u_resolution.value.set(width, height);
  };

  window.addEventListener('resize', resize, { passive: true });
  resize();

  // Custom 21st.dev Theme Toggle: Void <-> Aurora
  let isAurora = false;
  const themeToggle = document.getElementById('theme-toggle');
  
  if (themeToggle) {
    const handleToggle = (e) => {
      e.preventDefault();
      isAurora = !isAurora;
      themeToggle.setAttribute('aria-checked', isAurora.toString());
      const thumb = document.getElementById('toggle-thumb');
      
      if (isAurora) {
        if (thumb) {
          thumb.style.transform = 'translateX(22px)';
          thumb.style.backgroundColor = '#FF007F';
          thumb.style.boxShadow = '0 0 10px #FF007F';
        }
        if (typeof gsap !== 'undefined') {
          gsap.to(uniforms.u_color1.value, { r: 1.0, g: 0.0, b: 0.5, duration: 1.5 });
          gsap.to(uniforms.u_color2.value, { r: 1.0, g: 0.3, b: 0.0, duration: 1.5 });
        }
      } else {
        if (thumb) {
          thumb.style.transform = 'translateX(0px)';
          thumb.style.backgroundColor = '#00FFCC';
          thumb.style.boxShadow = '0 0 10px #00FFCC';
        }
        if (typeof gsap !== 'undefined') {
          gsap.to(uniforms.u_color1.value, { r: 0.0, g: 0.8, b: 0.7, duration: 1.5 });
          gsap.to(uniforms.u_color2.value, { r: 0.4, g: 0.0, b: 0.9, duration: 1.5 });
        }
      }
    };

    themeToggle.addEventListener('click', handleToggle);
    themeToggle.addEventListener('touchend', handleToggle, { passive: false });
  }

  const clock = new THREE.Clock();
  const animate = () => {
    requestAnimationFrame(animate);
    const time = clock.getElapsedTime();
    
    uniforms.u_time.value = time;

    camera.position.x += (mouseX * 0.003 - camera.position.x) * 0.05;
    camera.position.y += (-mouseY * 0.003 - camera.position.y) * 0.05;
    camera.lookAt(scene.position);

    spheres.forEach(s => {
      s.mesh.position.y = s.baseY + Math.sin(time * s.speed * 120 + s.offset) * 0.4;
      s.mesh.rotation.x = time * s.speed * 18;
      s.mesh.rotation.y = time * s.speed * 24;
    });

    renderer.render(scene, camera);
  };

  animate();
}

/* --------------------------------------------------------------------------
   DIMENSIONAL UI & GSAP TIMELINES
   -------------------------------------------------------------------------- */
function initDimensionalUI() {
  if (typeof gsap === 'undefined') return;

  if (typeof ScrollTrigger !== 'undefined') {
    gsap.registerPlugin(ScrollTrigger);
  }

  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (prefersReduced) return;

  gsap.set('.gsap-reveal-text', { y: 20, opacity: 0 });
  gsap.set('.gsap-reveal', { opacity: 0 });
  gsap.set('.masked-word', { y: "110%" });

  const tl = gsap.timeline({ defaults: { ease: "power3.out" } });

  tl.to('.gsap-reveal', { opacity: 1, duration: 0.9, delay: 0.15 })
    .to('.gsap-reveal-text', { y: 0, opacity: 1, duration: 0.8, stagger: 0.08 }, "-=0.7")
    .to('.masked-word', { y: "0%", duration: 0.85, stagger: 0.04 }, "-=0.6");

  gsap.to('.scroll-line', {
    yPercent: 150,
    opacity: 0,
    repeat: -1,
    duration: 2.2,
    ease: "power2.inOut",
    onRepeat: function() {
      if (this.targets()[0]) {
        gsap.set(this.targets()[0], { yPercent: -100, opacity: 1 });
      }
    }
  });
}

/* --------------------------------------------------------------------------
   CARD MOTION & SUBTLE HOVER ZOOM (SMOOTH & CLEAN, NO POPUPS)
   -------------------------------------------------------------------------- */
function initCardMotionAndLighting() {
  const cards = document.querySelectorAll('.cyber-card');
  if (!cards.length) return;

  const isTouch = window.matchMedia('(pointer: coarse)').matches || ('ontouchstart' in window);
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  cards.forEach(card => {
    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      
      card.style.setProperty('--card-mouse-x', `${x}px`);
      card.style.setProperty('--card-mouse-y', `${y}px`);

      if (!isTouch && !prefersReduced && window.innerWidth > 1024 && !card.classList.contains('no-tilt')) {
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        const rotateX = ((y - centerY) / centerY) * -2.5;
        const rotateY = ((x - centerX) / centerX) * 2.5;
        
        // Post cards get subtle smooth zoom-in (scale 1.025)
        if (card.classList.contains('post-card')) {
          card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-5px) scale(1.025)`;
        } else {
          card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-5px)`;
        }
      }
    }, { passive: true });

    // When cursor leaves the card, immediately & smoothly reset transform
    card.addEventListener('mouseleave', () => {
      card.style.transform = '';
    });
  });
}

/* --------------------------------------------------------------------------
   MOBILE NAVIGATION DRAWER
   -------------------------------------------------------------------------- */
function initMobileNav() {
  const toggleBtn = document.getElementById('mobile-nav-toggle');
  const drawer = document.getElementById('mobile-drawer');
  const closeBtn = document.getElementById('mobile-drawer-close');
  const header = document.querySelector('.site-header');

  if (!toggleBtn || !drawer) return;

  function updateDrawerPosition() {
    if (header) {
      drawer.style.top = `${header.offsetHeight}px`;
    }
  }

  function openDrawer() {
    updateDrawerPosition();
    drawer.classList.add('open');
    toggleBtn.setAttribute('aria-expanded', 'true');
    document.body.classList.add('drawer-open');
  }

  function closeDrawer() {
    drawer.classList.remove('open');
    toggleBtn.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('drawer-open');
  }

  toggleBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    if (drawer.classList.contains('open')) {
      closeDrawer();
    } else {
      openDrawer();
    }
  });

  if (closeBtn) {
    closeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      closeDrawer();
    });
  }

  window.addEventListener('resize', () => {
    if (drawer.classList.contains('open')) {
      updateDrawerPosition();
    }
    if (window.innerWidth > 768 && drawer.classList.contains('open')) {
      closeDrawer();
    }
  }, { passive: true });

  document.addEventListener('click', (e) => {
    if (drawer.classList.contains('open') && !drawer.contains(e.target) && e.target !== toggleBtn) {
      closeDrawer();
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && drawer.classList.contains('open')) {
      closeDrawer();
    }
  });
}

/* --------------------------------------------------------------------------
   ANALYTICS CLICK TRACKING
   -------------------------------------------------------------------------- */
function initAnalyticsTracking() {
  const downloadBtns = document.querySelectorAll('[data-track-download]');
  downloadBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const postId = btn.getAttribute('data-post-id');
      if (postId) {
        try {
          navigator.sendBeacon(`/api/track/download/${postId}`, new FormData());
        } catch (err) {}
      }
    });
  });

  const ytTriggers = document.querySelectorAll('[data-track-youtube]');
  ytTriggers.forEach(trigger => {
    trigger.addEventListener('click', () => {
      const postId = trigger.getAttribute('data-post-id') || 0;
      try {
        navigator.sendBeacon(`/api/track/youtube/${postId}`, new FormData());
      } catch (err) {}
    });
  });
}

/* --------------------------------------------------------------------------
   SIMULTANEOUS APPLE HARDWARE SHOWCASE ENGINE (PARALLEL MACBOOK & IPHONE)
   - MacBook Pro 16" (macOS Sequoia) + iPhone 16 Pro (iOS 18)
   - Running at the EXACT SAME TIME in full synchronization!
   -------------------------------------------------------------------------- */
function initAppleHardwareShowcase() {
  const stage = document.getElementById('hero-devices-stage');

  // MacBook elements
  const macLid = document.getElementById('macbook-lid');
  const macHandHint = document.getElementById('mac-hand-hint');
  const macCamLight = document.getElementById('mac-cam-light');
  const macBoot = document.getElementById('mac-boot');
  const macBootFill = document.getElementById('mac-boot-fill');
  const macSafariApp = document.getElementById('mac-safari-app');
  const macTypedUrl = document.getElementById('mac-typed-url');
  const macLoadingProgress = document.getElementById('mac-loading-progress');
  const macWebview = document.getElementById('mac-webview');
  const macSiteScroll = document.getElementById('mac-site-scroll');
  const macMouse = document.getElementById('mac-mouse-pointer');

  // iPhone elements
  const iphoneScreen = document.getElementById('iphone-screen');
  const iosBoot = document.getElementById('ios-boot');
  const iosBootFill = document.getElementById('ios-boot-fill');
  const iosDynamicIsland = document.getElementById('ios-dynamic-island');
  const islandIcon = document.getElementById('island-icon');
  const islandFilename = document.getElementById('island-filename');
  const islandStatus = document.getElementById('island-status');
  const islandProgressFill = document.getElementById('island-progress-fill');
  const iosTypedUrl = document.getElementById('ios-typed-url');
  const iosLoadingBar = document.getElementById('ios-loading-bar');
  const iosWebview = document.getElementById('ios-webview');
  const iosDownloadBtn = document.getElementById('ios-download-btn');
  const iosBtnTitle = document.getElementById('ios-btn-title');
  const iosBtnSub = document.getElementById('ios-btn-sub');
  const iosBtnProgress = document.getElementById('ios-btn-progress');
  const iosTouch = document.getElementById('ios-touch-pointer');
  const iosModal = document.getElementById('ios-download-modal');
  const iosModalConfirm = document.getElementById('ios-modal-confirm');

  if (!stage || !macLid || !iphoneScreen) return;

  const macTargetUrl = 'https://god4xe.onrender.com';
  const iosTargetUrl = 'god4xe.onrender.com';

  let currentCycleTimer = null;

  function runSimultaneousCycle() {
    clearTimeout(currentCycleTimer);

    // ==========================================
    // T = 0.0s: RESET BOTH DEVICES TOGETHER
    // ==========================================
    // MacBook Reset
    macLid.classList.remove('mac-lid-opened');
    macLid.classList.add('mac-lid-closed');
    if (macHandHint) macHandHint.classList.add('active');
    if (macCamLight) macCamLight.classList.remove('active');
    if (macBoot) {
      macBoot.classList.remove('fade-out');
      macBoot.classList.add('active');
    }
    if (macBootFill) {
      macBootFill.style.transition = 'none';
      macBootFill.style.width = '0%';
    }
    if (macSafariApp) macSafariApp.classList.remove('active');
    if (macTypedUrl) macTypedUrl.textContent = '';
    if (macLoadingProgress) {
      macLoadingProgress.style.transition = 'none';
      macLoadingProgress.style.width = '0%';
      macLoadingProgress.style.opacity = '1';
    }
    if (macWebview) macWebview.classList.remove('loaded');
    if (macSiteScroll) macSiteScroll.scrollTop = 0;
    if (macMouse) {
      macMouse.style.transition = 'none';
      macMouse.style.top = '70%';
      macMouse.style.left = '45%';
      macMouse.style.opacity = '0';
    }

    // iPhone Reset (Simultaneous)
    iphoneScreen.classList.remove('ios-awake');
    if (iosBoot) {
      iosBoot.classList.remove('fade-out');
      iosBoot.classList.add('active');
    }
    if (iosBootFill) {
      iosBootFill.style.transition = 'none';
      iosBootFill.style.width = '0%';
    }
    if (iosDynamicIsland) {
      iosDynamicIsland.classList.remove('expanded', 'completed');
    }
    if (islandProgressFill) islandProgressFill.style.width = '0%';
    if (iosTypedUrl) iosTypedUrl.textContent = '';
    if (iosLoadingBar) {
      iosLoadingBar.style.transition = 'none';
      iosLoadingBar.style.width = '0%';
      iosLoadingBar.style.opacity = '1';
    }
    if (iosWebview) {
      iosWebview.classList.remove('loaded');
      iosWebview.scrollTop = 0;
    }
    if (iosTouch) iosTouch.classList.remove('active', 'tapping');
    if (iosModal) iosModal.classList.remove('active');
    if (iosBtnProgress) {
      iosBtnProgress.style.transition = 'none';
      iosBtnProgress.style.width = '0%';
    }
    if (iosBtnTitle) iosBtnTitle.textContent = 'DOWNLOAD OB-52 VIP CONFIG';
    if (iosBtnSub) iosBtnSub.textContent = 'VERIFIED DIRECT MIRROR (2.4 MB)';

    // ==========================================
    // PHASE 1 (T = 0.8s): SIMULTANEOUS UNLATCH & BOOT
    // ==========================================
    setTimeout(() => {
      // MacBook Lid Opens in 3D
      macLid.classList.remove('mac-lid-closed');
      macLid.classList.add('mac-lid-opened');

      // Hand gesture fades out
      setTimeout(() => {
        if (macHandHint) macHandHint.classList.remove('active');
      }, 900);

      // BOTH Apple Boot Bars Fill at the EXACT SAME TIME!
      setTimeout(() => {
        if (macCamLight) macCamLight.classList.add('active');
        if (macBootFill) {
          macBootFill.style.transition = 'width 2.4s cubic-bezier(0.16, 1, 0.3, 1)';
          macBootFill.style.width = '100%';
        }
        if (iosBootFill) {
          iosBootFill.style.transition = 'width 2.4s cubic-bezier(0.16, 1, 0.3, 1)';
          iosBootFill.style.width = '100%';
        }

        // ==========================================
        // PHASE 2 (T = 4.2s): SIMULTANEOUS OS & SAFARI LAUNCH
        // ==========================================
        setTimeout(() => {
          // MacBook: Boot screen fades -> macOS wallpaper -> Safari opens
          if (macBoot) macBoot.classList.add('fade-out');
          if (macSafariApp) macSafariApp.classList.add('active');

          // iPhone: Boot screen fades -> iOS 18 wallpaper -> Safari active
          if (iosBoot) iosBoot.classList.add('fade-out');
          iphoneScreen.classList.add('ios-awake');

          // ==========================================
          // PHASE 3 (T = 5.8s): SIMULTANEOUS TYPING & SEARCH
          // ==========================================
          setTimeout(() => {
            // macOS cursor moves to Omnibar
            if (macMouse) {
              macMouse.style.opacity = '1';
              macMouse.style.transition = 'top 0.6s ease, left 0.6s ease';
              macMouse.style.top = '12px';
              macMouse.style.left = '42%';
            }

            // Both devices type URL in parallel!
            let charIndex = 0;
            const parallelTypingTimer = setInterval(() => {
              let hasMore = false;
              if (charIndex < macTargetUrl.length) {
                if (macTypedUrl) macTypedUrl.textContent += macTargetUrl[charIndex];
                hasMore = true;
              }
              if (charIndex < iosTargetUrl.length) {
                if (iosTypedUrl) iosTypedUrl.textContent += iosTargetUrl[charIndex];
                hasMore = true;
              }
              charIndex++;

              if (!hasMore) {
                clearInterval(parallelTypingTimer);

                // ==========================================
                // PHASE 4 (T = 9.2s): SIMULTANEOUS LOADING BARS SWEEP
                // ==========================================
                setTimeout(() => {
                  if (macLoadingProgress) {
                    macLoadingProgress.style.transition = 'width 0.9s cubic-bezier(0.16, 1, 0.3, 1)';
                    macLoadingProgress.style.width = '100%';
                  }
                  if (iosLoadingBar) {
                    iosLoadingBar.style.transition = 'width 0.9s cubic-bezier(0.16, 1, 0.3, 1)';
                    iosLoadingBar.style.width = '100%';
                  }

                  // ==========================================
                  // PHASE 5 (T = 10.4s): SIMULTANEOUS WEBSITE RENDER
                  // ==========================================
                  setTimeout(() => {
                    if (macLoadingProgress) macLoadingProgress.style.opacity = '0';
                    if (iosLoadingBar) iosLoadingBar.style.opacity = '0';

                    if (macWebview) macWebview.classList.add('loaded');
                    if (iosWebview) iosWebview.classList.add('loaded');

                    // ==========================================
                    // PHASE 6 (T = 11.8s): SIMULTANEOUS INTERACTION
                    // ==========================================
                    setTimeout(() => {
                      // MacBook: Cursor scrolls site
                      if (macSiteScroll) {
                        macSiteScroll.scrollTo({ top: 90, behavior: 'smooth' });
                      }
                      if (macMouse) {
                        macMouse.style.top = '150px';
                        macMouse.style.left = '58%';
                      }

                      // iPhone: Touch finger glides to download button & taps!
                      if (iosTouch) {
                        iosTouch.classList.add('active');
                        iosTouch.style.top = '185px';
                        iosTouch.style.left = '50%';
                      }

                      setTimeout(() => {
                        if (iosTouch) iosTouch.classList.add('tapping');

                        // iOS Download Modal Alert Pops Up
                        setTimeout(() => {
                          if (iosTouch) iosTouch.classList.remove('active', 'tapping');
                          if (iosModal) iosModal.classList.add('active');

                          // Touch pointer moves to "Download" in modal
                          setTimeout(() => {
                            if (iosTouch) {
                              iosTouch.classList.add('active');
                              iosTouch.style.top = '58%';
                              iosTouch.style.left = '68%';
                            }

                            // Tap "Download" button on modal
                            setTimeout(() => {
                              if (iosTouch) iosTouch.classList.add('tapping');
                              if (iosModalConfirm) iosModalConfirm.classList.add('pressed');

                              // Modal dismisses & Dynamic Island expands!
                              setTimeout(() => {
                                if (iosModal) iosModal.classList.remove('active');
                                if (iosTouch) iosTouch.classList.remove('active', 'tapping');

                                // Dynamic Island expands into active Live Activity download pill
                                if (iosDynamicIsland) {
                                  iosDynamicIsland.classList.add('expanded');
                                }
                                if (islandIcon) islandIcon.textContent = '⬇';
                                if (islandStatus) islandStatus.textContent = 'Downloading 2.4 MB...';
                                if (iosBtnTitle) iosBtnTitle.textContent = 'DOWNLOADING (2.4 MB)...';
                                if (iosBtnProgress) {
                                  iosBtnProgress.style.transition = 'width 2.8s ease-in-out';
                                  iosBtnProgress.style.width = '100%';
                                }
                                if (islandProgressFill) {
                                  islandProgressFill.style.transition = 'width 2.8s ease-in-out';
                                  islandProgressFill.style.width = '100%';
                                }

                                // Download complete celebration
                                setTimeout(() => {
                                  if (islandIcon) islandIcon.textContent = '✓';
                                  if (islandStatus) islandStatus.textContent = 'Download Complete!';
                                  if (iosBtnTitle) iosBtnTitle.textContent = '✓ DOWNLOAD COMPLETE';
                                  if (iosBtnSub) iosBtnSub.textContent = '100% BAN-SAFE VERIFIED';
                                  if (iosDynamicIsland) iosDynamicIsland.classList.add('completed');

                                  // Contract Dynamic Island back to sleek pill
                                  setTimeout(() => {
                                    if (iosDynamicIsland) {
                                      iosDynamicIsland.classList.remove('expanded');
                                    }
                                  }, 2200);

                                }, 3000);

                              }, 450);

                            }, 500);

                          }, 750);

                        }, 550);

                      }, 550);

                    }, 1400);

                  }, 1000);

                }, 300);

              }
            }, 80);

          }, 1200);

        }, 2600);

      }, 1200);

    }, 800);

    // Continuous smooth loop
    currentCycleTimer = setTimeout(() => {
      runSimultaneousCycle();
    }, 28000);
  }

  // Launch initial simultaneous cycle
  runSimultaneousCycle();

  // Desktop 3D Mouse Parallax
  const isTouch = window.matchMedia('(pointer: coarse)').matches || ('ontouchstart' in window);
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!isTouch && !prefersReduced && window.innerWidth > 1024) {
    stage.addEventListener('mousemove', (e) => {
      const rect = stage.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;

      const macDevice = document.getElementById('macbook-showcase');
      const iphoneWrap = document.getElementById('iphone-stage');
      if (macDevice && macLid.classList.contains('mac-lid-opened')) {
        macDevice.style.transform = `perspective(1200px) rotateY(${x * 8 - 4}deg) rotateX(${-y * 6 + 2}deg) translateY(-5px)`;
      }
      if (iphoneWrap) {
        iphoneWrap.style.transform = `perspective(1200px) rotateY(${x * 10 + 2}deg) rotateX(${-y * 6 + 2}deg) translateZ(15px)`;
      }
    });

    stage.addEventListener('mouseleave', () => {
      const macDevice = document.getElementById('macbook-showcase');
      const iphoneWrap = document.getElementById('iphone-stage');
      if (macDevice) macDevice.style.transform = '';
      if (iphoneWrap) iphoneWrap.style.transform = '';
    });
  }
}

/* --------------------------------------------------------------------------
   INTERACTIVE ARTICLE SLIDING DRAWER SYSTEM (SPLIT-VIEW DESKTOP & MOBILE SHEET)
   -------------------------------------------------------------------------- */
function initArticleSlideDrawer() {
  const drawer = document.getElementById('article-slide-drawer');
  const articlesWrapper = document.getElementById('articles-wrapper');
  const contentArea = document.getElementById('drawer-content-area');
  const closeBtn = document.getElementById('drawer-close-btn');
  const fullpageLink = document.getElementById('drawer-fullpage-link');
  const backdrop = document.getElementById('drawer-backdrop');

  if (!drawer || !contentArea) return;

  const postDrawerCache = {};
  let currentSlug = null;

  function closeArticleDrawer() {
    if (articlesWrapper) {
      articlesWrapper.classList.remove('drawer-active');
    }
    drawer.classList.remove('active');
    drawer.setAttribute('aria-hidden', 'true');
    if (backdrop) {
      backdrop.classList.remove('active');
      backdrop.setAttribute('aria-hidden', 'true');
    }
    document.querySelectorAll('.post-card.drawer-active-card').forEach(c => {
      c.classList.remove('drawer-active-card');
    });
    document.body.classList.remove('drawer-open-lock');
    currentSlug = null;
  }

  function openArticleDrawer(slug) {
    if (!slug) return;
    currentSlug = slug;

    // Highlight active card in grid
    document.querySelectorAll('.post-card').forEach(c => c.classList.remove('drawer-active-card'));
    const targetCard = document.querySelector(`[data-slug="${slug}"]`) || document.getElementById(`post-card-${slug}`) || document.getElementById(`pop-card-${slug}`);
    if (targetCard) {
      targetCard.classList.add('drawer-active-card');
    }

    if (fullpageLink) {
      fullpageLink.href = `/post/${encodeURIComponent(slug)}`;
    }

    if (articlesWrapper) {
      articlesWrapper.classList.add('drawer-active');
    }
    drawer.classList.add('active');
    drawer.setAttribute('aria-hidden', 'false');

    if (window.innerWidth <= 1024 && backdrop) {
      backdrop.classList.add('active');
      backdrop.setAttribute('aria-hidden', 'false');
      document.body.classList.add('drawer-open-lock');
    }

    // Scroll drawer top into view smoothly
    contentArea.scrollTop = 0;

    if (postDrawerCache[slug]) {
      renderDrawerContent(postDrawerCache[slug]);
    } else {
      contentArea.innerHTML = `
        <div class="drawer-loading-box">
          <div class="drawer-spinner"></div>
          <div class="drawer-loading-title">INITIALIZING DATA TOPOLOGY...</div>
          <p class="drawer-loading-sub">Fetching tournament configs, guide breakdown, and download mirrors.</p>
        </div>
      `;

      fetch(`/api/post-drawer/${encodeURIComponent(slug)}`)
        .then(res => {
          if (!res.ok) throw new Error('Network response not ok');
          return res.json();
        })
        .then(data => {
          postDrawerCache[slug] = data;
          if (currentSlug === slug) {
            renderDrawerContent(data);
          }
        })
        .catch(err => {
          contentArea.innerHTML = `
            <div class="drawer-error-box">
              <span style="font-size: 2.5rem;">⚠️</span>
              <h3>Failed to load guide</h3>
              <p>Could not load the interactive article. You can view the full guide directly.</p>
              <a href="/post/${encodeURIComponent(slug)}" class="btn btn-primary btn-sm">Open Full Page &rarr;</a>
            </div>
          `;
        });
    }
  }

  function renderDrawerContent(data) {
    const extLinksHtml = (data.custom_links && data.custom_links.length > 0) ? `
      <div class="drawer-ext-links-strip">
        <div class="ext-links-box-header">
          <span class="pulse-dot"></span>
          <span class="ext-links-box-title">RECOMMENDED OFFICIAL CHANNELS &amp; SERVERS</span>
        </div>
        <div class="post-card-ext-links">
          ${data.custom_links.map(l => `
            <a href="${escapeHtml(l.url)}" target="_blank" rel="noopener noreferrer" class="post-ext-chip">
              <span class="ext-chip-dot"></span>
              <span class="ext-chip-text">${escapeHtml(l.title)}</span>
              <svg class="ext-chip-arrow" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M7 17L17 7M17 7H7M17 7V17"/></svg>
            </a>
          `).join('')}
        </div>
      </div>
    ` : '';

    const downloadBoxHtml = data.download_url ? `
      <div class="download-card-container epic-download-box cyber-card" style="margin: 2rem 0;">
        <div class="download-card-glow" aria-hidden="true"></div>
        <div class="download-card-grid" aria-hidden="true"></div>
        <div class="epic-download-header">
          <span class="badge badge-cyan download-live-badge">
            <span class="pulse-dot"></span> VERIFIED MIRROR ACTIVE
          </span>
          <span class="download-meta-views">🔒 BAN-SAFE VERIFIED</span>
        </div>
        <h3 class="download-title">${escapeHtml(data.download_label || 'OFFICIAL CONFIG / FILE DOWNLOAD')}</h3>
        <p class="download-desc">Verified ban-safe configuration file. Click below to open secure server.</p>
        <div class="download-button-wrapper">
          <a href="${escapeHtml(data.download_url)}" target="_blank" rel="noopener noreferrer" class="btn-cyber-download-epic" data-track-download="1" data-post-id="${data.id}">
            <span class="btn-shimmer-sweep" aria-hidden="true"></span>
            <span class="btn-neon-aura" aria-hidden="true"></span>
            <span class="btn-download-icon-box">
              <svg class="download-arrow-svg" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
              </svg>
              <span class="radar-ping" aria-hidden="true"></span>
            </span>
            <span class="btn-download-text-group">
              <span class="btn-download-main-text">${escapeHtml(data.download_label || 'DOWNLOAD FILE NOW')}</span>
              <span class="btn-download-sub-text">⚡ DIRECT SECURE MIRROR • FAST CLOUD DELIVERY</span>
            </span>
            <svg class="btn-external-arrow" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3"/>
            </svg>
          </a>
        </div>
        <div class="download-trust-row">
          <div class="trust-item"><span>🛡️</span> Safe Link Protection</div>
          <div class="trust-item"><span>⚡</span> High Speed Cloud</div>
          <div class="trust-item"><span>✅</span> Anti-Cheat Passed</div>
        </div>
      </div>
    ` : '';

    const videoHtml = data.youtube_video_id ? `
      <div class="post-video-section" style="margin: 2rem 0 1rem;">
        <h3 class="post-video-heading" style="font-size: 0.95rem; margin-bottom: 0.75rem;">
          <svg width="20" height="20" fill="#ff0033" viewBox="0 0 24 24"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>
          <span>VIDEO SHOWCASE &amp; TUTORIAL</span>
        </h3>
        <div class="featured-video-card cyber-card" style="aspect-ratio: 16/9; overflow: hidden; border-radius: 8px;">
          <iframe 
            src="https://www.youtube-nocookie.com/embed/${escapeHtml(data.youtube_video_id)}" 
            title="${escapeHtml(data.title)}" 
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
            allowfullscreen 
            style="width: 100%; height: 100%; border: none;">
          </iframe>
        </div>
      </div>
    ` : '';

    const relatedHtml = (data.related && data.related.length > 0) ? `
      <div class="drawer-related-section" style="margin-top: 2.5rem; padding-top: 1.5rem; border-top: 1px solid rgba(255,255,255,0.08);">
        <h4 style="font-family: var(--font-display); font-size: 0.95rem; font-weight: 800; color: #fff; margin-bottom: 1rem; letter-spacing: 0.5px;">
          <span style="color: var(--neon-cyan);">//</span> RELATED GUIDES IN ARCHIVE
        </h4>
        <div style="display: flex; flex-direction: column; gap: 0.75rem;">
          ${data.related.map(r => `
            <div class="drawer-related-item cyber-card post-drawer-trigger" data-post-slug="${escapeHtml(r.slug)}" style="display: flex; align-items: center; gap: 0.85rem; padding: 0.65rem 0.85rem; cursor: pointer; border-radius: 8px;">
              <span style="font-size: 1.2rem;">🎯</span>
              <div style="flex: 1; min-width: 0;">
                <div style="font-family: var(--font-display); font-size: 0.85rem; font-weight: 700; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(r.title)}</div>
                <div style="font-size: 0.7rem; color: var(--neon-cyan); letter-spacing: 0.5px;">SWITCH GUIDE &rarr;</div>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    ` : '';

    contentArea.innerHTML = `
      <div class="drawer-article-view">
        ${data.thumbnail_url ? `
        <div class="drawer-hero-banner">
          <img src="${escapeHtml(data.thumbnail_url)}" alt="${escapeHtml(data.title)}" class="drawer-banner-img">
          <div class="drawer-hero-overlay"></div>
          ${data.section_name ? `<span class="post-badge">${escapeHtml(data.section_name)}</span>` : ''}
        </div>
        ` : ''}

        <div class="drawer-meta-bar">
          <span>📅 ${escapeHtml(data.published_at)}</span>
          <span class="meta-dot">•</span>
          <span>👁️ ${escapeHtml(data.view_count)} views</span>
          ${data.download_count ? `<span class="meta-dot">•</span><span>📥 ${escapeHtml(data.download_count)} DLs</span>` : ''}
        </div>

        <h2 class="drawer-title">${escapeHtml(data.title)}</h2>

        ${extLinksHtml}

        <div class="drawer-body-text article-body-content">
          ${data.formatted_content}
        </div>

        ${downloadBoxHtml}

        ${videoHtml}

        ${relatedHtml}
      </div>
    `;

    // Re-attach triggers inside drawer for related posts
    contentArea.querySelectorAll('.post-drawer-trigger').forEach(trigger => {
      trigger.addEventListener('click', (e) => {
        e.preventDefault();
        const nextSlug = trigger.getAttribute('data-post-slug');
        if (nextSlug) openArticleDrawer(nextSlug);
      });
    });
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Delegated click on all post drawer triggers
  document.addEventListener('click', (e) => {
    const trigger = e.target.closest('.post-drawer-trigger');
    if (trigger) {
      e.preventDefault();
      const slug = trigger.getAttribute('data-post-slug');
      if (slug) {
        openArticleDrawer(slug);
      }
    }
  });

  if (closeBtn) {
    closeBtn.addEventListener('click', (e) => {
      e.preventDefault();
      closeArticleDrawer();
    });
  }

  if (backdrop) {
    backdrop.addEventListener('click', (e) => {
      e.preventDefault();
      closeArticleDrawer();
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && drawer.classList.contains('active')) {
      closeArticleDrawer();
    }
  });
}

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
  initPostQuickPreview();
  initAnalyticsTracking();
  initDeviceShowcaseParallax();
  initDimensionalWebGL();
  initDimensionalUI();
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
   CARD MOTION & SPECULAR REACTION
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

      if (!isTouch && !prefersReduced && window.innerWidth > 1024 && !card.classList.contains('no-tilt') && !card.closest('.quick-preview-hud')) {
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        const rotateX = ((y - centerY) / centerY) * -4;
        const rotateY = ((x - centerX) / centerX) * 4;
        
        card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-5px)`;
      }
    }, { passive: true });

    card.addEventListener('mouseleave', () => {
      if (!isTouch && !prefersReduced && !card.classList.contains('no-tilt')) {
        card.style.transform = '';
      }
    });
  });
}

/* --------------------------------------------------------------------------
   POST CARD HOVER POP & QUICK PREVIEW HUD SYSTEM
   Bulletproof close handlers on tap, click, outside backdrop, and ESC
   -------------------------------------------------------------------------- */
function initPostQuickPreview() {
  const popover = document.getElementById('quick-preview-popover');
  const backdrop = document.getElementById('quick-preview-backdrop');
  if (!popover) return;

  const hudImg = document.getElementById('hud-preview-img');
  const hudBadge = document.getElementById('hud-preview-badge');
  const hudDate = document.getElementById('hud-preview-date');
  const hudViews = document.getElementById('hud-preview-views');
  const hudTitle = document.getElementById('hud-preview-title');
  const hudExcerpt = document.getElementById('hud-preview-excerpt');
  const hudLink = document.getElementById('hud-preview-link');
  const hudDl = document.getElementById('hud-preview-dl');
  const hudClose = document.getElementById('preview-hud-close-btn') || popover.querySelector('.preview-hud-close');

  const cards = document.querySelectorAll('[data-post-preview]');
  let hoverTimer = null;

  function closePreview() {
    clearTimeout(hoverTimer);
    popover.classList.remove('active');
    popover.setAttribute('aria-hidden', 'true');
    if (backdrop) backdrop.classList.remove('active');
    document.body.classList.remove('preview-hud-open');
  }

  function showPreview(card) {
    const title = card.getAttribute('data-preview-title') || '';
    const excerpt = card.getAttribute('data-preview-excerpt') || '';
    const url = card.getAttribute('data-preview-url') || '#';
    const date = card.getAttribute('data-preview-date') || '';
    const views = card.getAttribute('data-preview-views') || '0';
    const badge = card.getAttribute('data-preview-badge') || 'GUIDE';
    const img = card.getAttribute('data-preview-image') || '';
    const dl = card.getAttribute('data-preview-download') || '';

    if (hudTitle) hudTitle.textContent = title;
    if (hudExcerpt) hudExcerpt.textContent = excerpt;
    if (hudDate) hudDate.textContent = `📅 ${date}`;
    if (hudViews) hudViews.textContent = `👁️ ${views} views`;
    if (hudBadge) hudBadge.textContent = badge;
    if (hudLink) hudLink.href = url;

    const mediaBox = document.getElementById('hud-preview-media-box');
    if (hudImg && mediaBox) {
      if (img) {
        hudImg.src = img;
        mediaBox.style.display = 'block';
      } else {
        mediaBox.style.display = 'none';
      }
    }

    if (hudDl) {
      if (dl) {
        hudDl.href = dl;
        hudDl.style.display = 'inline-flex';
      } else {
        hudDl.style.display = 'none';
      }
    }

    popover.classList.add('active');
    popover.setAttribute('aria-hidden', 'false');
    if (backdrop) backdrop.classList.add('active');
    document.body.classList.add('preview-hud-open');
  }

  if (hudClose) {
    const handleClose = (e) => {
      e.preventDefault();
      e.stopPropagation();
      closePreview();
    };
    hudClose.addEventListener('click', handleClose);
    hudClose.addEventListener('touchend', handleClose, { passive: false });
  }

  if (backdrop) {
    backdrop.addEventListener('click', (e) => {
      e.preventDefault();
      closePreview();
    });
    backdrop.addEventListener('touchend', (e) => {
      e.preventDefault();
      closePreview();
    }, { passive: false });
  }

  cards.forEach(card => {
    card.addEventListener('mouseenter', () => {
      if (window.innerWidth > 1024) {
        clearTimeout(hoverTimer);
        hoverTimer = setTimeout(() => {
          showPreview(card);
        }, 320);
      }
    });

    card.addEventListener('mouseleave', () => {
      clearTimeout(hoverTimer);
    });

    const peekBtn = card.querySelector('.card-quick-peek-btn');
    if (peekBtn) {
      const handlePeek = (e) => {
        e.preventDefault();
        e.stopPropagation();
        showPreview(card);
      };
      peekBtn.addEventListener('click', handlePeek);
      peekBtn.addEventListener('touchend', handlePeek, { passive: false });
    }
  });

  document.addEventListener('click', (e) => {
    if (popover.classList.contains('active')) {
      const inner = popover.querySelector('.preview-hud-inner');
      if (inner && !inner.contains(e.target) && !e.target.closest('.card-quick-peek-btn')) {
        closePreview();
      }
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && popover.classList.contains('active')) {
      closePreview();
    }
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
   3D DUAL DEVICE SHOWCASE PARALLAX INTERACTION (DESKTOP ONLY)
   -------------------------------------------------------------------------- */
function initDeviceShowcaseParallax() {
  const stage = document.getElementById('hero-devices-stage');
  if (!stage) return;

  const isTouch = window.matchMedia('(pointer: coarse)').matches || ('ontouchstart' in window);
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (isTouch || prefersReduced || window.innerWidth <= 1024) return;

  const macbook = stage.querySelector('.macbook-device');
  const iphone = stage.querySelector('.iphone-device');
  if (!macbook || !iphone) return;

  stage.addEventListener('mousemove', (e) => {
    const rect = stage.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;

    macbook.style.transform = `rotateY(${x * 12 - 6}deg) rotateX(${-y * 10 + 5}deg) translateY(-6px)`;
    iphone.style.transform = `rotateY(${x * 16 - 15}deg) rotateX(${-y * 14 + 7}deg) translateZ(35px) translateY(-10px)`;
  });

  stage.addEventListener('mouseleave', () => {
    macbook.style.transform = '';
    iphone.style.transform = '';
  });
}

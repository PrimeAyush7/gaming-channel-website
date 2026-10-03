/**
 * GOD4XE GAMING - Core Interactive & Motion Script
 * - Smooth Dual-Core Desktop Cursor Glow (Cyan + Violet Glow)
 * - Mobile Navigation Drawer (Sleek Glassmorphic Sheet)
 * - 3D Card Tilt & Dynamic Specular Lighting Reaction
 * - Device Showcase 3D Parallax Tilt
 * - First-party Download & YouTube Click Analytics
 */

document.addEventListener('DOMContentLoaded', () => {
  initCursorGlow();
  initMobileNav();
  initCardMotionAndLighting();
  initAnalyticsTracking();
  initDeviceShowcaseParallax();
});

/* --------------------------------------------------------------------------
   CURSOR LIGHTING (DESKTOP)
   Dual-tone Cyber Neon Ambiance (Electric Cyan + Cyber Violet)
   -------------------------------------------------------------------------- */
function initCursorGlow() {
  const isTouch = window.matchMedia('(pointer: coarse)').matches;
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  
  if (isTouch || prefersReducedMotion) {
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
  let isMoving = false;
  let fadeTimeout = null;

  document.addEventListener('mousemove', (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;
    glowEl.style.opacity = '1';
    isMoving = true;
    clearTimeout(fadeTimeout);
    fadeTimeout = setTimeout(() => {
      isMoving = false;
    }, 2500);
  }, { passive: true });

  document.addEventListener('mouseleave', () => {
    glowEl.style.opacity = '0';
  });

  function animateCursor() {
    // Ultra smooth lerp interpolation
    currentX += (mouseX - currentX) * 0.16;
    currentY += (mouseY - currentY) * 0.16;
    
    glowEl.style.left = `${currentX}px`;
    glowEl.style.top = `${currentY}px`;
    
    requestAnimationFrame(animateCursor);
  }
  requestAnimationFrame(animateCursor);
}

/* --------------------------------------------------------------------------
   CARD MOTION & LIGHTING REACTION
   3D Micro-Tilt & Dynamic Specular Highlight
   -------------------------------------------------------------------------- */
function initCardMotionAndLighting() {
  const cards = document.querySelectorAll('.cyber-card');
  if (!cards.length) return;

  const isTouch = window.matchMedia('(pointer: coarse)').matches;
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  cards.forEach(card => {
    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      
      card.style.setProperty('--card-mouse-x', `${x}px`);
      card.style.setProperty('--card-mouse-y', `${y}px`);

      if (!isTouch && !prefersReduced && !card.classList.contains('no-tilt')) {
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        const rotateX = ((y - centerY) / centerY) * -5;
        const rotateY = ((x - centerX) / centerX) * 5;
        
        card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-4px)`;
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
   MOBILE NAVIGATION DRAWER
   Smooth Backdrop, Close Button, Outside Click, & Keyboard Escape
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

  // Close on outside click
  document.addEventListener('click', (e) => {
    if (drawer.classList.contains('open') && !drawer.contains(e.target) && e.target !== toggleBtn) {
      closeDrawer();
    }
  });

  // Close on Escape key
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
  // Download button click tracker
  const downloadBtns = document.querySelectorAll('[data-track-download]');
  downloadBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const postId = btn.getAttribute('data-post-id');
      if (postId) {
        try {
          navigator.sendBeacon(`/api/track/download/${postId}`, new FormData());
        } catch (err) {
          // Non-blocking fallback
        }
      }
    });
  });

  // YouTube action tracking
  const ytTriggers = document.querySelectorAll('[data-track-youtube]');
  ytTriggers.forEach(trigger => {
    trigger.addEventListener('click', () => {
      const postId = trigger.getAttribute('data-post-id') || 0;
      try {
        navigator.sendBeacon(`/api/track/youtube/${postId}`, new FormData());
      } catch (err) {
        // Non-blocking fallback
      }
    });
  });
}

/* --------------------------------------------------------------------------
   3D DUAL DEVICE SHOWCASE PARALLAX INTERACTION
   -------------------------------------------------------------------------- */
function initDeviceShowcaseParallax() {
  const stage = document.getElementById('hero-devices-stage');
  if (!stage) return;

  const isTouch = window.matchMedia('(pointer: coarse)').matches;
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (isTouch || prefersReduced) return;

  const macbook = stage.querySelector('.macbook-device');
  const iphone = stage.querySelector('.iphone-device');
  if (!macbook || !iphone) return;

  stage.addEventListener('mousemove', (e) => {
    const rect = stage.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;

    // Smooth interactive tilt
    macbook.style.transform = `rotateY(${x * 14 - 6}deg) rotateX(${-y * 12 + 5}deg) translateY(-8px)`;
    iphone.style.transform = `rotateY(${x * 18 - 15}deg) rotateX(${-y * 16 + 7}deg) translateZ(46px) translateY(-12px)`;
  });

  stage.addEventListener('mouseleave', () => {
    macbook.style.transform = '';
    iphone.style.transform = '';
  });
}

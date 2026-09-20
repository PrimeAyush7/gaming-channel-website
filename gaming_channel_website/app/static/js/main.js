/**
 * NEXUS GAMING - Core Interactive Script
 * - Smooth Desktop Cursor Glow
 * - Mobile Navigation Drawer
 * - Card Lighting Interaction
 * - First-party Download & YouTube Click Analytics
 */

document.addEventListener('DOMContentLoaded', () => {
  initCursorGlow();
  initMobileNav();
  initCardLighting();
  initAnalyticsTracking();
});

/* --------------------------------------------------------------------------
   CURSOR LIGHTING (DESKTOP)
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

  document.addEventListener('mousemove', (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;
    glowEl.style.opacity = '1';
  }, { passive: true });

  document.addEventListener('mouseleave', () => {
    glowEl.style.opacity = '0';
  });

  function animateCursor() {
    // Smooth interpolation (lerp)
    currentX += (mouseX - currentX) * 0.15;
    currentY += (mouseY - currentY) * 0.15;
    
    glowEl.style.left = `${currentX}px`;
    glowEl.style.top = `${currentY}px`;
    
    requestAnimationFrame(animateCursor);
  }
  requestAnimationFrame(animateCursor);
}

/* --------------------------------------------------------------------------
   CARD LIGHTING REACTION
   -------------------------------------------------------------------------- */
function initCardLighting() {
  const cards = document.querySelectorAll('.cyber-card');
  if (!cards.length) return;

  cards.forEach(card => {
    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      card.style.setProperty('--card-mouse-x', `${x}px`);
      card.style.setProperty('--card-mouse-y', `${y}px`);
    }, { passive: true });
  });
}

/* --------------------------------------------------------------------------
   MOBILE NAVIGATION DRAWER
   -------------------------------------------------------------------------- */
function initMobileNav() {
  const toggleBtn = document.getElementById('mobile-nav-toggle');
  const drawer = document.getElementById('mobile-drawer');

  if (!toggleBtn || !drawer) return;

  toggleBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    const isOpen = drawer.classList.contains('open');
    if (isOpen) {
      drawer.classList.remove('open');
      toggleBtn.setAttribute('aria-expanded', 'false');
    } else {
      drawer.classList.add('open');
      toggleBtn.setAttribute('aria-expanded', 'true');
    }
  });

  // Close on outside click
  document.addEventListener('click', (e) => {
    if (drawer.classList.contains('open') && !drawer.contains(e.target) && e.target !== toggleBtn) {
      drawer.classList.remove('open');
      toggleBtn.setAttribute('aria-expanded', 'false');
    }
  });

  // Close on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && drawer.classList.contains('open')) {
      drawer.classList.remove('open');
      toggleBtn.setAttribute('aria-expanded', 'false');
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
        navigator.sendBeacon(`/api/track/download/${postId}`, new FormData());
      }
    });
  });

  // YouTube action tracking
  const ytTriggers = document.querySelectorAll('[data-track-youtube]');
  ytTriggers.forEach(trigger => {
    trigger.addEventListener('click', () => {
      const postId = trigger.getAttribute('data-post-id') || 0;
      navigator.sendBeacon(`/api/track/youtube/${postId}`, new FormData());
    });
  });
}

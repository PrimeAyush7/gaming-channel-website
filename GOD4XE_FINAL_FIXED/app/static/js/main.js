/**
 * GOD4XE GAMING - Core Interactive Script
 * - Smooth Desktop Cursor Glow
 * - Mobile Navigation Drawer & Backdrop
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
   MOBILE NAVIGATION DRAWER & BACKDROP
   -------------------------------------------------------------------------- */
function initMobileNav() {
  const toggleBtn = document.getElementById('mobile-nav-toggle');
  const closeBtn = document.getElementById('mobile-drawer-close');
  const drawer = document.getElementById('mobile-drawer');
  const backdrop = document.getElementById('mobile-drawer-backdrop');
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
    if (backdrop) backdrop.classList.add('open');
    toggleBtn.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
  }

  function closeDrawer() {
    drawer.classList.remove('open');
    if (backdrop) backdrop.classList.remove('open');
    toggleBtn.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
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

  if (backdrop) {
    backdrop.addEventListener('click', () => {
      closeDrawer();
    });
  }

  // Close when clicking nav links inside drawer
  drawer.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
      closeDrawer();
    });
  });

  window.addEventListener('resize', () => {
    if (drawer.classList.contains('open')) {
      updateDrawerPosition();
    }
  }, { passive: true });

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
  const downloadBtns = document.querySelectorAll('[data-track-download]');
  downloadBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const postId = btn.getAttribute('data-post-id');
      if (postId) {
        navigator.sendBeacon(`/api/track/download/${postId}`, new FormData());
      }
    });
  });

  const ytTriggers = document.querySelectorAll('[data-track-youtube]');
  ytTriggers.forEach(trigger => {
    trigger.addEventListener('click', () => {
      const postId = trigger.getAttribute('data-post-id') || 0;
      navigator.sendBeacon(`/api/track/youtube/${postId}`, new FormData());
    });
  });
}

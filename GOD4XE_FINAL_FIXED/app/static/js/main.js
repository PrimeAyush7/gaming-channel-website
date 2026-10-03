/**
 * GOD4XE GAMING - Master Script (v3.3.0 Mobile Shield & Instant Modal Close)
 * - Strict Mobile & Touch Safe Event Handlers
 * - Bulletproof HUD Popover Close on Tap, Click, Outside Touch & ESC
 * - Zero Layout Shift Motion Controls
 * - 3D Card Hover & Desktop Parallax
 */

document.addEventListener('DOMContentLoaded', () => {
  initCursorGlow();
  initMobileNav();
  initCardMotionAndLighting();
  initPostQuickPreview();
  initAnalyticsTracking();
  initDeviceShowcaseParallax();
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

  // Unconditional close function
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

  // Bind close button: instant response on click, mousedown, or touchend
  if (hudClose) {
    const handleClose = (e) => {
      e.preventDefault();
      e.stopPropagation();
      closePreview();
    };
    hudClose.addEventListener('click', handleClose);
    hudClose.addEventListener('touchend', handleClose, { passive: false });
  }

  // Backdrop click/tap closes preview
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

  // Card interactions
  cards.forEach(card => {
    // Desktop hover trigger with debounce
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

    // Quick Peek button (works on Mobile and Desktop)
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

  // Close when tapping outside the modal window
  document.addEventListener('click', (e) => {
    if (popover.classList.contains('active')) {
      const inner = popover.querySelector('.preview-hud-inner');
      if (inner && !inner.contains(e.target) && !e.target.closest('.card-quick-peek-btn')) {
        closePreview();
      }
    }
  });

  // Close on Escape key
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

/**
 * GOD4XE GAMING - Core Interactive & Motion Script (v3.2.0)
 * - Smooth Dual-Core Desktop Cursor Glow (Cyan + Violet Glow)
 * - Mobile Navigation Drawer (Sleek Glassmorphic Sheet)
 * - 3D Card Tilt, Pop & Dynamic Specular Lighting Reaction
 * - Hover Post Popover / Quick Preview HUD Modal
 * - Device Showcase 3D Parallax Tilt
 * - First-party Download & YouTube Click Analytics
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
        
        card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-6px) scale(1.015)`;
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
   -------------------------------------------------------------------------- */
function initPostQuickPreview() {
  const popover = document.getElementById('quick-preview-popover');
  if (!popover) return;

  const hudImg = document.getElementById('hud-preview-img');
  const hudBadge = document.getElementById('hud-preview-badge');
  const hudDate = document.getElementById('hud-preview-date');
  const hudViews = document.getElementById('hud-preview-views');
  const hudTitle = document.getElementById('hud-preview-title');
  const hudExcerpt = document.getElementById('hud-preview-excerpt');
  const hudLink = document.getElementById('hud-preview-link');
  const hudDl = document.getElementById('hud-preview-dl');
  const hudClose = popover.querySelector('.preview-hud-close');

  const cards = document.querySelectorAll('[data-post-preview]');
  let hoverTimer = null;
  let isMouseOverPopover = false;

  popover.addEventListener('mouseenter', () => {
    isMouseOverPopover = true;
  });
  popover.addEventListener('mouseleave', () => {
    isMouseOverPopover = false;
    hidePreview();
  });

  if (hudClose) {
    hudClose.addEventListener('click', (e) => {
      e.stopPropagation();
      hidePreview();
    });
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

    if (hudImg) {
      if (img) {
        hudImg.src = img;
        hudImg.parentElement.style.display = 'block';
      } else {
        hudImg.parentElement.style.display = 'none';
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

    // Positioning: Responsive calculation
    const isMobile = window.innerWidth <= 768;
    if (isMobile) {
      popover.style.position = 'fixed';
      popover.style.top = '50%';
      popover.style.left = '50%';
      popover.style.transform = 'translate(-50%, -50%)';
    } else {
      popover.style.position = 'absolute';
      const rect = card.getBoundingClientRect();
      let top = rect.top + window.scrollY - 15;
      let left = rect.right + 20;

      // Ensure no viewport overflow on right
      if (left + 390 > window.innerWidth) {
        left = rect.left - 410;
        if (left < 15) {
          left = Math.max(15, (window.innerWidth - 380) / 2);
          top = Math.max(80, rect.bottom + window.scrollY + 15);
        }
      }

      popover.style.top = `${top}px`;
      popover.style.left = `${left}px`;
      popover.style.transform = 'none';
    }

    popover.classList.add('active');
    popover.setAttribute('aria-hidden', 'false');
  }

  function hidePreview() {
    clearTimeout(hoverTimer);
    if (!isMouseOverPopover) {
      popover.classList.remove('active');
      popover.setAttribute('aria-hidden', 'true');
    }
  }

  cards.forEach(card => {
    // Desktop hover trigger
    card.addEventListener('mouseenter', () => {
      if (window.innerWidth > 768) {
        clearTimeout(hoverTimer);
        hoverTimer = setTimeout(() => {
          showPreview(card);
        }, 250);
      }
    });

    card.addEventListener('mouseleave', () => {
      clearTimeout(hoverTimer);
      setTimeout(() => {
        if (!isMouseOverPopover) {
          hidePreview();
        }
      }, 150);
    });

    // Mobile / Quick Peek Button Click
    const peekBtn = card.querySelector('.card-quick-peek-btn');
    if (peekBtn) {
      peekBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        showPreview(card);
      });
    }
  });

  // Close on outside click
  document.addEventListener('click', (e) => {
    if (popover.classList.contains('active') && !popover.contains(e.target) && !e.target.closest('[data-post-preview]')) {
      hidePreview();
    }
  });

  // Close on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && popover.classList.contains('active')) {
      hidePreview();
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

    macbook.style.transform = `rotateY(${x * 14 - 6}deg) rotateX(${-y * 12 + 5}deg) translateY(-8px)`;
    iphone.style.transform = `rotateY(${x * 18 - 15}deg) rotateX(${-y * 16 + 7}deg) translateZ(46px) translateY(-12px)`;
  });

  stage.addEventListener('mouseleave', () => {
    macbook.style.transform = '';
    iphone.style.transform = '';
  });
}

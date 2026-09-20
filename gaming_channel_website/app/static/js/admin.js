/**
 * NEXUS GAMING - Admin Dashboard Helper Scripts
 */

document.addEventListener('DOMContentLoaded', () => {
  initSlugAutofill();
  initClipboardButtons();
  initConfirmDeletes();
  initEditorShortcuts();
});

function initSlugAutofill() {
  const titleInput = document.getElementById('title');
  const slugInput = document.getElementById('slug');
  if (titleInput && slugInput) {
    titleInput.addEventListener('blur', () => {
      if (!slugInput.value.trim()) {
        slugInput.value = titleInput.value
          .toLowerCase()
          .trim()
          .replace(/[^\w\s-]/g, '')
          .replace(/[\s_-]+/g, '-')
          .replace(/^-+|-+$/g, '');
      }
    });
  }
}

function initClipboardButtons() {
  document.querySelectorAll('[data-copy]').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      const text = btn.getAttribute('data-copy');
      if (!text) return;
      try {
        await navigator.clipboard.writeText(text);
        const originalText = btn.textContent;
        btn.textContent = 'Copied!';
        btn.classList.add('badge-success');
        setTimeout(() => {
          btn.textContent = originalText;
          btn.classList.remove('badge-success');
        }, 2000);
      } catch (err) {
        prompt('Copy URL manually:', text);
      }
    });
  });
}

function initConfirmDeletes() {
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', (e) => {
      const msg = el.getAttribute('data-confirm') || 'Are you sure you want to delete this?';
      if (!confirm(msg)) {
        e.preventDefault();
      }
    });
  });
}

function initEditorShortcuts() {
  const textarea = document.getElementById('content-editor');
  if (!textarea) return;

  function insertFormat(prefix, suffix = '') {
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const text = textarea.value;
    const selected = text.substring(start, end);
    const replacement = prefix + (selected || 'text') + suffix;
    textarea.value = text.substring(0, start) + replacement + text.substring(end);
    textarea.focus();
    textarea.selectionStart = start + prefix.length;
    textarea.selectionEnd = start + replacement.length - suffix.length;
  }

  document.querySelectorAll('[data-editor-cmd]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const cmd = btn.getAttribute('data-editor-cmd');
      if (cmd === 'h2') insertFormat('\n\n## ', '\n');
      else if (cmd === 'h3') insertFormat('\n\n### ', '\n');
      else if (cmd === 'bold') insertFormat('**', '**');
      else if (cmd === 'italic') insertFormat('*', '*');
      else if (cmd === 'quote') insertFormat('\n> ', '\n');
      else if (cmd === 'code') insertFormat('`', '`');
      else if (cmd === 'link') insertFormat('[', '](https://)');
    });
  });
}

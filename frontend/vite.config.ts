import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Inject diagnostics before the entry module only while Vite is serving the
// development app. The script is deliberately self-contained so it can report
// failures that happen before React (or any imported module) starts.
const startupDiagnosticsPlugin = () => ({
  name: 'kisan-hita-startup-diagnostics',
  transformIndexHtml: {
    order: 'pre' as const,
    handler(html: string, context: { server?: unknown }) {
      if (!context.server) return html;

      const diagnosticScript = `<script>
        (() => {
          const startedAt = new Date().toISOString();
          const events = [];
          let mounted = false;
          let overlay;
          const entryModule = { src: null, observed: false, loaded: false, failed: false };
          const seenScripts = new WeakSet();
          const safe = (value) => {
            try { return typeof value === 'string' ? value : JSON.stringify(value); }
            catch { return String(value); }
          };
          const escapeHtml = (value) => String(value).replace(/[&<>\"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '\"': '&quot;', "'": '&#39;' })[character]);
          const cleanUrl = (value) => {
            try { const url = new URL(value, location.href); return url.origin + url.pathname; }
            catch { return String(value).split('?')[0]; }
          };
          const moduleResources = () => performance.getEntriesByType('resource')
            .filter((entry) => entry.initiatorType === 'script' || /\\/src\\/|\\/@vite\\/|\\.m?js$/i.test(entry.name))
            .slice(-40)
            .map((entry) => ({
              url: cleanUrl(entry.name),
              initiator: entry.initiatorType,
              durationMs: Math.round(entry.duration),
              responseEndMs: Math.round(entry.responseEnd),
              transferSize: entry.transferSize,
              responseStatus: entry.responseStatus || null
            }));
          const details = () => ({
            page: location.origin + location.pathname,
            startedAt,
            userAgent: navigator.userAgent,
            viewport: innerWidth + 'x' + innerHeight,
            screen: screen.width + 'x' + screen.height,
            readyState: document.readyState,
            entryModule: {
              ...entryModule,
              src: entryModule.src ? cleanUrl(entryModule.src) : null,
              state: entryModule.failed ? 'load-error' : entryModule.loaded ? 'load-event-fired' : entryModule.observed ? 'requested-but-no-load-or-error-event' : 'script-element-not-observed'
            },
            moduleResources: moduleResources(),
            events: events.slice(-40)
          });
          const mark = (phase) => events.push({ time: new Date().toISOString(), message: 'Phase: ' + phase });
          const trackEntryModule = (script) => {
            if (!(script instanceof HTMLScriptElement) || script.type !== 'module' || !script.src || seenScripts.has(script)) return;
            seenScripts.add(script);
            if (!script.src.includes('/src/main.tsx')) return;
            entryModule.src = script.src;
            entryModule.observed = true;
            mark('entry module script observed; request may be in progress');
            script.addEventListener('load', () => {
              entryModule.loaded = true;
              mark('entry module load event fired; entry and static module graph completed');
            }, { once: true });
            script.addEventListener('error', () => {
              entryModule.failed = true;
              show('Entry module script reported a load or module-graph error: ' + cleanUrl(script.src), 'Inspect the module resource timings and Android Chrome console for the failed imported module.');
            }, { once: true });
          };
          const scriptObserver = new MutationObserver((mutations) => {
            for (const mutation of mutations) for (const node of mutation.addedNodes) {
              if (node instanceof HTMLScriptElement) trackEntryModule(node);
              else if (node.querySelectorAll) node.querySelectorAll('script[type="module"]').forEach(trackEntryModule);
            }
          });
          scriptObserver.observe(document.documentElement, { childList: true, subtree: true });
          document.querySelectorAll('script[type="module"]').forEach(trackEntryModule);
          const render = () => {
            if (!overlay) {
              overlay = document.createElement('section');
              overlay.id = 'kh-dev-startup-diagnostics';
              overlay.setAttribute('role', 'alert');
              overlay.setAttribute('aria-live', 'assertive');
              overlay.style.cssText = 'position:fixed;inset:0;z-index:2147483647;overflow:auto;padding:20px;background:#111827;color:#f9fafb;font:14px/1.45 system-ui,-apple-system,sans-serif;box-sizing:border-box';
              document.body.appendChild(overlay);
            }
            const latest = events.slice(-8).map((entry) => '<li><b>' + escapeHtml(entry.time) + '</b> ' + escapeHtml(entry.message) + (entry.stack ? '<pre style="white-space:pre-wrap;overflow-wrap:anywhere">' + escapeHtml(entry.stack) + '</pre>' : '') + '</li>').join('');
            overlay.innerHTML = '<div style="max-width:900px;margin:auto"><h1 style="font-size:22px;margin:0 0 8px">Kisan Hita startup diagnostic</h1><p style="margin:0 0 16px">Development-only report. Send this report to diagnose the blank screen.</p><h2 style="font-size:16px">Latest event</h2><p style="overflow-wrap:anywhere">' + escapeHtml(events.length ? events[events.length - 1].message : 'React did not confirm a mount before the diagnostic timeout.') + '</p><h2 style="font-size:16px">Startup events</h2><ol>' + latest + '</ol><p>Browser: ' + escapeHtml(navigator.userAgent) + '<br>Viewport: ' + innerWidth + ' × ' + innerHeight + '<br>Entry: /src/main.tsx<br>Entry module state: ' + (entryModule.failed ? 'error' : entryModule.loaded ? 'loaded' : entryModule.observed ? 'request observed; no completion event yet' : 'script not observed') + '<br>React mounted: ' + mounted + '</p><button id="kh-copy-diagnostics" type="button" style="min-height:48px;padding:10px 16px;border:0;border-radius:8px;background:#fbbf24;color:#111827;font:600 16px system-ui">Copy diagnostic report</button><span id="kh-copy-status" style="margin-left:12px"></span></div>';
            overlay.querySelector('#kh-copy-diagnostics').addEventListener('click', async () => {
              const report = JSON.stringify(details(), null, 2);
              try {
                await navigator.clipboard.writeText(report);
                overlay.querySelector('#kh-copy-status').textContent = 'Copied';
              } catch {
                const field = document.createElement('textarea');
                field.value = report;
                field.setAttribute('readonly', '');
                field.style.cssText = 'position:fixed;left:-9999px;top:0';
                document.body.appendChild(field);
                field.select();
                const copied = document.execCommand('copy');
                field.remove();
                overlay.querySelector('#kh-copy-status').textContent = copied ? 'Copied' : 'Copy unavailable; share a screenshot';
              }
            });
          };
          const show = (message, stack) => {
            events.push({ time: new Date().toISOString(), message: safe(message), stack: stack ? safe(stack) : '' });
            render();
          };
          window.__KH_STARTUP_DIAGNOSTICS__ = {
            mark,
            report: (error, info) => show('React startup error: ' + (error && error.message || error), info && info.componentStack || error && error.stack),
            mounted: () => { mounted = true; mark('React mounted successfully'); if (overlay) overlay.remove(); overlay = null; clearTimeout(watchdog); }
          };
          window.addEventListener('error', (event) => {
            const target = event.target;
            if (target && target !== window) {
              if (target.tagName === 'SCRIPT') {
                trackEntryModule(target);
                const resource = target.src ? cleanUrl(target.src) : target.outerHTML || target.tagName;
                show('Script or module failed to load: ' + resource, 'Check this URL and the module resource timings in the browser report.');
              }
            } else {
              show('JavaScript error: ' + (event.message || 'unknown error') + ' (' + (event.filename || 'unknown file') + ':' + (event.lineno || 0) + ':' + (event.colno || 0) + ')', event.error && event.error.stack);
            }
          }, true);
          window.addEventListener('unhandledrejection', (event) => show('Unhandled promise rejection: ' + safe(event.reason), event.reason && event.reason.stack));
          const watchdog = setTimeout(() => {
            if (mounted) return;
            const state = entryModule.failed ? 'entry module failed' : entryModule.loaded ? 'entry module loaded but React did not confirm mounting' : entryModule.observed ? 'entry module request was observed but has not completed' : 'entry module element was not observed';
            show('No React mount confirmation after 20 seconds (' + state + '). This longer timeout reduces false alarms on slower mobile connections.', JSON.stringify({ entryModule: details().entryModule, moduleResources: moduleResources() }, null, 2));
          }, 20000);
          window.__KH_STARTUP_DIAGNOSTICS__.mark('diagnostic handlers installed before app entry module');
        })();
      </script>`;

      return html.replace('</head>', `${diagnosticScript}</head>`);
    },
  },
});

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [startupDiagnosticsPlugin(), react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
      allowedHosts: ['observation-gore-scanner-amplifier.trycloudflare.com'],
      proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});


/** Validate that the current browser has an explicit account or guest session. */
export async function ensureBrowserSession(): Promise<void> {
  const response = await fetch('/api/auth/session', { credentials: 'same-origin' });
  const data = await response.json().catch(() => null);
  if (!response.ok || !data || !['guest', 'account'].includes(data.mode)) {
    throw new Error(`Session initialization failed (${response.status})`);
  }
}

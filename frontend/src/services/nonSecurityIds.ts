let fallbackSequence = 0;

/**
 * Create an identifier for UI/conversation bookkeeping only.
 *
 * If this browser has no cryptographic random API, the last-resort fallback is
 * based on time, a page-local counter, and Math.random. It is intentionally not
 * secure and MUST NOT be used for authentication, authorization, session
 * tokens, CSRF tokens, or any other security-sensitive value.
 */
export function createNonSecurityUuid(cryptoApi?: Crypto): string {
  const browserCrypto = cryptoApi ?? (typeof globalThis !== 'undefined' ? globalThis.crypto : undefined);

  if (typeof browserCrypto?.randomUUID === 'function') {
    try {
      return browserCrypto.randomUUID();
    } catch {
      // Some older/insecure browser contexts expose randomUUID but throw when
      // it is called. Continue to the getRandomValues path when possible.
    }
  }

  if (typeof browserCrypto?.getRandomValues === 'function') {
    try {
      const bytes = browserCrypto.getRandomValues(new Uint8Array(16));
      bytes[6] = (bytes[6] & 0x0f) | 0x40;
      bytes[8] = (bytes[8] & 0x3f) | 0x80;
      const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
      return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
    } catch {
      // Fall through to the documented non-security fallback.
    }
  }

  fallbackSequence += 1;
  return `local-${Date.now().toString(36)}-${fallbackSequence.toString(36)}-${Math.random().toString(36).slice(2)}`;
}

/** Load a persisted conversation ID once, creating and saving it when absent. */
export function getOrCreateConversationId(
  storage: Pick<Storage, 'getItem' | 'setItem'>,
  key: string,
  cryptoApi?: Crypto,
): string {
  const create = () => `conv_${createNonSecurityUuid(cryptoApi).replace(/-/g, '')}`;
  try {
    const saved = storage.getItem(key);
    if (saved && saved !== 'conv_session' && saved !== 'conv_default') return saved;
    const id = create();
    storage.setItem(key, id);
    return id;
  } catch {
    // Storage can be unavailable in private/restricted browser modes. The
    // provider's lazy useState initializer keeps this ID stable for that mount.
    return create();
  }
}

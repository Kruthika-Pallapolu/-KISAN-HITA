export type BrowserSessionMode = 'none' | 'guest' | 'account';

let currentMode: BrowserSessionMode = 'none';

export function setBrowserSessionMode(mode: BrowserSessionMode): void {
  currentMode = mode;
}

export function getBrowserSessionMode(): BrowserSessionMode {
  return currentMode;
}

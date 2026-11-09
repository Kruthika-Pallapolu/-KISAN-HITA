/** Small pure helpers matching the reference artifact's scroll-to-video timing. */
export const getScrollProgress = (scrollY: number, scrollHeight: number, viewportHeight: number): number => {
  const maxScroll = Math.max(0, scrollHeight - viewportHeight);
  if (maxScroll === 0) return 0;
  return Math.min(1, Math.max(0, scrollY / maxScroll));
};

export const easeScrollProgress = (current: number, target: number, mobile: boolean, reducedMotion: boolean): number => {
  if (reducedMotion) return target;
  return current + (target - current) * (mobile ? 0.22 : 0.14);
};

export const shouldSeekFrame = (seconds: number, previousSeconds: number, mobile: boolean): boolean =>
  previousSeconds < 0 || Math.abs(seconds - previousSeconds) > (mobile ? 1 / 16 : 1 / 48);

export const getVideoTime = (progress: number, duration: number): number =>
  Math.min(Math.max(0, duration - 0.05), Math.max(0, progress * duration));

export const clampProgress = (value: number): number => Math.min(1, Math.max(0, value));

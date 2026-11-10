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

type ScrollVideo = EventTarget & {
  currentTime: number;
  duration: number;
  seeking: boolean;
  readyState: number;
  networkState: number;
  pause(): void;
  load(): void;
};

type ScrubRuntimeOptions = {
  video: ScrollVideo;
  events?: EventTarget;
  readProgress: () => number;
  mobile: () => boolean;
  reducedMotion: () => boolean;
  onUnavailable: () => void;
  requestFrame?: (callback: FrameRequestCallback) => number;
  cancelFrame?: (handle: number) => void;
  setTimer?: (callback: () => void, delay: number) => ReturnType<typeof setTimeout>;
  clearTimer?: (handle: ReturnType<typeof setTimeout>) => void;
};

/** Owns one scroll-scrub video lifecycle, including late readiness and recoverable seeks. */
export class ScrollScrubRuntime {
  private readonly video: ScrollVideo;
  private readonly events: EventTarget;
  private readonly readProgress: () => number;
  private readonly mobile: () => boolean;
  private readonly reducedMotion: () => boolean;
  private readonly onUnavailable: () => void;
  private readonly requestFrame: (callback: FrameRequestCallback) => number;
  private readonly cancelFrame: (handle: number) => void;
  private readonly setTimer: (callback: () => void, delay: number) => ReturnType<typeof setTimeout>;
  private readonly clearTimer: (handle: ReturnType<typeof setTimeout>) => void;
  private active = false;
  private ready = false;
  private unavailable = false;
  private target = 0;
  private current = 0;
  private duration = 0;
  private lastSeek = -1;
  private frameHandle = 0;
  private retryHandle: ReturnType<typeof setTimeout> | null = null;
  private seekFailures = 0;
  private seekBlocked = false;
  private loadingRequested = false;

  constructor(options: ScrubRuntimeOptions) {
    this.video = options.video;
    this.events = options.events ?? window;
    this.readProgress = options.readProgress;
    this.mobile = options.mobile;
    this.reducedMotion = options.reducedMotion;
    this.onUnavailable = options.onUnavailable;
    this.requestFrame = options.requestFrame ?? ((callback) => window.requestAnimationFrame(callback));
    this.cancelFrame = options.cancelFrame ?? ((handle) => window.cancelAnimationFrame(handle));
    this.setTimer = options.setTimer ?? ((callback, delay) => setTimeout(callback, delay));
    this.clearTimer = options.clearTimer ?? ((handle) => clearTimeout(handle));
  }

  mount(): void {
    if (this.active) return;
    this.active = true;
    this.video.addEventListener('loadedmetadata', this.onReadyEvent);
    this.video.addEventListener('loadeddata', this.onReadyEvent);
    this.video.addEventListener('canplay', this.onReadyEvent);
    this.video.addEventListener('durationchange', this.onReadyEvent);
    this.video.addEventListener('seeked', this.onSeeked);
    this.video.addEventListener('error', this.onError);
    this.events.addEventListener('scroll', this.onScroll, { passive: true });
    this.events.addEventListener('resize', this.refresh, { passive: true });
    this.events.addEventListener('pageshow', this.refresh);
    this.events.addEventListener('popstate', this.refresh);

    this.video.pause();
    this.refresh();
    // Handles cached/already-ready media where the event fired before this effect.
    this.checkReady();
  }

  refresh = (): void => {
    if (!this.active) return;
    this.target = clampProgress(this.readProgress());
    if (this.ready && !this.unavailable) this.scheduleFrame();
  };

  destroy(): void {
    if (!this.active) return;
    this.active = false;
    if (this.frameHandle) this.cancelFrame(this.frameHandle);
    if (this.retryHandle) this.clearTimer(this.retryHandle);
    this.frameHandle = 0;
    this.retryHandle = null;
    this.video.removeEventListener('loadedmetadata', this.onReadyEvent);
    this.video.removeEventListener('loadeddata', this.onReadyEvent);
    this.video.removeEventListener('canplay', this.onReadyEvent);
    this.video.removeEventListener('durationchange', this.onReadyEvent);
    this.video.removeEventListener('seeked', this.onSeeked);
    this.video.removeEventListener('error', this.onError);
    this.events.removeEventListener('scroll', this.onScroll);
    this.events.removeEventListener('resize', this.refresh);
    this.events.removeEventListener('pageshow', this.refresh);
    this.events.removeEventListener('popstate', this.refresh);
    this.video.pause();
  }

  private onReadyEvent = (): void => {
    this.video.pause();
    this.checkReady();
  };

  private onScroll = (): void => {
    this.refresh();
    // Some mobile browsers defer metadata despite preload="metadata". Start one
    // request only if scrolling begins while the media element is still empty.
    if (!this.ready && !this.loadingRequested && this.video.networkState === 0) {
      this.loadingRequested = true;
      try {
        this.video.load();
      } catch {
        this.markUnavailable();
      }
    }
  };

  private checkReady(): void {
    if (!this.active || this.ready || this.unavailable) return;
    if (this.video.readyState < 1 || !Number.isFinite(this.video.duration) || this.video.duration <= 0) return;
    this.duration = this.video.duration;
    this.ready = true;
    // Re-read scroll after late metadata: the page may have moved while loading.
    this.target = clampProgress(this.readProgress());
    this.current = this.target;
    this.seekToTarget();
  }

  private onSeeked = (): void => {
    this.seekFailures = 0;
    this.seekBlocked = false;
    if (this.retryHandle) this.clearTimer(this.retryHandle);
    this.retryHandle = null;
    this.refresh();
  };

  private onError = (): void => this.markUnavailable();

  private markUnavailable(): void {
    if (this.unavailable) return;
    this.unavailable = true;
    if (this.frameHandle) this.cancelFrame(this.frameHandle);
    if (this.retryHandle) this.clearTimer(this.retryHandle);
    this.frameHandle = 0;
    this.retryHandle = null;
    this.video.pause();
    this.onUnavailable();
  }

  private scheduleFrame(): void {
    if (this.active && this.ready && !this.unavailable && !this.frameHandle && !this.seekBlocked) {
      this.frameHandle = this.requestFrame(this.tick);
    }
  }

  private scheduleSeekRetry(): void {
    this.seekBlocked = true;
    this.seekFailures += 1;
    const delay = Math.min(1500, 80 * (2 ** Math.min(this.seekFailures - 1, 4)));
    if (this.retryHandle) this.clearTimer(this.retryHandle);
    this.retryHandle = this.setTimer(() => {
      this.retryHandle = null;
      this.seekBlocked = false;
      this.lastSeek = -1;
      this.scheduleFrame();
    }, delay);
  }

  private seekToTarget(): void {
    const seconds = getVideoTime(this.target, this.duration);
    if (!shouldSeekFrame(seconds, this.lastSeek, this.mobile())) return;
    try {
      this.video.currentTime = seconds;
      this.lastSeek = seconds;
      this.scheduleFrame();
    } catch {
      // Seeking can fail transiently while a decoder initializes; retry with backoff.
      this.scheduleSeekRetry();
    }
  }

  private tick: FrameRequestCallback = () => {
    this.frameHandle = 0;
    if (!this.active || !this.ready || this.unavailable || this.seekBlocked) return;
    if (this.video.seeking) {
      this.scheduleFrame();
      return;
    }
    this.target = clampProgress(this.readProgress());
    this.current = easeScrollProgress(this.current, this.target, this.mobile(), this.reducedMotion());
    if (Math.abs(this.target - this.current) < 0.0005) this.current = this.target;
    const seconds = getVideoTime(this.current, this.duration);
    if (shouldSeekFrame(seconds, this.lastSeek, this.mobile())) {
      try {
        this.video.currentTime = seconds;
        this.lastSeek = seconds;
      } catch {
        this.scheduleSeekRetry();
        return;
      }
    }
    if (this.video.seeking || Math.abs(this.target - this.current) >= 0.0005) this.scheduleFrame();
  };
}

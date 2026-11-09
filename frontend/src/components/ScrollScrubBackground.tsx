import React, { useEffect, useRef } from 'react';
import { clampProgress, easeScrollProgress, getScrollProgress, getVideoTime, shouldSeekFrame } from '../services/scrollScrub';

const VIDEO_URL = '/assets/kisan-hita-scroll.mp4';
const POSTER_URL = '/assets/kisan-hita-sunset.png';

/**
 * Scroll-scrubbed version of the background video behavior in the original
 * Kisan Hita HTML artifact. The video is muted and never plays autonomously.
 */
export const ScrollScrubBackground: React.FC = () => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const veilRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const video = videoRef.current;
    const veil = veilRef.current;
    if (!video || !veil) return;

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const mobile = window.matchMedia('(max-width: 760px), (pointer: coarse)').matches;
    let duration = 0;
    let target = 0;
    let current = 0;
    let lastSeek = -1;
    let frameHandle = 0;
    let active = true;
    let seekFailed = false;

    const measure = () => {
      target = getScrollProgress(window.scrollY, document.documentElement.scrollHeight, window.innerHeight);

      // The original artifact scrubs a charcoal veil over its intro and footer.
      const intro = document.querySelector<HTMLElement>('[data-background-intro]');
      let introOpacity = 0;
      if (intro) {
        const rect = intro.getBoundingClientRect();
        const top = rect.top + window.scrollY;
        const start = top - window.innerHeight * 0.8;
        const end = top + rect.height * 0.5 - window.innerHeight * 0.5;
        introOpacity = clampProgress((window.scrollY - start) / Math.max(1, end - start)) * 0.34;
      }

      const footer = document.querySelector<HTMLElement>('footer');
      let footerOpacity = 0;
      if (footer) {
        const top = footer.getBoundingClientRect().top + window.scrollY;
        const start = top - window.innerHeight;
        const end = top - window.innerHeight * 0.3;
        const progress = clampProgress((window.scrollY - start) / Math.max(1, end - start));
        footerOpacity = (intro ? 0.34 : 0) + (0.72 - (intro ? 0.34 : 0)) * progress;
      }
      veil.style.opacity = String(Math.max(introOpacity, footerOpacity));
      if (duration > 0 && !reducedMotion) scheduleFrame();
    };

    const tick = () => {
      frameHandle = 0;
      if (!active || reducedMotion || seekFailed || duration <= 0 || video.seeking) return;
      current = easeScrollProgress(current, target, mobile, false);
      if (Math.abs(target - current) < 0.0005) current = target;
      const seconds = getVideoTime(current, duration);
      if (shouldSeekFrame(seconds, lastSeek, mobile)) {
        try {
          video.currentTime = seconds;
          lastSeek = seconds;
        } catch {
          // Avoid a per-frame retry loop; keep the exact supplied still image visible.
          seekFailed = true;
          video.style.visibility = 'hidden';
        }
      }
      if (Math.abs(target - current) >= 0.0005) scheduleFrame();
    };

    function scheduleFrame() {
      if (active && !frameHandle) frameHandle = window.requestAnimationFrame(tick);
    }

    const onMetadata = () => {
      duration = Number.isFinite(video.duration) ? video.duration : 0;
      video.pause();
      current = target;
      if (duration > 0 && !reducedMotion) {
        try {
          video.currentTime = getVideoTime(current, duration);
          lastSeek = video.currentTime;
        } catch {
          seekFailed = true;
          video.style.visibility = 'hidden';
        }
      }
    };

    const onVideoError = () => {
      video.style.visibility = 'hidden';
    };
    const onSeeked = () => {
      if (Math.abs(target - current) >= 0.0005) scheduleFrame();
    };

    video.pause();
    video.addEventListener('loadedmetadata', onMetadata);
    video.addEventListener('error', onVideoError);
    video.addEventListener('seeked', onSeeked);
    if (reducedMotion) video.style.visibility = 'hidden';
    window.addEventListener('scroll', measure, { passive: true });
    window.addEventListener('resize', measure, { passive: true });
    const resizeObserver = typeof ResizeObserver !== 'undefined'
      ? new ResizeObserver(measure)
      : null;
    resizeObserver?.observe(document.documentElement);
    measure();
    if (!reducedMotion) video.load();

    return () => {
      active = false;
      if (frameHandle) window.cancelAnimationFrame(frameHandle);
      resizeObserver?.disconnect();
      window.removeEventListener('scroll', measure);
      window.removeEventListener('resize', measure);
      video.removeEventListener('loadedmetadata', onMetadata);
      video.removeEventListener('error', onVideoError);
      video.removeEventListener('seeked', onSeeked);
      video.pause();
    };
  }, []);

  return (
    <div className="scroll-scrub-background" aria-hidden="true">
      <video
        ref={videoRef}
        className="scroll-scrub-background__video"
        src={VIDEO_URL}
        poster={POSTER_URL}
        muted
        playsInline
        preload="none"
        tabIndex={-1}
      />
      <div className="scroll-scrub-background__scrim" />
      <div ref={veilRef} className="scroll-scrub-background__veil" />
      <div className="scroll-scrub-background__grain" />
    </div>
  );
};

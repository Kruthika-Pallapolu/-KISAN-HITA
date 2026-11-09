import type { SupportedLanguage } from '../i18n/translations.ts';

// Browser speech synthesis is retained only as the existing output fallback
// when Timbre is disabled. This mapping is not used for speech recognition.
const TTS_LANG_MAP: Record<SupportedLanguage, string> = {
  en: 'en-IN', te: 'te-IN', hi: 'hi-IN', ta: 'ta-IN', kn: 'kn-IN', ml: 'ml-IN', mr: 'mr-IN',
};

/** Split long speech safely under the backend's 2,000-character request limit. */
export function splitSpeechText(text: string, maxChars = 1800): string[] {
  const normalized = text.replace(/\r\n?/g, '\n').replace(/\n+/g, '. ').trim();
  if (!normalized) return [];
  const sentences = normalized.match(/[^.!?।॥…]+[.!?।॥…]+|[^.!?।॥…]+$/gu) || [normalized];
  const chunks: string[] = [];
  let current = '';

  const push = (part: string) => {
    const value = part.trim();
    if (!value) return;
    if (!current) { current = value; return; }
    if (current.length + 1 + value.length <= maxChars) current += ` ${value}`;
    else { chunks.push(current); current = value; }
  };

  for (const sentence of sentences) {
    const cleanSentence = sentence.trim();
    if (!cleanSentence) continue;
    if (cleanSentence.length <= maxChars) { push(cleanSentence); continue; }
    if (current) { chunks.push(current); current = ''; }
    let segment = '';
    for (const word of cleanSentence.split(/\s+/u)) {
      if (word.length > maxChars) {
        if (segment) { chunks.push(segment); segment = ''; }
        const points = Array.from(word);
        while (points.length) chunks.push(points.splice(0, maxChars).join(''));
      } else if (!segment) segment = word;
      else if (segment.length + 1 + word.length <= maxChars) segment += ` ${word}`;
      else { chunks.push(segment); segment = word; }
    }
    current = segment;
  }
  if (current) chunks.push(current);
  return chunks;
}

// Text-to-Speech (TTS) Service
export class SpeechService {
  private static activeAudio: HTMLAudioElement | null = null;
  private static activeUtterance: SpeechSynthesisUtterance | null = null;
  private static activePlaybackCancel: (() => void) | null = null;
  private static activeOnEnd: (() => void) | null = null;
  private static speechToken = 0;

  static async speak(
    text: string,
    language: SupportedLanguage,
    onStart?: () => void,
    onEnd?: () => void,
    onError?: (err: any) => void
  ) {
    this.stop();
    const token = this.speechToken;

    const cleanText = text
      .replace(/[*#_~`[\]()]/g, '')
      .replace(/\n+/g, '. ')
      .trim();

    if (!cleanText) {
      onEnd?.();
      return;
    }
    this.activeOnEnd = onEnd || null;
    const chunks = splitSpeechText(cleanText);
    let didNotifyStart = false;
    const notifyStart = () => {
      if (didNotifyStart) return;
      didNotifyStart = true;
      onStart?.();
    };

    // Read the selected provider first so Timbre failures never silently switch
    // to a different voice. The config response contains no credentials.
    let timbreEnabled = false;
    try {
      const configResponse = await fetch('/api/voice/config', { credentials: 'same-origin' });
      if (!configResponse.ok) throw new Error('Speech provider settings could not be loaded.');
      const config = await configResponse.json();
      timbreEnabled = config?.timbre_enabled === true;
    } catch (error) {
      if (token !== this.speechToken) return;
      onError?.(error);
      this.completeActiveSpeech();
      return;
    }
    if (token !== this.speechToken) return;

    for (let index = 0; index < chunks.length; index += 1) {
      if (token !== this.speechToken) return;
      const chunk = chunks[index];
      try {
        const res = await fetch('/api/voice/tts', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: chunk, language }),
        });
        if (!res.ok) throw new Error(`Speech synthesis failed (HTTP ${res.status}).`);
        const data = await res.json();
        if (token !== this.speechToken) return;
        const responseLanguage = typeof data.language === 'string' ? data.language.split('-')[0].toLowerCase() : '';
        if (!data.audio_base64 || data.audio_base64.length <= 50 || responseLanguage !== language) {
          throw new Error('Speech service returned no playable audio in the selected language.');
        }
        if (timbreEnabled && (data.provider !== 'gnani_live' || data.model !== 'timbre-v3.0' || data.voice_name !== 'Vasudha' || data.format !== 'audio/wav')) {
          throw new Error('Timbre v3.0 did not return the selected Vasudha voice.');
        }
        await this.playAudioChunk(`data:${data.format || 'audio/wav'};base64,${data.audio_base64}`, notifyStart, token);
      } catch (error) {
        if (token !== this.speechToken) return;
        if (timbreEnabled) {
          onError?.(error);
          this.completeActiveSpeech();
          return;
        }
        // Local/browser fallback is allowed only when Timbre is not selected.
        await this.speakWithBrowserFallback(chunks.slice(index).join(' '), language, notifyStart, onError, token);
        return;
      }
    }
    if (token === this.speechToken) this.completeActiveSpeech();
  }

  private static async playAudioChunk(audioUrl: string, onStart: (() => void) | undefined, token: number): Promise<void> {
    const audio = new Audio(audioUrl);
    this.activeAudio = audio;
    await new Promise<void>((resolve, reject) => {
      let settled = false;
      const finish = () => {
        if (settled) return;
        settled = true;
        if (this.activeAudio === audio) this.activeAudio = null;
        this.activePlaybackCancel = null;
        resolve();
      };
      const fail = (error: unknown) => {
        if (settled) return;
        settled = true;
        if (this.activeAudio === audio) this.activeAudio = null;
        this.activePlaybackCancel = null;
        reject(error instanceof Error ? error : new Error('Audio playback failed.'));
      };
      this.activePlaybackCancel = finish;
      audio.onplay = () => { if (token === this.speechToken) onStart?.(); };
      audio.onended = finish;
      audio.onerror = fail;
      Promise.resolve(audio.play()).catch(fail);
    });
  }

  private static async speakWithBrowserFallback(
    cleanText: string,
    language: SupportedLanguage,
    onStart?: () => void,
    onError?: (err: any) => void,
    token = this.speechToken
  ) {
    if (!('speechSynthesis' in window)) {
      onError?.(new Error('Speech synthesis is not supported in this browser.'));
      if (token === this.speechToken) this.completeActiveSpeech();
      return;
    }

    const synthesis = window.speechSynthesis;
    let voices = synthesis.getVoices();
    if (!voices.length && typeof synthesis.addEventListener === 'function') {
      await new Promise<void>((resolve) => {
        let finished = false;
        const done = () => {
          if (finished) return;
          finished = true;
          clearTimeout(timer);
          synthesis.removeEventListener?.('voiceschanged', done);
          resolve();
        };
        const timer = setTimeout(done, 750);
        synthesis.addEventListener('voiceschanged', done, { once: true });
      });
      if (token !== this.speechToken) return;
      voices = synthesis.getVoices();
    }

    const targetLang = TTS_LANG_MAP[language] || 'en-IN';
    const targetPrimary = targetLang.split('-')[0].toLowerCase();
    const matchingVoice = voices.find((voice) =>
      typeof voice.lang === 'string' && voice.lang.split('-')[0].toLowerCase() === targetPrimary
    );
    if (!matchingVoice) {
      onError?.(new Error(`No browser speech voice is available for ${targetLang}.`));
      if (token === this.speechToken) this.completeActiveSpeech();
      return;
    }

    synthesis.cancel();
    try {
      for (const chunk of splitSpeechText(cleanText)) {
        if (token !== this.speechToken) return;
        await new Promise<void>((resolve, reject) => {
          const utterance = new SpeechSynthesisUtterance(chunk);
          utterance.lang = targetLang;
          utterance.rate = 0.95;
          utterance.pitch = 1.0;
          utterance.voice = matchingVoice;
          utterance.onstart = () => { if (token === this.speechToken) onStart?.(); };
          utterance.onend = () => { this.activeUtterance = null; resolve(); };
          utterance.onerror = (event) => {
            this.activeUtterance = null;
            if (token !== this.speechToken) resolve();
            else reject(event);
          };
          this.activeUtterance = utterance;
          window.speechSynthesis.speak(utterance);
        });
      }
      if (token === this.speechToken) this.completeActiveSpeech();
    } catch (error) {
      if (token !== this.speechToken) return;
      onError?.(error);
      this.completeActiveSpeech();
    }
  }

  static stop(notifyOnEnd = false) {
    this.speechToken += 1;
    const hadActiveSpeech = Boolean(this.activeAudio || this.activeUtterance || this.activeOnEnd);
    if (this.activeAudio) {
      this.activeAudio.pause();
      this.activeAudio.currentTime = 0;
      this.activeAudio = null;
    }
    this.activePlaybackCancel?.();
    this.activePlaybackCancel = null;
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    this.activeUtterance = null;
    if (notifyOnEnd && hadActiveSpeech) this.completeActiveSpeech();
    else this.activeOnEnd = null;
  }

  private static completeActiveSpeech() {
    const onEnd = this.activeOnEnd;
    this.activeOnEnd = null;
    onEnd?.();
  }

  static isSpeaking(): boolean {
    if (this.activeAudio && !this.activeAudio.paused) {
      return true;
    }
    if ('speechSynthesis' in window) {
      return window.speechSynthesis.speaking;
    }
    return false;
  }
}


const SUPPORTED_MIME_TYPES = [
  'audio/mp4',
  'audio/wav',
  'audio/mpeg',
  'audio/ogg',
  'audio/flac',
  'audio/aac',
];

const FILE_EXTENSIONS: Record<string, string> = {
  'audio/mp4': 'm4a',
  'audio/wav': 'wav',
  'audio/mpeg': 'mp3',
  'audio/ogg': 'ogg',
  'audio/flac': 'flac',
  'audio/aac': 'aac',
};

export interface RecordedPrismaAudio {
  blob: Blob;
  mimeType: string;
  filename: string;
  durationSeconds: number;
}

/** Records a deliberate, foreground clip initiated by the user. */
export class PrismaManualRecorder {
  private stream: MediaStream | null = null;
  private recorder: MediaRecorder | null = null;
  private chunks: Blob[] = [];
  private startedAt = 0;
  private resultPromise: Promise<RecordedPrismaAudio> | null = null;

  async start(existingStream?: MediaStream): Promise<void> {
    if (typeof MediaRecorder === 'undefined') throw new Error('Manual audio recording is not supported in this browser.');
    this.stream = existingStream || await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeType = SUPPORTED_MIME_TYPES.find((candidate) => MediaRecorder.isTypeSupported(candidate));
    if (!mimeType) {
      this.stream.getTracks().forEach((track) => track.stop());
      this.stream = null;
      throw new Error('This browser cannot record an audio format supported by Prisma.');
    }

    this.chunks = [];
    this.recorder = new MediaRecorder(this.stream, { mimeType });
    this.resultPromise = new Promise((resolve, reject) => {
      const activeRecorder = this.recorder!;
      activeRecorder.ondataavailable = (event) => { if (event.data?.size) this.chunks.push(event.data); };
      activeRecorder.onerror = () => {
        this.releaseStream();
        reject(new Error('Audio recording failed.'));
      };
      activeRecorder.onstop = () => {
        const durationSeconds = (Date.now() - this.startedAt) / 1000;
        const blob = new Blob(this.chunks, { type: mimeType });
        this.releaseStream();
        if (!blob.size) reject(new Error('The recording is empty.'));
        else resolve({ blob, mimeType, filename: `recording.${FILE_EXTENSIONS[mimeType]}`, durationSeconds });
      };
      this.startedAt = Date.now();
    });
    try {
      this.recorder.start(250);
    } catch (error) {
      this.releaseStream();
      this.recorder = null;
      this.resultPromise = null;
      throw error;
    }
  }

  async stop(): Promise<RecordedPrismaAudio> {
    const recorder = this.recorder;
    if (!recorder || !this.resultPromise) throw new Error('No Prisma recording is active.');
    const resultPromise = this.resultPromise;
    if (recorder.state !== 'inactive') recorder.stop();
    this.recorder = null;
    return resultPromise;
  }

  cancel(): void {
    const recorder = this.recorder;
    this.recorder = null;
    if (recorder && recorder.state !== 'inactive') {
      recorder.onstop = null;
      try { recorder.stop(); } catch {}
    }
    this.releaseStream();
    this.chunks = [];
    this.resultPromise = null;
  }

  private releaseStream() {
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
  }
}

export async function uploadPrismaRecording(
  recording: RecordedPrismaAudio,
  language: string,
  fetcher: typeof fetch = fetch,
): Promise<string> {
  if (recording.durationSeconds <= 0 || recording.durationSeconds > 30) {
    throw new Error('Prisma v3.0 accepts recordings up to 30 seconds.');
  }
  const form = new FormData();
  form.append('file', recording.blob, recording.filename);
  form.append('language', language);
  form.append('duration_seconds', String(recording.durationSeconds));
  const response = await fetcher('/api/voice/stt/upload', {
    method: 'POST',
    credentials: 'same-origin',
    body: form,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : 'Prisma transcription failed.');
  if (typeof data?.transcript !== 'string' || !data.transcript.trim()) throw new Error('Prisma returned no usable transcript.');
  return data.transcript.trim();
}

/**
 * Browser Microphone Voice Recorder + Client-Side 16kHz Mono WAV Encoder
 * Guarantees reliable Mandarin speech capture even in domestic networks where
 * Chrome's built-in webkitSpeechRecognition fails with `network`.
 */

export interface VoiceCaptureCallbacks {
  onLevels?: (bars: number[]) => void;
  onInterimText?: (text: string) => void;
  onElapsed?: (seconds: number) => void;
  onAutoStop?: () => void;
}

export interface VoiceCaptureResult {
  wavBlob: Blob;
  durationSec: number;
  browserTranscript: string;
}

function encodeMonoWav16Bit(samples: Float32Array, sampleRate = 16000): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  const writeString = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  };

  writeString(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true); // PCM chunk size
  view.setUint16(20, 1, true); // PCM format
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  writeString(36, "data");
  view.setUint32(40, samples.length * 2, true);

  let offset = 44;
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    offset += 2;
  }

  return new Blob([buffer], { type: "audio/wav" });
}

async function convertAudioBlobToWav16k(blob: Blob): Promise<Blob> {
  const AudioCtx =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  if (!AudioCtx) return blob;

  const ctx = new AudioCtx();
  try {
    const arrayBuffer = await blob.arrayBuffer();
    const decoded = await ctx.decodeAudioData(arrayBuffer);
    const targetRate = 16000;
    const frameCount = Math.max(1, Math.ceil(decoded.duration * targetRate));
    const OfflineCtx =
      window.OfflineAudioContext ||
      (window as unknown as { webkitOfflineAudioContext: typeof OfflineAudioContext })
        .webkitOfflineAudioContext;

    if (!OfflineCtx) {
      const ch0 = decoded.getChannelData(0);
      return encodeMonoWav16Bit(ch0, decoded.sampleRate);
    }

    const offline = new OfflineCtx(1, frameCount, targetRate);
    const source = offline.createBufferSource();
    source.buffer = decoded;
    source.connect(offline.destination);
    source.start(0);
    const rendered = await offline.startRendering();
    const monoSamples = rendered.getChannelData(0);
    return encodeMonoWav16Bit(monoSamples, targetRate);
  } finally {
    try {
      await ctx.close();
    } catch {}
  }
}

export class VoiceCaptureSession {
  private stream: MediaStream | null = null;
  private recorder: MediaRecorder | null = null;
  private chunks: BlobPart[] = [];
  private audioCtx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private rafId: number | null = null;
  private timerId: number | null = null;
  private maxLimitId: number | null = null;
  private startedAt = 0;
  private recognition: any = null;
  private browserTranscript = "";
  private stopped = false;

  async start(callbacks: VoiceCaptureCallbacks = {}): Promise<void> {
    if (
      typeof navigator === "undefined" ||
      !navigator.mediaDevices ||
      !navigator.mediaDevices.getUserMedia
    ) {
      throw new Error("当前浏览器不支持麦克风录音，请使用 Chrome / Edge / Safari 或直接输入文字");
    }

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    this.stream = stream;
    this.chunks = [];
    this.browserTranscript = "";
    this.stopped = false;
    this.startedAt = Date.now();

    // Choose the cleanest supported MediaRecorder mime type
    const mimeCandidates = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/mp4",
      "audio/ogg;codecs=opus",
    ];
    let mimeType = "";
    if (typeof MediaRecorder !== "undefined" && typeof MediaRecorder.isTypeSupported === "function") {
      mimeType = mimeCandidates.find((m) => MediaRecorder.isTypeSupported(m)) || "";
    }

    const recorder = mimeType
      ? new MediaRecorder(stream, { mimeType })
      : new MediaRecorder(stream);
    this.recorder = recorder;
    recorder.ondataavailable = (ev: BlobEvent) => {
      if (ev.data && ev.data.size > 0) {
        this.chunks.push(ev.data);
      }
    };
    recorder.start(250);

    // Live 12-bar audio level visualizer
    try {
      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (AudioCtx) {
        const audioCtx = new AudioCtx();
        if (audioCtx.state === "suspended") {
          try {
            await audioCtx.resume();
          } catch {}
        }
        this.audioCtx = audioCtx;
        const src = audioCtx.createMediaStreamSource(stream);
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 64;
        src.connect(analyser);
        this.analyser = analyser;

        const bins = new Uint8Array(analyser.frequencyBinCount);
        const tick = () => {
          if (this.stopped || !this.analyser) return;
          this.analyser.getByteFrequencyData(bins);
          const bars: number[] = [];
          for (let i = 0; i < 12; i++) {
            const val = bins[Math.min(bins.length - 1, i + 1)] || 0;
            bars.push(Math.max(0.12, Math.min(1, val / 170)));
          }
          callbacks.onLevels?.(bars);
          this.rafId = window.requestAnimationFrame(tick);
        };
        this.rafId = window.requestAnimationFrame(tick);
      }
    } catch {
      // Visualizer is strictly optional
    }

    // Do not open concurrent SpeechRecognition to avoid dual microphone contention on iOS/Android/macOS Safari

    this.timerId = window.setInterval(() => {
      const sec = Math.max(0, Math.floor((Date.now() - this.startedAt) / 1000));
      callbacks.onElapsed?.(sec);
    }, 250);

    // Safety cap at 25 seconds so audio stays compact and fast to transcribe
    this.maxLimitId = window.setTimeout(() => {
      if (!this.stopped) {
        callbacks.onAutoStop?.();
      }
    }, 25000);
  }

  private cleanupResources() {
    this.stopped = true;
    if (this.rafId !== null) {
      window.cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
    if (this.timerId !== null) {
      window.clearInterval(this.timerId);
      this.timerId = null;
    }
    if (this.maxLimitId !== null) {
      window.clearTimeout(this.maxLimitId);
      this.maxLimitId = null;
    }
    if (this.recognition) {
      try {
        this.recognition.stop();
      } catch {}
      this.recognition = null;
    }
    if (this.audioCtx) {
      try {
        this.audioCtx.close();
      } catch {}
      this.audioCtx = null;
      this.analyser = null;
    }
    if (this.stream) {
      this.stream.getTracks().forEach((t) => {
        try {
          t.stop();
        } catch {}
      });
      this.stream = null;
    }
  }

  async stop(): Promise<VoiceCaptureResult> {
    const durationSec = Math.max(
      0.1,
      Math.round(((Date.now() - this.startedAt) / 1000) * 10) / 10
    );

    const recorder = this.recorder;
    const rawBlob = await new Promise<Blob>((resolve) => {
      if (!recorder || recorder.state === "inactive") {
        resolve(new Blob(this.chunks, { type: "audio/webm" }));
        return;
      }
      recorder.onstop = () => {
        const mime = recorder.mimeType || "audio/webm";
        resolve(new Blob(this.chunks, { type: mime }));
      };
      try {
        recorder.stop();
      } catch {
        resolve(new Blob(this.chunks, { type: "audio/webm" }));
      }
    });

    this.cleanupResources();
    this.recorder = null;

    let wavBlob = rawBlob;
    try {
      if (rawBlob.size > 0) {
        wavBlob = await convertAudioBlobToWav16k(rawBlob);
      }
    } catch {
      // Fallback to raw blob if browser cannot decode specific audio container
      wavBlob = rawBlob;
    }

    return {
      wavBlob,
      durationSec,
      browserTranscript: this.browserTranscript.trim(),
    };
  }

  cancel() {
    if (this.recorder && this.recorder.state !== "inactive") {
      try {
        this.recorder.stop();
      } catch {}
    }
    this.recorder = null;
    this.chunks = [];
    this.cleanupResources();
  }
}

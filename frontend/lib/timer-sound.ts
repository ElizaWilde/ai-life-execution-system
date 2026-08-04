let timerAudioContext: AudioContext | null = null;
const TIMER_SOUND_DEDUPE_KEY = "ai-life-last-timer-sound";

function getTimerAudioContext() {
  if (typeof window === "undefined") return null;
  if (timerAudioContext) return timerAudioContext;
  const AudioContextClass = window.AudioContext
    ?? (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioContextClass) return null;
  timerAudioContext = new AudioContextClass();
  return timerAudioContext;
}

export async function primeTimerSound() {
  try {
    const context = getTimerAudioContext();
    if (context?.state === "suspended") await context.resume();
  } catch {
    // The next explicit timer interaction will try again.
  }
}

export async function playTimerCompleteSound(notificationId?: string | number) {
  try {
    const soundId = notificationId === undefined ? null : String(notificationId);
    if (
      soundId &&
      typeof window !== "undefined" &&
      window.localStorage.getItem(TIMER_SOUND_DEDUPE_KEY) === soundId
    ) return;

    const context = getTimerAudioContext();
    if (!context) return;
    if (context.state === "suspended") await context.resume();
    if (soundId) window.localStorage.setItem(TIMER_SOUND_DEDUPE_KEY, soundId);

    const startAt = context.currentTime + 0.02;
    [880, 988, 1175].forEach((frequency, index) => {
      const noteAt = startAt + index * 0.2;
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = "sine";
      oscillator.frequency.setValueAtTime(frequency, noteAt);
      gain.gain.setValueAtTime(0.0001, noteAt);
      gain.gain.exponentialRampToValueAtTime(0.22, noteAt + 0.015);
      gain.gain.exponentialRampToValueAtTime(0.0001, noteAt + 0.16);
      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator.start(noteAt);
      oscillator.stop(noteAt + 0.17);
    });
  } catch {
    // Browsers may block background audio until the next user interaction.
  }
}

export function playTimerStartSound(notificationId?: string | number) {
  const soundId = notificationId === undefined
    ? `timer-start-${Date.now()}`
    : `timer-start-${notificationId}`;
  return playTimerCompleteSound(soundId);
}

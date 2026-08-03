import { AppSettings } from "./settings";

export type FocusMusicSource = "rain" | "campfire" | "external";

let audioContext: AudioContext | null = null;
let ambientSource: AudioBufferSourceNode | null = null;
let ambientGain: GainNode | null = null;
let externalAudio: HTMLAudioElement | null = null;
let youtubeEmbed: HTMLIFrameElement | null = null;
let activeSource = "";
let musicIsPlaying = false;

function sendYouTubeCommand(command: "playVideo" | "pauseVideo") {
  youtubeEmbed?.contentWindow?.postMessage(JSON.stringify({
    event: "command",
    func: command,
    args: [],
  }), "https://www.youtube.com");
}

function pauseCurrentMusic() {
  if (ambientSource) {
    try { ambientSource.stop(); } catch { /* It may already have stopped. */ }
    ambientSource.disconnect();
    ambientSource = null;
    activeSource = "";
  }
  ambientGain?.disconnect();
  ambientGain = null;
  externalAudio?.pause();
  sendYouTubeCommand("pauseVideo");
  musicIsPlaying = false;
}

function disposeCurrentMusic() {
  pauseCurrentMusic();
  if (externalAudio) {
    externalAudio.removeAttribute("src");
    externalAudio.load();
    externalAudio = null;
  }
  if (youtubeEmbed) {
    youtubeEmbed.removeAttribute("src");
    youtubeEmbed.remove();
    youtubeEmbed = null;
  }
  activeSource = "";
}

function parseYouTubeUrl(value: string) {
  try {
    const url = new URL(value);
    const host = url.hostname.toLowerCase().replace(/^www\./, "");
    let videoId = "";
    if (host === "youtu.be") videoId = url.pathname.split("/").filter(Boolean)[0] ?? "";
    if (["youtube.com", "m.youtube.com", "music.youtube.com"].includes(host)) {
      videoId = url.searchParams.get("v") ?? "";
      if (!videoId && /^\/(embed|shorts)\//.test(url.pathname)) {
        videoId = url.pathname.split("/").filter(Boolean)[1] ?? "";
      }
    }
    if (!/^[A-Za-z0-9_-]{11}$/.test(videoId)) return null;
    return { videoId, list: url.searchParams.get("list") };
  } catch {
    return null;
  }
}

function playYouTube(url: string) {
  const parsed = parseYouTubeUrl(url);
  if (!parsed) return false;
  const params = new URLSearchParams({
    autoplay: "1",
    controls: "0",
    enablejsapi: "1",
    loop: "1",
    modestbranding: "1",
    playsinline: "1",
    playlist: parsed.list || parsed.videoId,
  });
  const iframe = document.createElement("iframe");
  iframe.src = `https://www.youtube.com/embed/${parsed.videoId}?${params}`;
  iframe.title = "Focus background music";
  iframe.allow = "autoplay; encrypted-media";
  iframe.setAttribute("aria-hidden", "true");
  iframe.style.cssText = "position:fixed;width:1px;height:1px;bottom:0;right:0;opacity:.01;pointer-events:none;border:0";
  document.body.appendChild(iframe);
  youtubeEmbed = iframe;
  return true;
}

function createAmbientBuffer(context: AudioContext, source: Exclude<FocusMusicSource, "external">) {
  const buffer = context.createBuffer(1, context.sampleRate * 12, context.sampleRate);
  const samples = buffer.getChannelData(0);
  let brownNoise = 0;
  for (let index = 0; index < samples.length; index += 1) {
    const whiteNoise = Math.random() * 2 - 1;
    brownNoise = (brownNoise + 0.02 * whiteNoise) / 1.02;
    samples[index] += source === "rain" ? whiteNoise * 0.28 + brownNoise * 1.2 : brownNoise * 2.4;
    if (source === "campfire" && Math.random() < 0.00055) {
      const length = Math.min(samples.length - index, Math.floor(context.sampleRate * 0.025));
      for (let offset = 0; offset < length; offset += 1) {
        samples[index + offset] += (Math.random() * 2 - 1) * (1 - offset / length) * 0.9;
      }
    }
  }
  return buffer;
}

async function playBuiltIn(source: Exclude<FocusMusicSource, "external">) {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  audioContext ??= new AudioContextClass();
  if (audioContext.state === "suspended") await audioContext.resume();
  const node = audioContext.createBufferSource();
  const gain = audioContext.createGain();
  const filter = audioContext.createBiquadFilter();
  node.buffer = createAmbientBuffer(audioContext, source);
  node.loop = true;
  filter.type = source === "rain" ? "highpass" : "lowpass";
  filter.frequency.value = source === "rain" ? 550 : 1350;
  gain.gain.value = source === "rain" ? 0.24 : 0.3;
  node.connect(filter).connect(gain).connect(audioContext.destination);
  node.start();
  ambientSource = node;
  ambientGain = gain;
}

export async function syncFocusMusic(shouldPlay: boolean, settings: AppSettings) {
  if (typeof window === "undefined") return;
  const source = settings.focusMusicSource;
  const sourceKey = source === "external" ? `external:${settings.focusMusicUrl.trim()}` : source;
  if (!shouldPlay || !settings.focusMusicEnabled) {
    pauseCurrentMusic();
    return;
  }
  if (activeSource === sourceKey) {
    if (musicIsPlaying) return;
    if (externalAudio) await externalAudio.play();
    if (youtubeEmbed) sendYouTubeCommand("playVideo");
    musicIsPlaying = true;
    return;
  }
  disposeCurrentMusic();
  if (source === "external") {
    const url = settings.focusMusicUrl.trim();
    if (!/^https?:\/\//i.test(url)) throw new Error("Enter a valid http(s), YouTube, or direct audio URL.");
    if (!playYouTube(url)) {
      const audio = new Audio(url);
      audio.loop = true;
      audio.volume = 0.35;
      externalAudio = audio;
      await audio.play();
    }
  } else {
    await playBuiltIn(source);
  }
  activeSource = sourceKey;
  musicIsPlaying = true;
}

export function stopFocusMusic() { pauseCurrentMusic(); }

declare global {
  interface Window { webkitAudioContext: typeof AudioContext; }
}

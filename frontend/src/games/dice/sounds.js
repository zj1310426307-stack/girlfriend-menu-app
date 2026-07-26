export const DICE_SOUND_PATHS = {
  roll: "/sounds/dice_roll.mp3",
  hit: "/sounds/dice_hit.mp3",
  cup: "/sounds/cup_shake.mp3",
};

const audioCache = new Map();
let audioContext = null;
let soundEnabled = true;
let lastHitAt = 0;
let customSourcesEnabled = false;

/**
 * Enables or disables all dice-game sound playback.
 */
export function setDiceSoundEnabled(enabled) {
  soundEnabled = enabled;
}

/**
 * Allows a future release to switch from synthesized sound to licensed files.
 */
export function useCustomDiceSoundFiles(enabled) {
  customSourcesEnabled = enabled;
}

/**
 * Lazily creates a Web Audio context after the first user gesture.
 */
function getAudioContext() {
  if (typeof window === "undefined") {
    return null;
  }
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) {
    return null;
  }
  if (!audioContext) {
    audioContext = new AudioContextClass();
  }
  if (audioContext.state === "suspended") {
    audioContext.resume().catch(() => {});
  }
  return audioContext;
}

/**
 * Produces an original short impact sound without requiring a downloaded asset.
 */
function synthesizeImpact(volume, force = 18) {
  const context = getAudioContext();
  if (!context) {
    return;
  }
  const duration = 0.075 + Math.min(force, 70) / 900;
  const buffer = context.createBuffer(1, Math.ceil(context.sampleRate * duration), context.sampleRate);
  const data = buffer.getChannelData(0);
  for (let index = 0; index < data.length; index += 1) {
    const envelope = Math.pow(1 - index / data.length, 3.6);
    data[index] = (Math.random() * 2 - 1) * envelope;
  }
  const source = context.createBufferSource();
  const filter = context.createBiquadFilter();
  const gain = context.createGain();
  filter.type = "bandpass";
  filter.frequency.value = 820 + Math.min(force, 70) * 18;
  filter.Q.value = 1.3;
  gain.gain.value = volume;
  source.buffer = buffer;
  source.connect(filter).connect(gain).connect(context.destination);
  source.start();
}

/**
 * Produces a layered cup-and-dice rolling sound using filtered noise.
 */
function synthesizeRoll(name, volume) {
  const context = getAudioContext();
  if (!context) {
    return;
  }
  const duration = name === "cup" ? 0.52 : 0.78;
  const buffer = context.createBuffer(1, Math.ceil(context.sampleRate * duration), context.sampleRate);
  const data = buffer.getChannelData(0);
  for (let index = 0; index < data.length; index += 1) {
    const time = index / context.sampleRate;
    const pulse = 0.35 + Math.abs(Math.sin(time * (name === "cup" ? 72 : 108))) * 0.65;
    const envelope = Math.sin(Math.min(1, time / 0.04) * Math.PI / 2) *
      Math.pow(1 - index / data.length, 0.65);
    data[index] = (Math.random() * 2 - 1) * pulse * envelope;
  }
  const source = context.createBufferSource();
  const filter = context.createBiquadFilter();
  const gain = context.createGain();
  filter.type = "lowpass";
  filter.frequency.value = name === "cup" ? 520 : 1600;
  gain.gain.value = volume;
  source.buffer = buffer;
  source.connect(filter).connect(gain).connect(context.destination);
  source.start();
}

/**
 * Plays a licensed file when configured, otherwise uses original synthesized audio.
 */
export function playDiceSound(name, volume = 0.55) {
  if (!soundEnabled || !DICE_SOUND_PATHS[name]) {
    return;
  }

  if (customSourcesEnabled && typeof Audio !== "undefined") {
    let audio = audioCache.get(name);
    if (!audio) {
      audio = new Audio(DICE_SOUND_PATHS[name]);
      audio.preload = "auto";
      audioCache.set(name, audio);
    }
    audio.volume = volume;
    audio.currentTime = 0;
    audio.play().catch(() => {});
    return;
  }
  synthesizeRoll(name, volume);
}

/**
 * Plays a throttled collision sound so several dice do not create audio noise.
 */
export function playDiceHit(force = 18) {
  const now = performance.now();
  if (now - lastHitAt < 95) {
    return;
  }
  lastHitAt = now;
  if (customSourcesEnabled) {
    playDiceSound("hit", Math.min(0.48, 0.2 + force / 220));
  } else if (soundEnabled) {
    synthesizeImpact(Math.min(0.22, 0.08 + force / 520), force);
  }
}

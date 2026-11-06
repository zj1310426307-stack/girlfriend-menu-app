import Taro from "@tarojs/taro";

/**
 * Lightweight game feedback: short synthesized sounds plus haptic pulses.
 *
 * Sounds live in dist/assets/sounds (copied by the build config) and are
 * referenced with absolute mini-program paths so subpackage pages can use
 * them too. Each sound keeps ONE cached InnerAudioContext that is replayed
 * with seek(0); contexts are never left dangling (E-09 discipline).
 *
 * obeyMuteSwitch stays true (default) so the phone's silent switch mutes
 * game sounds; haptics are independent of it.
 */

const SOUND_PATHS = {
  tap: "/assets/sounds/tap.wav", // 落子 / 选牌 / 轻点击
  win: "/assets/sounds/win.wav", // 对局胜利
  dice: "/assets/sounds/dice.wav" // 摇骰 / 开盅
};

const audioContexts = {};

/** Lazily create one reusable audio context per sound name. */
function getAudioContext(name) {
  if (!SOUND_PATHS[name]) return null;
  if (!audioContexts[name]) {
    const audio = Taro.createInnerAudioContext();
    audio.src = SOUND_PATHS[name];
    audio.obeyMuteSwitch = true;
    audio.onError(() => {
      // A failed context is useless; drop it so the next attempt recreates it.
      try { audio.destroy(); } catch (error) { /* already gone */ }
      delete audioContexts[name];
    });
    audioContexts[name] = audio;
  }
  return audioContexts[name];
}

/** Play one short sound; never throws, never blocks the caller. */
export function playSound(name) {
  try {
    const audio = getAudioContext(name);
    if (!audio) return;
    audio.stop();
    audio.seek(0);
    audio.play();
  } catch (error) {
    // Feedback must never break gameplay; swallow runtime errors silently.
  }
}

/** Light haptic pulse; safe to call anywhere. */
export function vibrateLight() {
  try {
    Taro.vibrateShort({ type: "light" }).catch(() => {});
  } catch (error) {
    // Some runtimes throw synchronously; ignore.
  }
}

/** Combined feedback for interactive moments: sound + light vibration. */
export function playFeedback(name, { haptic = true } = {}) {
  playSound(name);
  if (haptic) vibrateLight();
}

/** Clean up every cached audio context (call from page onUnload if needed). */
export function destroyFeedbackSounds() {
  Object.keys(audioContexts).forEach((name) => {
    try { audioContexts[name].destroy(); } catch (error) { /* ignore */ }
    delete audioContexts[name];
  });
}

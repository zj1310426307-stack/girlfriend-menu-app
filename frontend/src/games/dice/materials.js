import { useEffect, useMemo } from "react";
import {
  CanvasTexture,
  RepeatWrapping,
  SRGBColorSpace,
} from "three";

/**
 * Creates a repeatable canvas texture and configures it for PBR material maps.
 */
function createCanvasTexture(size, painter, { color = false, repeat = [4, 4] } = {}) {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");
  painter(context, size);
  const texture = new CanvasTexture(canvas);
  texture.wrapS = RepeatWrapping;
  texture.wrapT = RepeatWrapping;
  texture.repeat.set(...repeat);
  texture.anisotropy = 4;
  if (color) {
    texture.colorSpace = SRGBColorSpace;
  }
  texture.needsUpdate = true;
  return texture;
}

/**
 * Builds subtle ceramic grain for the matte white dice material.
 */
function createDiceMicroTexture() {
  return createCanvasTexture(
    128,
    (context, size) => {
      const image = context.createImageData(size, size);
      for (let index = 0; index < image.data.length; index += 4) {
        const grain = 218 + Math.floor(Math.random() * 34);
        image.data[index] = grain;
        image.data[index + 1] = grain;
        image.data[index + 2] = grain;
        image.data[index + 3] = 255;
      }
      context.putImageData(image, 0, 0);
    },
    { repeat: [3, 3] },
  );
}

/**
 * Builds blue felt fibers with tiny directional highlights for the dice table.
 */
function createFeltTextures() {
  const colorMap = createCanvasTexture(
    256,
    (context, size) => {
      context.fillStyle = "#174f80";
      context.fillRect(0, 0, size, size);
      for (let index = 0; index < 1600; index += 1) {
        const lightness = 38 + Math.random() * 18;
        context.strokeStyle = `hsla(203, 58%, ${lightness}%, ${0.08 + Math.random() * 0.12})`;
        context.lineWidth = 0.45 + Math.random() * 0.8;
        const x = Math.random() * size;
        const y = Math.random() * size;
        context.beginPath();
        context.moveTo(x, y);
        context.lineTo(x + 2 + Math.random() * 7, y + (Math.random() - 0.5) * 2);
        context.stroke();
      }
    },
    { color: true, repeat: [4, 4] },
  );
  const bumpMap = createCanvasTexture(
    128,
    (context, size) => {
      context.fillStyle = "#777";
      context.fillRect(0, 0, size, size);
      for (let index = 0; index < 900; index += 1) {
        const value = 90 + Math.floor(Math.random() * 95);
        context.strokeStyle = `rgb(${value},${value},${value})`;
        context.lineWidth = 0.5;
        const x = Math.random() * size;
        const y = Math.random() * size;
        context.beginPath();
        context.moveTo(x, y);
        context.lineTo(x + 4 + Math.random() * 5, y);
        context.stroke();
      }
    },
    { repeat: [5, 5] },
  );
  return { colorMap, bumpMap };
}

/**
 * Builds fine leather pores used by the modeled dice cup.
 */
function createLeatherTexture() {
  return createCanvasTexture(
    192,
    (context, size) => {
      context.fillStyle = "#707070";
      context.fillRect(0, 0, size, size);
      for (let index = 0; index < 2300; index += 1) {
        const value = 80 + Math.floor(Math.random() * 70);
        context.fillStyle = `rgba(${value},${value},${value},${0.14 + Math.random() * 0.28})`;
        const radius = 0.35 + Math.random() * 1.1;
        context.beginPath();
        context.arc(Math.random() * size, Math.random() * size, radius, 0, Math.PI * 2);
        context.fill();
      }
    },
    { repeat: [3, 5] },
  );
}

/**
 * Returns reusable dice PBR maps and disposes GPU resources on unmount.
 */
export function useDiceMaterialMaps() {
  const maps = useMemo(() => {
    const microTexture = createDiceMicroTexture();
    return { roughnessMap: microTexture, bumpMap: microTexture };
  }, []);
  useEffect(() => () => maps.roughnessMap.dispose(), [maps]);
  return maps;
}

/**
 * Returns reusable felt PBR maps and disposes GPU resources on unmount.
 */
export function useFeltMaterialMaps() {
  const maps = useMemo(createFeltTextures, []);
  useEffect(
    () => () => {
      maps.colorMap.dispose();
      maps.bumpMap.dispose();
    },
    [maps],
  );
  return maps;
}

/**
 * Returns a leather roughness/bump map for the dice cup.
 */
export function useLeatherMaterialMap() {
  const texture = useMemo(createLeatherTexture, []);
  useEffect(() => () => texture.dispose(), [texture]);
  return texture;
}

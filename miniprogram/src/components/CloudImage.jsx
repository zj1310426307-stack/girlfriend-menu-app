import { useEffect, useMemo, useState } from "react";
import { Image } from "@tarojs/components";
import Taro from "@tarojs/taro";

import { USE_CLOUDBASE_PRIVATE_ACCESS } from "../config/env";
import { requestImageBinary, resolveImageUrl } from "../api/transport";

const imageCache = new Map();

/** Produce a stable, non-sensitive filename for one backend image path. */
function hashPath(value) {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

/** Infer a safe local extension from a response content type. */
function imageExtension(headers = {}) {
  const contentType = String(headers["content-type"] || headers["Content-Type"] || "").toLowerCase();
  if (contentType.includes("jpeg")) return ".jpg";
  if (contentType.includes("png")) return ".png";
  if (contentType.includes("webp")) return ".webp";
  return ".img";
}

/** Resolve a relative backend image through CloudBase and persist it in the user cache. */
async function cachePrivateImage(imageUrl) {
  if (imageCache.has(imageUrl)) return imageCache.get(imageUrl);

  const pending = (async () => {
    const fileSystem = Taro.getFileSystemManager?.();
    const userDataPath = Taro.env?.USER_DATA_PATH || globalThis.wx?.env?.USER_DATA_PATH;
    if (!fileSystem || !userDataPath) throw new Error("当前微信版本不支持图片缓存");

    const response = await requestImageBinary(imageUrl);
    const filePath = `${userDataPath}/loveos-${hashPath(imageUrl)}${imageExtension(response.header)}`;
    await new Promise((resolve, reject) => {
      fileSystem.writeFile({
        filePath,
        data: response.data,
        success: resolve,
        fail: reject
      });
    });
    return filePath;
  })().catch((error) => {
    imageCache.delete(imageUrl);
    throw error;
  });

  imageCache.set(imageUrl, pending);
  return pending;
}

/** Render external images directly and private API images through the local CloudBase cache. */
export default function CloudImage({ src, maxWidth = 0, ...props }) {
  const directSource = useMemo(
    () => resolveImageUrl(src, { maxWidth }),
    [src, maxWidth]
  );
  const needsPrivateFetch = Boolean(
    USE_CLOUDBASE_PRIVATE_ACCESS
    && src
    && !/^(https?:|data:|blob:|wxfile:)/i.test(src)
  );
  const [resolvedSource, setResolvedSource] = useState(needsPrivateFetch ? "" : directSource);

  useEffect(() => {
    let active = true;
    if (!needsPrivateFetch) {
      setResolvedSource(directSource);
      return () => { active = false; };
    }
    setResolvedSource("");
    cachePrivateImage(src)
      .then((filePath) => {
        if (active) setResolvedSource(filePath);
      })
      .catch(() => {
        if (active) setResolvedSource("");
      });
    return () => { active = false; };
  }, [directSource, needsPrivateFetch, src]);

  return <Image {...props} src={resolvedSource} />;
}

const environmentName = process.env.TARO_APP_ENV_NAME || (process.env.NODE_ENV === "development" ? "development" : "production");
const apiOrigin = (process.env.TARO_APP_API_ORIGIN || "").replace(/\/$/, "");
const cloudBaseEnvId = (process.env.TARO_APP_CLOUDBASE_ENV_ID || "").trim();
const cloudBaseService = (process.env.TARO_APP_CLOUDBASE_SERVICE || "").trim();
const useCloudBasePrivateAccess = process.env.TARO_APP_USE_CLOUDBASE_PRIVATE_ACCESS === "true";
const productionApiOrigin = "https://loveos-api-317508-4-1479584710.sh.run.tcloudbase.com";
if (!apiOrigin) {
  throw new Error(`Missing TARO_APP_API_ORIGIN for ${environmentName} build`);
}
if (["staging", "production"].includes(environmentName) && !apiOrigin.startsWith("https://")) {
  throw new Error(`${environmentName} TARO_APP_API_ORIGIN must use HTTPS`);
}
if (environmentName === "staging" && apiOrigin === productionApiOrigin) {
  throw new Error("Staging TARO_APP_API_ORIGIN must not use the production API");
}
if (useCloudBasePrivateAccess && (!cloudBaseEnvId || !cloudBaseService)) {
  throw new Error("CloudBase private access requires TARO_APP_CLOUDBASE_ENV_ID and TARO_APP_CLOUDBASE_SERVICE");
}

const config = {
  projectName: "girlfriend-menu-miniprogram",
  date: "2026-07-14",
  designWidth: 750,
  deviceRatio: {
    640: 2.34 / 2,
    750: 1,
    828: 1.81 / 2
  },
  sourceRoot: "src",
  outputRoot: process.env.TARO_OUTPUT_ROOT || "dist",
  plugins: [],
  // Keep production artifacts deterministic across main-package/subpackage graph changes.
  // Taro 4.2 filesystem cache can retain obsolete numeric module references here.
  cache: {
    enable: false
  },
  defineConstants: {
    __APP_ENV_NAME__: JSON.stringify(environmentName),
    __API_ORIGIN__: JSON.stringify(apiOrigin),
    __CLOUDBASE_ENV_ID__: JSON.stringify(cloudBaseEnvId),
    __CLOUDBASE_SERVICE__: JSON.stringify(cloudBaseService),
    __USE_CLOUDBASE_PRIVATE_ACCESS__: JSON.stringify(useCloudBasePrivateAccess),
    __DEBUG_LOGS__: JSON.stringify(environmentName !== "production")
  },
  copy: {
    patterns: [],
    options: {}
  },
  framework: "react",
  compiler: "webpack5",
  mini: {
    postcss: {
      pxtransform: {
        enable: true,
        config: {}
      },
      cssModules: {
        enable: false,
        config: {
          namingPattern: "module",
          generateScopedName: "[name]__[local]___[hash:base64:5]"
        }
      }
    }
  }
};

module.exports = function mergeConfig(merge) {
  if (process.env.NODE_ENV === "development") {
    return merge({}, config, require("./dev"));
  }
  return merge({}, config, require("./prod"));
};

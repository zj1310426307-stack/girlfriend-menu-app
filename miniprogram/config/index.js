const environmentName = process.env.TARO_APP_ENV_NAME || (process.env.NODE_ENV === "development" ? "development" : "production");
const apiOrigin = (process.env.TARO_APP_API_ORIGIN || "").replace(/\/$/, "");
const productionApiOrigin = "https://girlfriend-menu-api.onrender.com";
if (!apiOrigin) {
  throw new Error(`Missing TARO_APP_API_ORIGIN for ${environmentName} build`);
}
if (["staging", "production"].includes(environmentName) && !apiOrigin.startsWith("https://")) {
  throw new Error(`${environmentName} TARO_APP_API_ORIGIN must use HTTPS`);
}
if (environmentName === "staging" && apiOrigin === productionApiOrigin) {
  throw new Error("Staging TARO_APP_API_ORIGIN must not use the production API");
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
  outputRoot: "dist",
  plugins: [],
  // Reuse Taro's supported Webpack filesystem cache for repeat local builds.
  // Taro tracks this config as a build dependency and invalidates stale output.
  cache: {
    enable: true
  },
  defineConstants: {
    __APP_ENV_NAME__: JSON.stringify(environmentName),
    __API_ORIGIN__: JSON.stringify(apiOrigin),
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

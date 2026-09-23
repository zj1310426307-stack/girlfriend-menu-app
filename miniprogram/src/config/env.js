export const ENV_NAME = __APP_ENV_NAME__;
export const API_ORIGIN = __API_ORIGIN__;
export const API_BASE_URL = `${API_ORIGIN}/api`;
export const WEBSOCKET_ORIGIN = API_ORIGIN.replace(/^http/i, "ws");
export const CLOUDBASE_ENV_ID = __CLOUDBASE_ENV_ID__;
export const CLOUDBASE_SERVICE = __CLOUDBASE_SERVICE__;
export const USE_CLOUDBASE_PRIVATE_ACCESS = __USE_CLOUDBASE_PRIVATE_ACCESS__;
export const DEBUG_LOGS = __DEBUG_LOGS__;

import { F as CONFIG_PATH } from "./entry.js";
import { i as displayPath } from "./utils-PmTbZoD1.js";

//#region src/config/logging.ts
function formatConfigPath(path = CONFIG_PATH) {
	return displayPath(path);
}
function logConfigUpdated(runtime, opts = {}) {
	const path = formatConfigPath(opts.path ?? CONFIG_PATH);
	const suffix = opts.suffix ? ` ${opts.suffix}` : "";
	runtime.log(`Updated ${path}${suffix}`);
}

//#endregion
export { logConfigUpdated as n, formatConfigPath as t };
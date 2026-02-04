import path from "node:path";
import { AuthStorage, AuthStorage as AuthStorage$1, ModelRegistry, ModelRegistry as ModelRegistry$1 } from "@mariozechner/pi-coding-agent";

//#region src/agents/pi-model-discovery.ts
function discoverAuthStorage(agentDir) {
	return new AuthStorage(path.join(agentDir, "auth.json"));
}
function discoverModels(authStorage, agentDir) {
	return new ModelRegistry(authStorage, path.join(agentDir, "models.json"));
}

//#endregion
export { discoverModels as i, ModelRegistry$1 as n, discoverAuthStorage as r, AuthStorage$1 as t };
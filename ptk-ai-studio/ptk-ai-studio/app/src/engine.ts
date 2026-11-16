// Cliente do motor Python (via comandos Tauri -> sidecar JSON-lines).
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
export type Job = { id: number; kind: string; status: string; progress: number; error: string | null; output: string | null };
export const call = <T,>(cmd: string, args: object = {}) => invoke<T>("engine_call", { cmd, args });
export const onJob = (cb: (j: Job) => void) => listen<Job>("engine-job", e => cb(e.payload));

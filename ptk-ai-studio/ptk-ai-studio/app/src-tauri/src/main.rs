// NAO TESTADO: escrito sem acesso a Rust/internet. Espere ajustes na primeira compilacao.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use std::{collections::HashMap, sync::{Arc, Mutex}};
use tauri::{Emitter, Manager, State};
use tauri_plugin_shell::{process::{CommandChild, CommandEvent}, ShellExt};
use tokio::sync::oneshot;

struct Engine { child: Mutex<Option<CommandChild>>, pending: Arc<Mutex<HashMap<u64, oneshot::Sender<serde_json::Value>>>>, next: Mutex<u64> }

#[tauri::command]
async fn engine_call(state: State<'_, Engine>, cmd: String, args: serde_json::Value) -> Result<serde_json::Value, String> {
    let id = { let mut n = state.next.lock().unwrap(); *n += 1; *n };
    let (tx, rx) = oneshot::channel();
    state.pending.lock().unwrap().insert(id, tx);
    let line = serde_json::json!({"id": id, "cmd": cmd, "args": args}).to_string() + "\n";
    state.child.lock().unwrap().as_mut().ok_or("motor nao iniciado")?
        .write(line.as_bytes()).map_err(|e| e.to_string())?;
    let resp = rx.await.map_err(|_| "motor encerrou".to_string())?;
    if resp["ok"].as_bool() == Some(true) { Ok(resp["result"].clone()) }
    else { Err(resp["error"].as_str().unwrap_or("erro").to_string()) }
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_autostart::init(tauri_plugin_autostart::MacosLauncher::LaunchAgent, None))
        .manage(Engine { child: Mutex::new(None), pending: Arc::new(Mutex::new(HashMap::new())), next: Mutex::new(0) })
        .setup(|app| {
            let handle = app.handle().clone();
            let ff = app.path().resource_dir().map_err(|e| e.to_string())?.join("resources").join("ffmpeg");
            let (mut rx, child) = app.shell().sidecar("ptk-engine").map_err(|e| e.to_string())?
                .env("PTK_FFMPEG_DIR", ff.to_string_lossy().to_string()).spawn().map_err(|e| e.to_string())?;
            *app.state::<Engine>().child.lock().unwrap() = Some(child);
            let pending = app.state::<Engine>().pending.clone();
            tauri::async_runtime::spawn(async move {
                while let Some(ev) = rx.recv().await {
                    if let CommandEvent::Stdout(bytes) = ev {
                        if let Ok(v) = serde_json::from_slice::<serde_json::Value>(&bytes) {
                            if v["event"] == "job" { let _ = handle.emit("engine-job", v["job"].clone()); }
                            else if let Some(id) = v["id"].as_u64() {
                                if let Some(tx) = pending.lock().unwrap().remove(&id) { let _ = tx.send(v); }
                            }
                        }
                    }
                }
            });
            // Atalho global Ctrl+Shift+P
            use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};
            let sc = Shortcut::new(Some(Modifiers::CONTROL | Modifiers::SHIFT), Code::KeyP);
            let h2 = app.handle().clone();
            app.global_shortcut().on_shortcut(sc, move |_, _, ev| {
                if ev.state == ShortcutState::Pressed {
                    if let Some(w) = h2.get_webview_window("main") { let _ = w.show(); let _ = w.set_focus(); }
                }
            }).map_err(|e| e.to_string())?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![engine_call])
        .run(tauri::generate_context!())
        .expect("erro ao iniciar PTK AI STUDIO");
}

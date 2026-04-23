use std::sync::{Arc, Mutex};
use tauri::Manager;
use tauri_plugin_shell::process::CommandEvent;
use tauri_plugin_shell::ShellExt;

/// Shared state that holds the port the Python sidecar chose at runtime.
struct BackendPort(Arc<Mutex<Option<u16>>>);

/// Tauri command — the frontend calls this via `invoke('get_backend_port')`
/// and retries until it gets a value (the sidecar may take a second to start).
#[tauri::command]
fn get_backend_port(state: tauri::State<'_, BackendPort>) -> Option<u16> {
    *state.0.lock().unwrap()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let port_state = Arc::new(Mutex::new(None::<u16>));

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(BackendPort(port_state))
        .invoke_handler(tauri::generate_handler![get_backend_port])
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?
            }

            // Spawn sidecar and capture its stdout to learn which port it picked.
            let sidecar = app
                .shell()
                .sidecar("markdown-reader-backend")
                .expect("failed to prepare backend sidecar");
            let (mut rx, _child) = sidecar.spawn().expect("failed to spawn backend sidecar");

            // Clone the port store so the async task can write into it.
            let port_arc = app.state::<BackendPort>().0.clone();

            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    if let CommandEvent::Stdout(bytes) = event {
                        let line = String::from_utf8_lossy(&bytes);
                        // Backend prints "BACKEND_PORT=<n>" as its very first line.
                        if let Some(rest) = line.trim().strip_prefix("BACKEND_PORT=") {
                            if let Ok(port) = rest.parse::<u16>() {
                                *port_arc.lock().unwrap() = Some(port);
                                break; // port received — no need to keep reading
                            }
                        }
                    }
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

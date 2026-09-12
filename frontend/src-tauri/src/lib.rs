use std::process::Command as StdCommand;
use std::sync::{Arc, Mutex};
use tauri::{Emitter, Manager};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

/// Shared state that holds the port the Python sidecar chose at runtime.
struct BackendPort(Arc<Mutex<Option<u16>>>);
struct BackendChild(Mutex<Option<CommandChild>>);
struct PendingOpenFiles(Mutex<Vec<String>>);

/// Tauri command — the frontend calls this via `invoke('get_backend_port')`
/// and retries until it gets a value (the sidecar may take a second to start).
#[tauri::command]
fn get_backend_port(state: tauri::State<'_, BackendPort>) -> Option<u16> {
    *state.0.lock().unwrap()
}

#[tauri::command]
fn take_pending_open_files(state: tauri::State<'_, PendingOpenFiles>) -> Vec<String> {
    let mut pending = state.0.lock().unwrap();
    std::mem::take(&mut *pending)
}

fn terminate_process_tree(pid: u32) {
    if let Ok(output) = StdCommand::new("pgrep")
        .arg("-P")
        .arg(pid.to_string())
        .output()
    {
        let stdout = String::from_utf8_lossy(&output.stdout);
        for child_pid in stdout
            .lines()
            .filter_map(|line| line.trim().parse::<u32>().ok())
        {
            terminate_process_tree(child_pid);
        }
    }

    let _ = StdCommand::new("kill")
        .arg("-TERM")
        .arg(pid.to_string())
        .status();
}

fn stop_backend(app: &tauri::AppHandle) {
    if let Some(child) = app.state::<BackendChild>().0.lock().unwrap().take() {
        terminate_process_tree(child.pid());
        let _ = child.kill();
    }
}

fn normalize_windows_path(arg: &str) -> Option<String> {
    let trimmed = arg.trim_matches('"').trim();

    if trimmed.starts_with('-') || trimmed.is_empty() {
        return None;
    }

    let path = std::path::Path::new(trimmed);
    let lower = trimmed.to_lowercase();

    if (lower.ends_with(".md") || lower.ends_with(".markdown")) && path.exists() {
        if let Ok(canonical) = path.canonicalize() {
            let mut path_str = canonical.to_string_lossy().to_string();
            if path_str.starts_with(r"\\?\") {
                path_str = path_str[4..].to_string();
            }
            Some(path_str.replace('\\', "/"))
        } else {
            Some(trimmed.replace('\\', "/"))
        }
    } else {
        None
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let port_state = Arc::new(Mutex::new(None::<u16>));

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, argv, _cwd| {
            let mut paths = Vec::new();
            for arg in argv.into_iter().skip(1) {
                if let Some(valid_path) = normalize_windows_path(&arg) {
                    paths.push(valid_path);
                }
            }
            if !paths.is_empty() {
                app.state::<PendingOpenFiles>()
                    .0
                    .lock()
                    .unwrap()
                    .extend(paths.clone());

                let _ = app.emit("open-file-paths", paths);

                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.unminimize();
                    let _ = window.set_focus();
                }
            }
        }))
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .manage(BackendPort(port_state))
        .manage(BackendChild(Mutex::new(None)))
        .manage(PendingOpenFiles(Mutex::new(Vec::new())))
        .invoke_handler(tauri::generate_handler![
            get_backend_port,
            take_pending_open_files
        ])
        .on_window_event(|window, event| {
            if matches!(event, tauri::WindowEvent::CloseRequested { .. }) {
                stop_backend(window.app_handle());
                window.app_handle().exit(0);
            }
        })
        .setup(|app| {
            let args: Vec<String> = std::env::args().collect();
            let mut initial_files = Vec::new();
            for arg in args.into_iter().skip(1) {
                if let Some(valid_path) = normalize_windows_path(&arg) {
                    initial_files.push(valid_path);
                }
            }

            if !initial_files.is_empty() {
                app.state::<PendingOpenFiles>()
                    .0
                    .lock()
                    .unwrap()
                    .extend(initial_files);
            }

            if cfg!(debug_assertions) {
                let backend_port = std::env::var("MARKDOWN_READER_BACKEND_PORT")
                    .ok()
                    .and_then(|value| value.parse::<u16>().ok())
                    .unwrap_or(8000);
                *app.state::<BackendPort>().0.lock().unwrap() = Some(backend_port);
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;

                return Ok(());
            }

            // In packaged mode, spawn sidecar and capture its stdout to learn which port it picked.
            let sidecar = app
                .shell()
                .sidecar("markdown-reader-backend")
                .map(|command| {
                    command.env("MARKDOWN_READER_PARENT_PID", std::process::id().to_string())
                })
                .expect("failed to prepare backend sidecar");
            let (mut rx, child) = sidecar.spawn().expect("failed to spawn backend sidecar");
            *app.state::<BackendChild>().0.lock().unwrap() = Some(child);

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
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|app_handle, event| match event {
        #[cfg(target_os = "macos")]
        tauri::RunEvent::Opened { urls } => {
            let paths: Vec<String> = urls
                .into_iter()
                .filter_map(|url| url.to_file_path().ok())
                .map(|path| path.to_string_lossy().to_string())
                .collect();

            if !paths.is_empty() {
                app_handle
                    .state::<PendingOpenFiles>()
                    .0
                    .lock()
                    .unwrap()
                    .extend(paths.clone());
                let _ = app_handle.emit("open-file-paths", paths);
            }
        }
        tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit => {
            stop_backend(app_handle);
        }
        _ => {}
    });
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs::File;
    use tempfile::tempdir;

    #[test]
    fn test_normalize_windows_path_valid_md() {
        let dir = tempdir().unwrap();
        let file_path = dir.path().join("test_note.md");
        File::create(&file_path).unwrap();

        let path_str = file_path.to_string_lossy().to_string();

        let quoted_path = format!("\"{}\"", path_str);

        let result = normalize_windows_path(&quoted_path);
        assert!(result.is_some());
        assert!(result.unwrap().ends_with("test_note.md"));
    }

    #[test]
    fn test_normalize_windows_path_ignore_cli_flags() {
        assert_eq!(normalize_windows_path("--config"), None);
        assert_eq!(normalize_windows_path("-v"), None);
        assert_eq!(normalize_windows_path(""), None);
    }

    #[test]
    fn test_normalize_windows_path_non_md_file() {
        let dir = tempdir().unwrap();
        let file_path = dir.path().join("image.png");
        File::create(&file_path).unwrap();

        let path_str = file_path.to_string_lossy().to_string();
        assert_eq!(normalize_windows_path(&path_str), None);
    }

    #[test]
    fn test_normalize_windows_path_slashes_conversion() {
        let dir = tempdir().unwrap();
        let file_path = dir.path().join("nested_file.markdown");
        File::create(&file_path).unwrap();

        let path_str = file_path.to_string_lossy().to_string(); // В Windows содержит '\'
        let result = normalize_windows_path(&path_str).unwrap();

        // Убеждаемся, что обратные слэши конвертированы в прямой '/' для JS
        assert!(!result.contains('\\'));
        assert!(result.contains('/'));
    }
}

const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

// Get path to bundled backend executable
function getBackendPath() {
    if (app.isPackaged) {
        // Production: executable is in Resources folder
        return path.join(process.resourcesPath, 'mekabox-backend');
    } else {
        // Development: executable is in resources folder
        return path.join(__dirname, 'resources', 'mekabox-backend');
    }
}

let mainWindow;

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 800,
        height: 600,
        minWidth: 700,
        minHeight: 620,
        backgroundColor: '#0a0a0f',
        frame: false,
        titleBarStyle: 'hidden',
        trafficLightPosition: { x: -100, y: -100 },
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false
        }
    });

    mainWindow.loadFile('index.html');
}

app.whenReady().then(() => {
    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

// ============================================================================
// IPC Handlers - Bridge between renderer and bundled backend
// ============================================================================

// Open file dialog for XML selection
ipcMain.handle('select-xml-file', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
        properties: ['openFile'],
        filters: [
            { name: 'XML Files', extensions: ['xml'] },
            { name: 'All Files', extensions: ['*'] }
        ]
    });

    if (result.canceled) {
        return null;
    }
    return result.filePaths[0];
});

// Open folder dialog for output selection
ipcMain.handle('select-output-folder', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
        properties: ['openDirectory', 'createDirectory']
    });

    if (result.canceled) {
        return null;
    }
    return result.filePaths[0];
});

// Get playlists from XML file
ipcMain.handle('get-playlists', async (event, xmlPath) => {
    return new Promise((resolve) => {
        const backendPath = getBackendPath();
        const args = JSON.stringify({ xml_path: xmlPath });

        const backend = spawn(backendPath, ['get_playlists', args]);
        let output = '';
        let errorOutput = '';

        backend.stdout.on('data', (data) => {
            output += data.toString();
        });

        backend.stderr.on('data', (data) => {
            errorOutput += data.toString();
        });

        backend.on('close', (code) => {
            try {
                const result = JSON.parse(output.trim());
                resolve(result);
            } catch (e) {
                resolve({ success: false, error: errorOutput || 'Failed to parse backend output' });
            }
        });

        backend.on('error', (err) => {
            resolve({ success: false, error: `Failed to start backend: ${err.message}` });
        });
    });
});

// Get track count for a playlist
ipcMain.handle('get-track-count', async (event, xmlPath, playlistName) => {
    return new Promise((resolve) => {
        const backendPath = getBackendPath();
        const args = JSON.stringify({ xml_path: xmlPath, playlist_name: playlistName });

        const backend = spawn(backendPath, ['get_track_count', args]);
        let output = '';

        backend.stdout.on('data', (data) => {
            output += data.toString();
        });

        backend.on('close', (code) => {
            try {
                const result = JSON.parse(output.trim());
                resolve(result);
            } catch (e) {
                resolve({ success: false, error: 'Failed to get track count' });
            }
        });

        backend.on('error', (err) => {
            resolve({ success: false, error: `Failed to start backend: ${err.message}` });
        });
    });
});

// Export playlist - streams progress back to renderer
ipcMain.handle('export-playlist', async (event, options) => {
    const { xmlPath, playlistName, outputFolder, mode } = options;

    return new Promise((resolve) => {
        const backendPath = getBackendPath();
        const args = JSON.stringify({
            xml_path: xmlPath,
            playlist_name: playlistName,
            output_folder: outputFolder,
            mode: mode
        });

        const backend = spawn(backendPath, ['export', args]);
        let finalResult = null;

        backend.stdout.on('data', (data) => {
            const lines = data.toString().split('\n').filter(l => l.trim());
            for (const line of lines) {
                try {
                    const msg = JSON.parse(line);
                    if (msg.type === 'progress') {
                        mainWindow.webContents.send('export-progress', msg);
                    } else if (msg.type === 'complete' || msg.type === 'error') {
                        finalResult = msg;
                    }
                } catch (e) {
                    // Ignore non-JSON output
                }
            }
        });

        backend.stderr.on('data', (data) => {
            console.error('Backend stderr:', data.toString());
        });

        backend.on('close', (code) => {
            if (finalResult) {
                resolve(finalResult);
            } else {
                resolve({ success: false, error: 'Export process ended unexpectedly' });
            }
        });

        backend.on('error', (err) => {
            resolve({ success: false, error: `Failed to start backend: ${err.message}` });
        });
    });
});

// Open folder in Finder/Explorer
ipcMain.handle('open-folder', async (event, folderPath) => {
    const { shell } = require('electron');
    shell.openPath(folderPath);
});

// Window controls
ipcMain.handle('window-minimize', async () => {
    mainWindow.minimize();
});

ipcMain.handle('window-close', async () => {
    mainWindow.close();
});

// Expand ~ to home directory
ipcMain.handle('expand-path', async (event, filePath) => {
    const os = require('os');
    if (filePath.startsWith('~')) {
        return filePath.replace('~', os.homedir());
    }
    return filePath;
});

// Preferences storage
const PREFS_PATH = path.join(app.getPath('userData'), 'preferences.json');

ipcMain.handle('get-preferences', async () => {
    try {
        if (fs.existsSync(PREFS_PATH)) {
            const data = fs.readFileSync(PREFS_PATH, 'utf8');
            return JSON.parse(data);
        }
    } catch (e) {
        console.error('Error reading preferences:', e);
    }
    return {};
});

ipcMain.handle('set-preferences', async (event, prefs) => {
    try {
        fs.writeFileSync(PREFS_PATH, JSON.stringify(prefs, null, 2));
        return true;
    } catch (e) {
        console.error('Error saving preferences:', e);
        return false;
    }
});

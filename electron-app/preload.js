const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods to renderer process
contextBridge.exposeInMainWorld('api', {
    // File dialogs
    selectXmlFile: () => ipcRenderer.invoke('select-xml-file'),
    selectOutputFolder: () => ipcRenderer.invoke('select-output-folder'),

    // Python backend calls
    getPlaylists: (xmlPath) => ipcRenderer.invoke('get-playlists', xmlPath),
    getTrackCount: (xmlPath, playlistName) => ipcRenderer.invoke('get-track-count', xmlPath, playlistName),
    exportPlaylist: (options) => ipcRenderer.invoke('export-playlist', options),

    // Progress listener
    onExportProgress: (callback) => {
        ipcRenderer.on('export-progress', (event, data) => callback(data));
    },

    // Utility
    openFolder: (folderPath) => ipcRenderer.invoke('open-folder', folderPath),
    expandPath: (filePath) => ipcRenderer.invoke('expand-path', filePath),

    // Preferences
    getPreferences: () => ipcRenderer.invoke('get-preferences'),
    setPreferences: (prefs) => ipcRenderer.invoke('set-preferences', prefs),

    // Window controls
    windowMinimize: () => ipcRenderer.invoke('window-minimize'),
    windowClose: () => ipcRenderer.invoke('window-close')
});

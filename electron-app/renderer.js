// ============================================================================
// MekaBox Renderer - Frontend Logic
// ============================================================================

// State
let state = {
    xmlPath: null,
    lastUsedPath: null,
    playlists: [],
    selectedPlaylist: null,
    trackCount: 0,
    exportMode: 'full',
    outputFolder: null,
    isExporting: false
};

// DOM Elements
const screens = {
    welcome: document.getElementById('screen-welcome'),
    import: document.getElementById('screen-import'),
    playlist: document.getElementById('screen-playlist'),
    options: document.getElementById('screen-options'),
    progress: document.getElementById('screen-progress'),
    complete: document.getElementById('screen-complete')
};

const modal = document.getElementById('modal-tutorial');

// ============================================================================
// Screen Navigation
// ============================================================================

function showScreen(screenName) {
    Object.values(screens).forEach(screen => screen.classList.remove('active'));
    screens[screenName].classList.add('active');

    // Toggle header visibility - hide on welcome screen, show on all others
    const header = document.querySelector('.frame-header');
    const frameContent = document.querySelector('.frame-content');

    if (screenName === 'welcome') {
        header.classList.add('hidden');
        frameContent.classList.add('welcome-mode');
    } else {
        header.classList.remove('hidden');
        frameContent.classList.remove('welcome-mode');
    }
}

function showModal() {
    modal.classList.add('active');
}

function hideModal() {
    modal.classList.remove('active');
}

// ============================================================================
// Splash Screen
// ============================================================================

function initSplashScreen() {
    const splash = document.getElementById('splash-screen');
    const video = document.getElementById('splash-video');
    const cyberFrame = document.querySelector('.cyber-frame');

    if (!splash || !video) return;

    // Hide buttons and logo during splash
    cyberFrame.classList.add('splash-active');

    // Play the video
    video.play().catch(err => {
        // If video fails to play, just skip the splash
        console.log('Splash video failed to play:', err);
        splash.classList.add('hidden');
        cyberFrame.classList.remove('splash-active');
    });

    // When video ends, freeze on last frame then glow out
    video.addEventListener('ended', () => {
        // Pause on last frame (it's already paused at end)
        // Wait a brief moment, then glow out
        setTimeout(() => {
            splash.classList.add('glow-out');
            // Show buttons and logo as splash fades
            cyberFrame.classList.remove('splash-active');
            // Remove from DOM after glow completes
            setTimeout(() => {
                splash.classList.add('hidden');
            }, 600);
        }, 300);
    });
}

// ============================================================================
// Initialization
// ============================================================================

async function init() {
    // Load preferences
    const prefs = await window.api.getPreferences();
    if (prefs.lastUsedPath) {
        state.lastUsedPath = prefs.lastUsedPath;
        updateLastUsedSection();
    }
    if (prefs.outputFolder) {
        state.outputFolder = prefs.outputFolder;
    }

    // Set default output folder
    if (!state.outputFolder) {
        // Default to Desktop/rekordbox-exports
        state.outputFolder = '~/Desktop/rekordbox-exports';
    }

    // Hide header on welcome screen (initial state)
    const header = document.querySelector('.frame-header');
    const frameContent = document.querySelector('.frame-content');
    header.classList.add('hidden');
    frameContent.classList.add('welcome-mode');

    setupEventListeners();
}

function setupEventListeners() {
    // Window controls
    document.querySelector('.window-btn-minimize').addEventListener('click', () => window.api.windowMinimize());
    document.querySelector('.window-btn-close').addEventListener('click', () => window.api.windowClose());

    // Welcome screen
    document.getElementById('btn-tutorial').addEventListener('click', showModal);
    document.getElementById('btn-proceed').addEventListener('click', () => showScreen('import'));

    // Tutorial modal
    document.getElementById('btn-close-tutorial').addEventListener('click', hideModal);
    document.getElementById('btn-tutorial-proceed').addEventListener('click', () => {
        hideModal();
        showScreen('import');
    });
    document.getElementById('btn-view-tutorial').addEventListener('click', showModal);

    // Import screen
    document.getElementById('btn-back-import').addEventListener('click', () => showScreen('welcome'));
    const dropZone = document.getElementById('drop-zone');
    dropZone.addEventListener('click', selectXmlFile);
    dropZone.addEventListener('dragover', handleDragOver);
    dropZone.addEventListener('dragleave', handleDragLeave);
    dropZone.addEventListener('drop', handleDrop);

    document.getElementById('btn-clear-last').addEventListener('click', clearLastUsed);
    document.getElementById('btn-use-last').addEventListener('click', useLastPath);
    document.getElementById('btn-continue-import').addEventListener('click', continueToPlaylist);

    // Playlist screen
    document.getElementById('btn-back-playlist').addEventListener('click', () => showScreen('import'));
    document.getElementById('playlist-search').addEventListener('input', filterPlaylists);
    document.getElementById('btn-continue-playlist').addEventListener('click', continueToOptions);

    // Options screen
    document.getElementById('btn-back-options').addEventListener('click', () => showScreen('playlist'));
    document.querySelectorAll('input[name="export-mode"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            state.exportMode = e.target.value;
            updateOptionCards();
        });
    });
    document.getElementById('btn-browse-output').addEventListener('click', selectOutputFolder);
    document.getElementById('btn-export').addEventListener('click', startExport);

    // Progress screen
    document.getElementById('btn-cancel').addEventListener('click', cancelExport);

    // Complete screen
    document.getElementById('btn-open-folder').addEventListener('click', openOutputFolder);
    document.getElementById('btn-export-another').addEventListener('click', () => showScreen('playlist'));
    document.getElementById('btn-show-failed').addEventListener('click', toggleFailedList);

    // Progress listener
    window.api.onExportProgress(handleExportProgress);
}

// ============================================================================
// Import Screen Logic
// ============================================================================

async function selectXmlFile() {
    const path = await window.api.selectXmlFile();
    if (path) {
        setXmlPath(path);
    }
}

function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('drop-zone').classList.add('drag-over');
}

function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('drop-zone').classList.remove('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('drop-zone').classList.remove('drag-over');

    const files = e.dataTransfer.files;
    if (files.length > 0) {
        const file = files[0];
        if (file.name.endsWith('.xml')) {
            setXmlPath(file.path);
        }
    }
}

function setXmlPath(path) {
    state.xmlPath = path;
    document.getElementById('selected-file-section').style.display = 'block';
    document.getElementById('selected-file-path').textContent = shortenPath(path);
    document.getElementById('btn-continue-import').disabled = false;
}

function updateLastUsedSection() {
    if (state.lastUsedPath) {
        document.getElementById('last-used-section').style.display = 'block';
        document.getElementById('last-used-path').textContent = shortenPath(state.lastUsedPath);
    } else {
        document.getElementById('last-used-section').style.display = 'none';
    }
}

function clearLastUsed() {
    state.lastUsedPath = null;
    updateLastUsedSection();
    window.api.setPreferences({ lastUsedPath: null });
}

function useLastPath() {
    if (state.lastUsedPath) {
        setXmlPath(state.lastUsedPath);
    }
}

function shortenPath(path) {
    // Replace home directory with ~
    const home = path.split('/').slice(0, 3).join('/');
    if (path.startsWith('/Users/')) {
        return path.replace(home, '~');
    }
    return path;
}

async function continueToPlaylist() {
    if (!state.xmlPath) return;

    const btn = document.getElementById('btn-continue-import');
    btn.classList.add('loading');
    btn.textContent = 'Loading...';

    try {
        // Save as last used
        state.lastUsedPath = state.xmlPath;
        await window.api.setPreferences({ lastUsedPath: state.xmlPath, outputFolder: state.outputFolder });

        // Get playlists
        const result = await window.api.getPlaylists(state.xmlPath);

        if (result.success) {
            state.playlists = result.playlists.sort();
            renderPlaylistList();
            document.getElementById('playlist-count').textContent = `Found ${state.playlists.length} playlists`;
            showScreen('playlist');
        } else {
            alert('Error loading playlists: ' + result.error);
        }
    } finally {
        btn.classList.remove('loading');
        btn.textContent = 'Continue';
    }
}

// ============================================================================
// Playlist Screen Logic
// ============================================================================

function renderPlaylistList() {
    const container = document.getElementById('playlist-list');
    const searchTerm = document.getElementById('playlist-search').value.toLowerCase();

    const filtered = state.playlists.filter(name =>
        name.toLowerCase().includes(searchTerm)
    );

    container.innerHTML = filtered.map(name => `
        <div class="playlist-item ${state.selectedPlaylist === name ? 'selected' : ''}"
             data-name="${escapeHtml(name)}">
            <div class="playlist-radio"></div>
            <span class="playlist-name">${escapeHtml(name)}</span>
        </div>
    `).join('');

    // Add click handlers
    container.querySelectorAll('.playlist-item').forEach(item => {
        item.addEventListener('click', () => selectPlaylist(item.dataset.name));
    });
}

function selectPlaylist(name) {
    state.selectedPlaylist = name;
    renderPlaylistList();
    document.getElementById('btn-continue-playlist').disabled = false;
}

function filterPlaylists() {
    renderPlaylistList();
}

async function continueToOptions() {
    if (!state.selectedPlaylist) return;

    const btn = document.getElementById('btn-continue-playlist');
    btn.classList.add('loading');
    btn.textContent = 'Loading...';

    try {
        // Get track count
        const result = await window.api.getTrackCount(state.xmlPath, state.selectedPlaylist);
        state.trackCount = result.success ? result.count : 0;

        // Update display
        const simpleName = state.selectedPlaylist.split('/').pop();
        document.getElementById('selected-playlist-info').textContent =
            `Playlist: ${simpleName} (${state.trackCount} tracks)`;

        // Set output folder
        document.getElementById('output-folder').value = state.outputFolder || '~/Desktop/rekordbox-exports';

        updateOptionCards();
        showScreen('options');
    } finally {
        btn.classList.remove('loading');
        btn.textContent = 'Continue';
    }
}

function updateOptionCards() {
    document.querySelectorAll('.option-card').forEach(card => {
        const radio = card.querySelector('input[type="radio"]');
        card.classList.toggle('selected', radio.checked);
    });
}

// ============================================================================
// Options Screen Logic
// ============================================================================

async function selectOutputFolder() {
    const path = await window.api.selectOutputFolder();
    if (path) {
        state.outputFolder = path;
        document.getElementById('output-folder').value = shortenPath(path);
        await window.api.setPreferences({ lastUsedPath: state.lastUsedPath, outputFolder: path });
    }
}

// ============================================================================
// Export Logic
// ============================================================================

async function startExport() {
    if (state.isExporting) return;
    state.isExporting = true;

    // Show loading on export button
    const btn = document.getElementById('btn-export');
    btn.classList.add('loading');
    btn.textContent = 'Starting...';

    // Update progress screen
    const simpleName = state.selectedPlaylist.split('/').pop();
    document.getElementById('progress-playlist-name').textContent = `Playlist: ${simpleName}`;
    document.getElementById('progress-fill').style.width = '0%';
    document.getElementById('progress-percent').textContent = '0%';
    document.getElementById('progress-status').textContent = 'Preparing...';
    document.getElementById('progress-current').textContent = '';

    // Small delay to show loading state before transitioning
    await new Promise(r => setTimeout(r, 100));
    btn.classList.remove('loading');
    btn.textContent = 'Export';

    showScreen('progress');

    // Expand ~ to home directory for the path
    let outputFolder = await window.api.expandPath(state.outputFolder);

    // Start export
    const result = await window.api.exportPlaylist({
        xmlPath: state.xmlPath,
        playlistName: state.selectedPlaylist,
        outputFolder: outputFolder,
        mode: state.exportMode
    });

    state.isExporting = false;
    showComplete(result);
}

function handleExportProgress(data) {
    const percent = Math.round((data.current / data.total) * 100);
    document.getElementById('progress-fill').style.width = `${percent}%`;
    document.getElementById('progress-percent').textContent = `${percent}%`;
    document.getElementById('progress-status').textContent = `Copying: ${data.current} of ${data.total} tracks`;
    document.getElementById('progress-current').textContent = data.track;
}

function cancelExport() {
    // TODO: Implement cancellation (would need to send signal to Python process)
    state.isExporting = false;
    showScreen('options');
}

function showComplete(result) {
    const simpleName = state.selectedPlaylist.split('/').pop();

    if (result.success) {
        const hasFailures = result.failed > 0;

        document.getElementById('complete-icon').textContent = hasFailures ? '\u26A0' : '\u2713';
        document.getElementById('complete-icon').className = 'complete-icon' + (hasFailures ? ' warning' : '');
        document.getElementById('complete-title').textContent = hasFailures ? 'EXPORT COMPLETE' : 'COMPLETE';
        document.getElementById('complete-playlist-name').textContent =
            `${hasFailures ? 'Exported' : 'Successfully exported'}: ${simpleName}`;

        document.getElementById('stat-success').textContent = result.successful;
        document.getElementById('stat-failed').textContent = result.failed;
        document.getElementById('output-path').textContent = shortenPath(result.output_folder);

        // Show failed section if there are failures
        const failedSection = document.getElementById('failed-section');
        if (hasFailures && result.failed_tracks) {
            failedSection.style.display = 'block';
            const failedList = document.getElementById('failed-list');
            failedList.innerHTML = result.failed_tracks.map(t =>
                `<p>${escapeHtml(t.name)}: ${escapeHtml(t.reason)}</p>`
            ).join('');
        } else {
            failedSection.style.display = 'none';
        }

        // Store output folder for "Open Folder" button
        state.lastOutputFolder = result.output_folder;

    } else {
        document.getElementById('complete-icon').textContent = '\u2717';
        document.getElementById('complete-icon').className = 'complete-icon warning';
        document.getElementById('complete-title').textContent = 'EXPORT FAILED';
        document.getElementById('complete-playlist-name').textContent = result.error || 'Unknown error';
        document.getElementById('stat-success').textContent = '0';
        document.getElementById('stat-failed').textContent = '0';
        document.getElementById('output-path').textContent = '';
        document.getElementById('failed-section').style.display = 'none';
    }

    showScreen('complete');
}

function openOutputFolder() {
    if (state.lastOutputFolder) {
        window.api.openFolder(state.lastOutputFolder);
    }
}

function toggleFailedList() {
    const list = document.getElementById('failed-list');
    const btn = document.getElementById('btn-show-failed');
    if (list.style.display === 'none') {
        list.style.display = 'block';
        btn.innerHTML = 'Hide failed tracks &#9650;';
    } else {
        list.style.display = 'none';
        btn.innerHTML = 'Show failed tracks &#9660;';
    }
}

// ============================================================================
// Utilities
// ============================================================================

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================================
// Initialize
// ============================================================================

initSplashScreen();
init();

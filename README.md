# MekaBox

**Share Rekordbox playlists with all your cues and beat grids preserved!**

MekaBox exports Rekordbox playlists as shareable packages that include all your hot cues, cue points, beat grids, and metadata.

---

## Download

### Mac (Apple Silicon)
Download the latest release from the [Releases page](../../releases):
- **MekaBox-x.x.x-mac-arm64.dmg** - Disk image installer

**Installation:**
1. Download the DMG file
2. Open it and drag MekaBox to your Applications folder
3. Double-click to run

> **Note:** On first launch, you may need to right-click > Open to bypass Gatekeeper.

### Windows / Linux / Intel Mac
Use the Python CLI (see [Command Line Usage](#command-line-usage) below).

**Quick start:**
```bash
# Requires Python 3.6+
python3 rekordbox_playlist_copier.py
```

---

## How to Use

### Step 1: Export Your Rekordbox Collection

Before using MekaBox, export your Rekordbox collection to XML:

1. Open **Rekordbox**
2. Go to **File > Export Collection in XML format**
3. Save the file somewhere easy to find

### Step 2: Open MekaBox

1. Launch MekaBox
2. Drag & drop your XML file (or click to browse)
3. Select the playlist you want to export
4. Choose your export mode:
   - **Copy tracks only** - Just the audio files
   - **Copy tracks + Generate XML** - Full shareable package with all metadata
5. Pick an output folder and click Export

### Step 3: Share Your Playlist

When you export with "Copy tracks + Generate XML":
1. Zip the entire output folder
2. Send it to your friend
3. They'll find a README.txt with instructions inside

---

## For Recipients

If someone sent you a MekaBox playlist:

1. Unzip the folder
2. **Run the Setup script first:**
   - Mac: Double-click `Setup (Mac).command`
   - Windows: Double-click `Setup (Windows).bat`
3. Import into Rekordbox:
   - Go to **Preferences > Advanced > Database**
   - Under "rekordbox xml", click **Browse** and select the `.xml` file
   - The playlist appears under "rekordbox xml" in your sidebar
   - Right-click the playlist > **Import To Collection**

> **Important:** Always run the Setup script before importing. It updates the file paths for your computer.

---

## Command Line Usage

MekaBox includes a Python CLI script that works on **Windows, Mac, and Linux**.

### Requirements
- Python 3.6+ ([Download Python](https://www.python.org/downloads/))

### Running the CLI

**Mac/Linux:**
```bash
python3 rekordbox_playlist_copier.py
```

**Windows:**
```bash
python rekordbox_playlist_copier.py
```

The script will interactively ask for:
1. Path to your Rekordbox XML file
2. Which playlist to export
3. Export mode (copy only or full package)
4. Output folder location

### Export Modes

**Mode 1: Copy Tracks Only**
```
PlaylistName/
├── 001 - Artist - Track.mp3
├── 002 - Artist - Track.mp3
└── ...
```

**Mode 2: Copy Tracks + Generate XML**
```
PlaylistName/
├── PlaylistName_tracks/        # All audio files
├── PlaylistName.xml            # Rekordbox XML with metadata
├── Setup (Mac).command         # Setup script for Mac
├── Setup (Windows).bat         # Setup script for Windows
└── README.txt                  # Instructions for recipient
```

### Tips
- Drag and drop your XML file into the terminal to paste the path
- Type `quit` at any prompt to exit
- Press Enter at the output folder prompt to use Desktop

---

## Building from Source

### Requirements
- Node.js 18+
- Python 3.6+
- PyInstaller (`pip install pyinstaller`)

### Build Steps

```bash
# Clone the repo
git clone https://github.com/jaredb650/MekaBox.git
cd MekaBox

# Run the build script
chmod +x build.sh
./build.sh mac
```

The built app will be in `electron-app/dist/`.

---

## Troubleshooting

### "File not found" error
- Make sure the XML file exists at the specified path
- Try dragging and dropping the file instead of typing

### "Playlist not found" error
- Use the exact name shown, including `ROOT/` prefix if present
- Names are case-sensitive

### App won't open on Mac
- Right-click the app > Open (bypasses Gatekeeper on first launch)

### Recipient can't import the XML
- Make sure they ran the Setup script first
- The entire folder must stay together (don't move just the XML)

---

## License

MIT

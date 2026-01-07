"""
MekaBox Core - Shared logic for Rekordbox playlist export

This module contains all the core functionality for:
- Parsing Rekordbox XML files
- Extracting playlist and track information
- Generating shareable playlist packages with metadata
- Creating setup scripts for recipients

Used by both the CLI (rekordbox_playlist_copier.py) and GUI (mekabox_app.py)
"""

import os
import shutil
import stat
from pathlib import Path
from urllib.parse import quote, unquote
from xml.etree import ElementTree as ET


def copy_element(elem):
    """
    Deep copy an ElementTree Element including all children and attributes.
    Python's copy.deepcopy() doesn't work correctly with ElementTree elements.
    """
    new_elem = ET.Element(elem.tag, elem.attrib)
    new_elem.text = elem.text
    new_elem.tail = elem.tail
    for child in elem:
        new_elem.append(copy_element(child))
    return new_elem


# =============================================================================
# Path Encoding/Decoding
# =============================================================================

def decode_rekordbox_path(location):
    """
    Decode Rekordbox file location to actual file path.
    Rekordbox stores paths as file:// URLs that need to be decoded.
    """
    # Remove 'file://localhost' or 'file://' prefix
    if location.startswith('file://localhost'):
        path = location[16:]
    elif location.startswith('file://'):
        path = location[7:]
    else:
        path = location

    # URL decode the path
    path = unquote(path)

    return path


def encode_rekordbox_path(path):
    """
    Encode a file path to Rekordbox file:// URL format.
    """
    # URL encode the path, but keep forward slashes
    encoded = quote(str(path), safe='/')
    return f"file://localhost{encoded}"


def sanitize_filename(name):
    """Remove or replace characters that are invalid in filenames."""
    return "".join(c for c in name if c.isalnum() or c in (' ', '-', '_', '.')).strip()


def get_unique_folder_path(base_folder, folder_name):
    """
    Get a unique folder path, handling case-insensitive filesystem collisions.

    On macOS/Windows, 'Freeform' and 'freeform' are the same folder.
    This function detects when a folder exists with different casing and
    appends a suffix to make the new folder name unique.

    Args:
        base_folder: Parent directory path
        folder_name: Desired folder name

    Returns:
        Path object for a unique folder location
    """
    base_path = Path(base_folder)
    target_path = base_path / folder_name

    # If the exact path doesn't exist, check for case-insensitive collision
    if not target_path.exists():
        # Check if any existing folder matches case-insensitively
        try:
            existing_folders = [f.name for f in base_path.iterdir() if f.is_dir()]
            for existing in existing_folders:
                if existing.lower() == folder_name.lower() and existing != folder_name:
                    # Case collision detected - need to make unique
                    break
            else:
                # No collision, use the original name
                return target_path
        except FileNotFoundError:
            # Parent folder doesn't exist yet, no collision possible
            return target_path

    # Folder exists or collision detected - find a unique name
    counter = 2
    while True:
        unique_name = f"{folder_name}_{counter}"
        unique_path = base_path / unique_name

        # Check both exact match and case-insensitive collision
        if not unique_path.exists():
            try:
                existing_folders = [f.name.lower() for f in base_path.iterdir() if f.is_dir()]
                if unique_name.lower() not in existing_folders:
                    return unique_path
            except FileNotFoundError:
                return unique_path

        counter += 1
        if counter > 100:  # Safety limit
            raise RuntimeError(f"Could not find unique folder name for {folder_name}")


# =============================================================================
# XML Parsing
# =============================================================================

def get_playlists(xml_file):
    """
    Parse XML and return all playlist names.

    Returns:
        dict: Mapping of playlist full names to their XML nodes
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()

    playlists = {}
    playlists_node = root.find('.//PLAYLISTS')

    if playlists_node is None:
        return playlists

    def parse_playlist_node(node, prefix=""):
        """Recursively parse playlist nodes."""
        for child in node:
            if child.tag == 'NODE':
                node_type = child.get('Type')
                name = child.get('Name')

                if node_type == '0':  # Folder
                    # Recursively parse folder contents
                    parse_playlist_node(child, prefix=f"{prefix}{name}/")
                elif node_type == '1':  # Playlist
                    full_name = f"{prefix}{name}"
                    playlists[full_name] = child

    parse_playlist_node(playlists_node)
    return playlists


def get_full_track_elements(xml_file, playlist_name):
    """
    Extract complete TRACK XML elements for a playlist, preserving all metadata.

    Returns:
        list: List of tuples (track_element, track_info_dict)
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # Build a dictionary of all tracks by TrackID
    all_tracks = {}
    collection = root.find('COLLECTION')
    if collection is not None:
        for track in collection.findall('TRACK'):
            track_id = track.get('TrackID')
            all_tracks[track_id] = track

    # Get the playlist
    playlists = get_playlists(xml_file)

    if playlist_name not in playlists:
        return []

    playlist_node = playlists[playlist_name]
    result = []

    for track_node in playlist_node.findall('TRACK'):
        key = track_node.get('Key')
        if key in all_tracks:
            track_elem = all_tracks[key]
            track_info = {
                'location': decode_rekordbox_path(track_elem.get('Location', '')),
                'name': track_elem.get('Name', 'Unknown'),
                'artist': track_elem.get('Artist', 'Unknown'),
                'track_id': key
            }
            # Deep copy the element so we can modify it without affecting the original
            # Note: Must use copy_element() because copy.deepcopy() doesn't preserve child elements
            result.append((copy_element(track_elem), track_info))

    return result


def get_playlist_track_count(xml_file, playlist_name):
    """Get the number of tracks in a playlist without loading full metadata."""
    playlists = get_playlists(xml_file)
    if playlist_name not in playlists:
        return 0

    playlist_node = playlists[playlist_name]
    return len(playlist_node.findall('TRACK'))


# =============================================================================
# XML Generation
# =============================================================================

def generate_playlist_xml(track_elements, playlist_name, tracks_folder_name, output_path):
    """
    Generate a Rekordbox-compatible XML file with placeholder paths.

    Args:
        track_elements: List of tuples (track_xml_element, track_info_dict)
        playlist_name: Name of the playlist
        tracks_folder_name: Name of the tracks subfolder (e.g., "PlaylistName_tracks")
        output_path: Path where the XML will be saved
    """
    # Create root element
    root = ET.Element('DJ_PLAYLISTS', Version="1.0.0")

    # Add product info
    product = ET.SubElement(root, 'PRODUCT',
                            Name="rekordbox",
                            Version="6.6.8",
                            Company="AlphaTheta")

    # Create collection with all tracks
    collection = ET.SubElement(root, 'COLLECTION', Entries=str(len(track_elements)))

    # Add each track with updated location
    for track_elem, track_info in track_elements:
        # Get the new filename that was used when copying
        new_filename = track_info.get('new_filename', '')

        # Create placeholder path - PLACEHOLDER_ROOT will be replaced by setup script
        # Note: PLACEHOLDER_ROOT will be replaced with full path including leading slash
        placeholder_path = f"PLACEHOLDER_ROOT/{tracks_folder_name}/{new_filename}"
        track_elem.set('Location', f"file://localhost{placeholder_path}")

        collection.append(track_elem)

    # Create playlists section
    playlists = ET.SubElement(root, 'PLAYLISTS')
    root_node = ET.SubElement(playlists, 'NODE', Type="0", Name="ROOT", Count="1")

    # Create the playlist node
    playlist_node = ET.SubElement(root_node, 'NODE',
                                   Name=playlist_name,
                                   Type="1",
                                   KeyType="0",
                                   Entries=str(len(track_elements)))

    # Add track references to playlist
    for track_elem, track_info in track_elements:
        ET.SubElement(playlist_node, 'TRACK', Key=track_info['track_id'])

    # Create the tree and write to file
    tree = ET.ElementTree(root)

    # Write with XML declaration
    with open(output_path, 'wb') as f:
        tree.write(f, encoding='UTF-8', xml_declaration=True)

    return output_path


# =============================================================================
# Setup Script Generation
# =============================================================================

def generate_mac_setup_script(output_path, xml_filename, tracks_folder_name):
    """Generate a double-clickable Mac setup script with robust error handling."""
    script_content = f'''#!/bin/bash
# Rekordbox Playlist Setup Script
# Double-click this file to prepare the playlist for import into Rekordbox.

cd "$(dirname "$0")"
CURRENT_DIR=$(pwd)
XML_FILE="{xml_filename}"
BACKUP_FILE="{xml_filename}.backup"
TRACKS_FOLDER="{tracks_folder_name}"

echo "======================================"
echo "Rekordbox Playlist Setup"
echo "======================================"
echo ""
echo "Current location: $CURRENT_DIR"
echo "XML file: $XML_FILE"
echo "Tracks folder: $TRACKS_FOLDER"
echo ""

# --------------------------------------
# Step 1: Validate XML file exists
# --------------------------------------
echo "[1/5] Checking XML file exists..."
if [ ! -f "$XML_FILE" ]; then
    echo "  ERROR: XML file not found: $XML_FILE"
    echo ""
    echo "  Make sure you're running this script from the playlist folder."
    echo ""
    read -p "Press Enter to close..."
    exit 1
fi
echo "  Found: $XML_FILE"

# --------------------------------------
# Step 2: URL-encode the current path
# --------------------------------------
echo ""
echo "[2/5] Encoding current path for Rekordbox..."
ENCODED_DIR=""
for (( i=0; i<${{#CURRENT_DIR}}; i++ )); do
    char="${{CURRENT_DIR:$i:1}}"
    case "$char" in
        [a-zA-Z0-9/_.-])
            ENCODED_DIR+="$char"
            ;;
        ' ')
            ENCODED_DIR+="%20"
            ;;
        *)
            ENCODED_DIR+=$(printf '%%%02X' "'$char")
            ;;
    esac
done

if [ -z "$ENCODED_DIR" ]; then
    echo "  ERROR: Failed to encode directory path."
    echo ""
    read -p "Press Enter to close..."
    exit 1
fi
echo "  Encoded path: $ENCODED_DIR"

# --------------------------------------
# Step 3: Analyze current XML state
# --------------------------------------
echo ""
echo "[3/5] Analyzing XML file..."

# Check if already configured for THIS location
if grep -q "$ENCODED_DIR/$TRACKS_FOLDER" "$XML_FILE"; then
    echo "  Current path in XML: $ENCODED_DIR"
    echo "  Target path: $ENCODED_DIR"
    echo ""
    echo "  STATUS: Paths already match - no changes needed!"
    echo ""
    echo "  This playlist is already set up for this location."
    echo "  You can import it directly into Rekordbox."
    echo ""
    echo "======================================"
    read -p "Press Enter to close..."
    exit 0
fi

# Determine what's currently in the XML
if grep -q "PLACEHOLDER_ROOT" "$XML_FILE"; then
    OLD_PATH="PLACEHOLDER_ROOT"
    echo "  Current path in XML: PLACEHOLDER_ROOT (fresh export, not yet configured)"
    PATH_TYPE="placeholder"
else
    OLD_PATH=$(grep -o 'file://localhost[^"]*/'$TRACKS_FOLDER'/' "$XML_FILE" | head -1 | sed "s|/$TRACKS_FOLDER/||" | sed "s|file://localhost||")
    if [ -z "$OLD_PATH" ]; then
        echo "  ERROR: Could not find any path pattern in XML."
        echo "  The XML file may be corrupted or in an unexpected format."
        echo ""
        read -p "Press Enter to close..."
        exit 1
    fi
    echo "  Current path in XML: $OLD_PATH"
    PATH_TYPE="existing"
fi
echo "  Target path: $ENCODED_DIR"

# --------------------------------------
# Step 4: Create backup
# --------------------------------------
echo ""
echo "[4/5] Creating backup..."
cp "$XML_FILE" "$BACKUP_FILE"
if [ $? -ne 0 ]; then
    echo "  ERROR: Failed to create backup. Check disk space and permissions."
    echo ""
    read -p "Press Enter to close..."
    exit 1
fi
echo "  Backup created: $BACKUP_FILE"

# --------------------------------------
# Step 5: Update XML paths
# --------------------------------------
echo ""
echo "[5/5] Updating XML paths..."

if [ "$PATH_TYPE" = "placeholder" ]; then
    echo "  Replacing PLACEHOLDER_ROOT with actual path..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|PLACEHOLDER_ROOT|$ENCODED_DIR|g" "$XML_FILE"
    else
        sed -i "s|PLACEHOLDER_ROOT|$ENCODED_DIR|g" "$XML_FILE"
    fi
else
    echo "  Replacing old path with new path..."
    # Escape special characters for sed
    # Pattern needs: . escaped (regex special), & escaped, | escaped (our delimiter)
    # Replacement needs: & escaped (means "matched text" in sed)
    ESCAPED_OLD_PATH=$(printf '%s' "$OLD_PATH" | sed -e 's/[.&|]/\\\\&/g')
    ESCAPED_NEW_PATH=$(printf '%s' "$ENCODED_DIR" | sed -e 's/[&]/\\\\&/g')
    ESCAPED_TRACKS_FOLDER=$(printf '%s' "$TRACKS_FOLDER" | sed -e 's/[.&|]/\\\\&/g')
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|file://localhost$ESCAPED_OLD_PATH/$ESCAPED_TRACKS_FOLDER/|file://localhost$ESCAPED_NEW_PATH/$TRACKS_FOLDER/|g" "$XML_FILE"
    else
        sed -i "s|file://localhost$ESCAPED_OLD_PATH/$ESCAPED_TRACKS_FOLDER/|file://localhost$ESCAPED_NEW_PATH/$TRACKS_FOLDER/|g" "$XML_FILE"
    fi
fi

if [ $? -ne 0 ]; then
    echo "  ERROR: sed command failed."
    echo "  Restoring from backup..."
    mv "$BACKUP_FILE" "$XML_FILE"
    echo ""
    read -p "Press Enter to close..."
    exit 1
fi

# --------------------------------------
# Verify the replacement worked
# --------------------------------------
echo ""
echo "Verifying changes..."

if grep -q "PLACEHOLDER_ROOT" "$XML_FILE"; then
    echo "  ERROR: XML still contains PLACEHOLDER_ROOT after update."
    echo "  Restoring from backup..."
    mv "$BACKUP_FILE" "$XML_FILE"
    echo ""
    read -p "Press Enter to close..."
    exit 1
fi

if ! grep -q "$ENCODED_DIR/$TRACKS_FOLDER" "$XML_FILE"; then
    echo "  ERROR: XML doesn't contain the new path after update."
    echo "  Restoring from backup..."
    mv "$BACKUP_FILE" "$XML_FILE"
    echo ""
    read -p "Press Enter to close..."
    exit 1
fi

# Count how many paths were updated
PATH_COUNT=$(grep -c "$ENCODED_DIR/$TRACKS_FOLDER" "$XML_FILE" || echo "0")

rm -f "$BACKUP_FILE"

echo ""
echo "======================================"
echo "SUCCESS!"
echo "======================================"
echo ""
echo "Changed XML paths:"
echo "  FROM: $OLD_PATH"
echo "  TO:   $ENCODED_DIR"
echo ""
echo "Updated $PATH_COUNT track path(s) in $XML_FILE"
echo ""
echo "======================================"
echo "Next steps:"
echo "======================================"
echo ""
echo "1. Open Rekordbox"
echo "2. Go to Preferences > Advanced > Database"
echo "3. Under 'rekordbox xml', click Browse and select:"
echo "   $CURRENT_DIR/$XML_FILE"
echo "4. The playlist will appear in your rekordbox xml section"
echo "5. Right-click the playlist and select 'Import To Collection'"
echo ""
echo "======================================"
read -p "Press Enter to close..."
'''

    with open(output_path, 'w') as f:
        f.write(script_content)

    # Make executable
    os.chmod(output_path, os.stat(output_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def generate_windows_setup_script(output_path, xml_filename, tracks_folder_name):
    """Generate a double-clickable Windows setup script with robust error handling."""
    # Use PowerShell for the heavy lifting - it's built into Windows and handles
    # URL encoding, file operations, and error handling much better than batch
    script_content = f'''@echo off
REM Rekordbox Playlist Setup Script
REM Double-click this file to prepare the playlist for import into Rekordbox.

cd /d "%~dp0"

REM Run the setup logic in PowerShell (built into Windows, no extra install needed)
powershell -ExecutionPolicy Bypass -Command ^
$ErrorActionPreference = 'Stop'; ^
$xmlFile = '{xml_filename}'; ^
$backupFile = '{xml_filename}.backup'; ^
$tracksFolder = '{tracks_folder_name}'; ^
$currentDir = (Get-Location).Path; ^
^
Write-Host '======================================'; ^
Write-Host 'Rekordbox Playlist Setup'; ^
Write-Host '======================================'; ^
Write-Host ''; ^
Write-Host \"Current location: $currentDir\"; ^
Write-Host \"XML file: $xmlFile\"; ^
Write-Host \"Tracks folder: $tracksFolder\"; ^
Write-Host ''; ^
^
try {{ ^
    Write-Host '[1/5] Checking XML file exists...'; ^
    if (-not (Test-Path $xmlFile)) {{ ^
        throw \"  ERROR: XML file not found: $xmlFile`n`n  Make sure you're running this script from the playlist folder.\"; ^
    }} ^
    Write-Host \"  Found: $xmlFile\"; ^
    ^
    $content = Get-Content $xmlFile -Raw; ^
    ^
    Write-Host ''; ^
    Write-Host '[2/5] Encoding current path for Rekordbox...'; ^
    Add-Type -AssemblyName System.Web; ^
    $encodedDir = [System.Web.HttpUtility]::UrlEncode($currentDir).Replace('%%2b', '+').Replace('%%2f', '/').Replace('%%5c', '/').Replace('%%3a', ':'); ^
    $encodedDir = $encodedDir -replace '\\\\', '/'; ^
    Write-Host \"  Encoded path: $encodedDir\"; ^
    ^
    $expectedPath = \"$encodedDir/$tracksFolder\"; ^
    ^
    Write-Host ''; ^
    Write-Host '[3/5] Analyzing XML file...'; ^
    ^
    if ($content -match [regex]::Escape($expectedPath)) {{ ^
        Write-Host \"  Current path in XML: $encodedDir\"; ^
        Write-Host \"  Target path: $encodedDir\"; ^
        Write-Host ''; ^
        Write-Host '  STATUS: Paths already match - no changes needed!'; ^
        Write-Host ''; ^
        Write-Host '  This playlist is already set up for this location.'; ^
        Write-Host '  You can import it directly into Rekordbox.'; ^
        Write-Host ''; ^
        Write-Host '======================================'; ^
        Read-Host 'Press Enter to close'; ^
        exit 0; ^
    }} ^
    ^
    $oldPath = $null; ^
    $pathType = $null; ^
    ^
    if ($content -match 'PLACEHOLDER_ROOT') {{ ^
        $oldPath = 'PLACEHOLDER_ROOT'; ^
        $pathType = 'placeholder'; ^
        Write-Host '  Current path in XML: PLACEHOLDER_ROOT (fresh export, not yet configured)'; ^
    }} else {{ ^
        $pattern = \"file://localhost([^`\"]*?)/$tracksFolder/\"; ^
        $match = [regex]::Match($content, $pattern); ^
        if (-not $match.Success) {{ ^
            throw '  ERROR: Could not find any path pattern in XML.`n  The XML file may be corrupted or in an unexpected format.'; ^
        }} ^
        $oldPath = $match.Groups[1].Value; ^
        $pathType = 'existing'; ^
        Write-Host \"  Current path in XML: $oldPath\"; ^
    }} ^
    Write-Host \"  Target path: $encodedDir\"; ^
    ^
    Write-Host ''; ^
    Write-Host '[4/5] Creating backup...'; ^
    Copy-Item $xmlFile $backupFile -Force; ^
    Write-Host \"  Backup created: $backupFile\"; ^
    ^
    Write-Host ''; ^
    Write-Host '[5/5] Updating XML paths...'; ^
    ^
    if ($pathType -eq 'placeholder') {{ ^
        Write-Host '  Replacing PLACEHOLDER_ROOT with actual path...'; ^
        $newContent = $content -replace 'PLACEHOLDER_ROOT', $encodedDir; ^
    }} else {{ ^
        Write-Host '  Replacing old path with new path...'; ^
        $escapedOldPath = [regex]::Escape($oldPath); ^
        $escapedTracksFolder = [regex]::Escape($tracksFolder); ^
        $newContent = $content -replace \"file://localhost$escapedOldPath/$escapedTracksFolder/\", \"file://localhost$encodedDir/$tracksFolder/\"; ^
    }} ^
    ^
    Set-Content $xmlFile $newContent -NoNewline; ^
    ^
    Write-Host ''; ^
    Write-Host 'Verifying changes...'; ^
    $verifyContent = Get-Content $xmlFile -Raw; ^
    ^
    if ($verifyContent -match 'PLACEHOLDER_ROOT') {{ ^
        throw '  ERROR: XML still contains PLACEHOLDER_ROOT after update.'; ^
    }} ^
    ^
    if ($verifyContent -notmatch [regex]::Escape($expectedPath)) {{ ^
        throw '  ERROR: XML does not contain the new path after update.'; ^
    }} ^
    ^
    $pathCount = ([regex]::Matches($verifyContent, [regex]::Escape($expectedPath))).Count; ^
    ^
    Remove-Item $backupFile -Force -ErrorAction SilentlyContinue; ^
    ^
    Write-Host ''; ^
    Write-Host '======================================'; ^
    Write-Host 'SUCCESS!'; ^
    Write-Host '======================================'; ^
    Write-Host ''; ^
    Write-Host 'Changed XML paths:'; ^
    Write-Host \"  FROM: $oldPath\"; ^
    Write-Host \"  TO:   $encodedDir\"; ^
    Write-Host ''; ^
    Write-Host \"Updated $pathCount track path(s) in $xmlFile\"; ^
    Write-Host ''; ^
    Write-Host '======================================'; ^
    Write-Host 'Next steps:'; ^
    Write-Host '======================================'; ^
    Write-Host ''; ^
    Write-Host '1. Open Rekordbox'; ^
    Write-Host '2. Go to Preferences ^> Advanced ^> Database'; ^
    Write-Host \"3. Under 'rekordbox xml', click Browse and select:\"; ^
    Write-Host \"   $currentDir\\$xmlFile\"; ^
    Write-Host '4. The playlist will appear in your rekordbox xml section'; ^
    Write-Host \"5. Right-click the playlist and select 'Import To Collection'\"; ^
    Write-Host ''; ^
    Write-Host '======================================'; ^
^
}} catch {{ ^
    Write-Host ''; ^
    Write-Host $_.Exception.Message -ForegroundColor Red; ^
    Write-Host ''; ^
    if (Test-Path $backupFile) {{ ^
        Write-Host 'Restoring from backup...'; ^
        Move-Item $backupFile $xmlFile -Force; ^
    }} ^
}} ^
^
Read-Host 'Press Enter to close'
'''

    with open(output_path, 'w') as f:
        f.write(script_content)


def generate_recipient_readme(output_path, playlist_name, xml_filename):
    """Generate a README.txt for the recipient explaining how to use the package."""
    readme_content = f'''==============================================
REKORDBOX PLAYLIST: {playlist_name}
==============================================

This folder contains a Rekordbox playlist with all metadata preserved
(hot cues, cue points, beat grids, BPM, key, etc.)

----------------------------------------------
QUICK START
----------------------------------------------

1. FIRST, run the setup script for your operating system:
   - Mac: Double-click "Setup (Mac).command"
   - Windows: Double-click "Setup (Windows).bat"

2. THEN, import the playlist into Rekordbox:
   - Open Rekordbox
   - Go to Preferences > Advanced > Database
   - Under "rekordbox xml", click Browse
   - Select the file: {xml_filename}
   - The playlist will appear in your sidebar under "rekordbox xml"
   - Right-click the playlist > "Import To Collection"

----------------------------------------------
MAC USERS: IF THE SCRIPT IS BLOCKED
----------------------------------------------

macOS Gatekeeper may block the setup script from running because it
was downloaded from the internet. You have two options:

OPTION 1: Use System Settings (GUI)
   - Try to run the script (it will be blocked)
   - Open System Settings > Privacy & Security
   - Scroll down to find the blocked script message
   - Click "Allow Anyway"
   - Try running the script again

OPTION 2: Use Terminal (Faster)
   Open Terminal and run this command (replace the path with your actual path):

   xattr -d com.apple.quarantine "/path/to/Setup (Mac).command"

   For example, if the playlist is on your Desktop:

   xattr -d com.apple.quarantine ~/Desktop/{playlist_name}/Setup\\ \\(Mac\\).command

   Or navigate to the playlist folder and run:

   cd ~/Desktop/{playlist_name}
   xattr -d com.apple.quarantine "Setup (Mac).command"

   This removes the "quarantine" flag that macOS adds to downloaded files.

----------------------------------------------
IMPORTANT NOTES
----------------------------------------------

- You MUST run the Setup script BEFORE importing into Rekordbox
- If you move this folder, re-run the Setup script to update paths
- You can run the Setup script as many times as needed
- All your friend's cue points and beat grids will be preserved!

----------------------------------------------
FOLDER CONTENTS
----------------------------------------------

- {playlist_name}_tracks/  : The audio files
- {xml_filename}           : Rekordbox XML with all metadata
- Setup (Mac).command      : Setup script for Mac users
- Setup (Windows).bat      : Setup script for Windows users
- README.txt               : This file

==============================================
'''

    with open(output_path, 'w') as f:
        f.write(readme_content)


# =============================================================================
# Auto-run Setup (for GUI - replaces placeholders immediately)
# =============================================================================

def run_setup_for_exporter(xml_path, tracks_folder_path):
    """
    Run the setup script logic in Python - replaces PLACEHOLDER_ROOT with actual path.
    This is called by the GUI so the exporter's XML is ready immediately.

    Args:
        xml_path: Path to the XML file
        tracks_folder_path: Path to the tracks folder (parent of the tracks)
    """
    # Get the folder containing the XML (the playlist folder)
    playlist_folder = Path(xml_path).parent

    # URL-encode the path
    encoded_path = quote(str(playlist_folder), safe='/')

    # Read the XML file
    with open(xml_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace the placeholder
    content = content.replace('PLACEHOLDER_ROOT', encoded_path)

    # Write back
    with open(xml_path, 'w', encoding='utf-8') as f:
        f.write(content)


# =============================================================================
# Export Function
# =============================================================================

class ExportResult:
    """Result of an export operation."""
    def __init__(self):
        self.successful = 0
        self.failed = 0
        self.failed_tracks = []
        self.output_folder = None
        self.cancelled = False


def export_playlist(xml_file, playlist_name, output_base_folder, mode="full",
                    progress_callback=None, auto_run_setup=False):
    """
    Export a playlist to a folder.

    Args:
        xml_file: Path to the Rekordbox XML file
        playlist_name: Full name of the playlist (including path like "ROOT/folder/name")
        output_base_folder: Folder where the export will be created
        mode: "copy_only" for just tracks, "full" for tracks + XML + setup scripts
        progress_callback: Optional function(current, total, track_name, status) for progress updates
                          status can be: "copying", "success", "failed", "generating", "complete"
                          If callback returns False, export is cancelled
        auto_run_setup: If True and mode is "full", run setup script logic after export
                        (replaces PLACEHOLDER_ROOT with actual paths)

    Returns:
        ExportResult with successful count, failed count, failed tracks list, and output folder
    """
    result = ExportResult()

    # Get playlist name without path prefix (for folder naming)
    simple_playlist_name = playlist_name.split('/')[-1]
    safe_playlist_name = sanitize_filename(simple_playlist_name)

    # Get full track elements with all metadata
    track_elements = get_full_track_elements(xml_file, playlist_name)

    if not track_elements:
        return result

    total_tracks = len(track_elements)

    # Create folder structure - handle case-insensitive filesystem collisions
    # (e.g., "Freeform" vs "freeform" on macOS)
    playlist_folder = get_unique_folder_path(output_base_folder, safe_playlist_name)
    # Update safe_playlist_name to match the actual folder name used
    actual_folder_name = playlist_folder.name

    if mode == "full":
        tracks_folder_name = f"{actual_folder_name}_tracks"
        tracks_folder = playlist_folder / tracks_folder_name
        tracks_folder.mkdir(parents=True, exist_ok=True)
    else:
        # copy_only mode: tracks go directly in playlist folder
        tracks_folder = playlist_folder
        tracks_folder_name = None

    playlist_folder.mkdir(parents=True, exist_ok=True)
    result.output_folder = playlist_folder

    # Copy tracks and update track_info with new filenames
    valid_track_elements = []

    for i, (track_elem, track_info) in enumerate(track_elements, 1):
        source_path = Path(track_info['location'])
        track_display = f"{track_info['artist']} - {track_info['name']}"

        # Report progress - copying
        if progress_callback:
            should_continue = progress_callback(i, total_tracks, track_display, "copying")
            if should_continue is False:
                result.cancelled = True
                return result

        if not source_path.exists():
            result.failed += 1
            result.failed_tracks.append({
                'name': track_display,
                'reason': 'File not found',
                'path': str(source_path)
            })
            if progress_callback:
                progress_callback(i, total_tracks, track_display, "failed")
            continue

        # Create numbered filename to preserve order
        file_extension = source_path.suffix
        safe_name = sanitize_filename(f"{track_info['artist']} - {track_info['name']}")
        dest_filename = f"{i:03d} - {safe_name}{file_extension}"
        dest_path = tracks_folder / dest_filename

        try:
            shutil.copy2(source_path, dest_path)
            result.successful += 1

            # Store the new filename for XML generation
            track_info['new_filename'] = dest_filename
            valid_track_elements.append((track_elem, track_info))

            if progress_callback:
                progress_callback(i, total_tracks, track_display, "success")
        except Exception as e:
            result.failed += 1
            result.failed_tracks.append({
                'name': track_display,
                'reason': str(e),
                'path': str(source_path)
            })
            if progress_callback:
                progress_callback(i, total_tracks, track_display, "failed")

    if not valid_track_elements:
        return result

    if mode == "full":
        # Report progress - generating
        if progress_callback:
            progress_callback(total_tracks, total_tracks, "Generating XML...", "generating")

        # Generate the playlist XML (use actual_folder_name for consistency with folder)
        xml_filename = f"{actual_folder_name}.xml"
        xml_path = playlist_folder / xml_filename
        generate_playlist_xml(valid_track_elements, simple_playlist_name, tracks_folder_name, xml_path)

        # Generate setup scripts
        if progress_callback:
            progress_callback(total_tracks, total_tracks, "Generating setup scripts...", "generating")

        mac_script_path = playlist_folder / "Setup (Mac).command"
        windows_script_path = playlist_folder / "Setup (Windows).bat"

        generate_mac_setup_script(mac_script_path, xml_filename, tracks_folder_name)
        generate_windows_setup_script(windows_script_path, xml_filename, tracks_folder_name)

        # Generate README for recipient
        readme_path = playlist_folder / "README.txt"
        generate_recipient_readme(readme_path, simple_playlist_name, xml_filename)

        # Auto-run setup if requested (for GUI - makes exporter's XML ready immediately)
        if auto_run_setup:
            if progress_callback:
                progress_callback(total_tracks, total_tracks, "Preparing XML for import...", "generating")
            run_setup_for_exporter(xml_path, tracks_folder)

    # Report completion
    if progress_callback:
        progress_callback(total_tracks, total_tracks, "Complete!", "complete")

    return result

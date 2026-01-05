"""
MekaBox Core - Shared logic for Rekordbox playlist export

This module contains all the core functionality for:
- Parsing Rekordbox XML files
- Extracting playlist and track information
- Generating shareable playlist packages with metadata
- Creating setup scripts for recipients

Used by both the CLI (rekordbox_playlist_copier.py) and GUI (mekabox_app.py)
"""

import copy
import os
import shutil
import stat
from pathlib import Path
from urllib.parse import quote, unquote
from xml.etree import ElementTree as ET


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
            result.append((copy.deepcopy(track_elem), track_info))

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
    """Generate a double-clickable Mac setup script."""
    script_content = f'''#!/bin/bash
# Rekordbox Playlist Setup Script
# Double-click this file to prepare the playlist for import into Rekordbox.

cd "$(dirname "$0")"
CURRENT_DIR=$(pwd)

echo "======================================"
echo "Rekordbox Playlist Setup"
echo "======================================"
echo ""
echo "Preparing playlist for import..."
echo "Location: $CURRENT_DIR"
echo ""

# URL-encode spaces and special characters in the path
ENCODED_DIR=$(python3 -c "import sys; from urllib.parse import quote; print(quote(sys.argv[1], safe='/'))" "$CURRENT_DIR")

# Replace placeholder with actual path in XML
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s|PLACEHOLDER_ROOT|$ENCODED_DIR|g" "{xml_filename}"
else
    # Linux
    sed -i "s|PLACEHOLDER_ROOT|$ENCODED_DIR|g" "{xml_filename}"
fi

echo "Done!"
echo ""
echo "Next steps:"
echo "1. Open Rekordbox"
echo "2. Go to Preferences > Advanced > Database"
echo "3. Under 'rekordbox xml', click Browse and select:"
echo "   $CURRENT_DIR/{xml_filename}"
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
    """Generate a double-clickable Windows setup script."""
    script_content = f'''@echo off
REM Rekordbox Playlist Setup Script
REM Double-click this file to prepare the playlist for import into Rekordbox.

echo ======================================
echo Rekordbox Playlist Setup
echo ======================================
echo.
echo Preparing playlist for import...
echo Location: %~dp0
echo.

cd /d "%~dp0"

REM Get current directory and encode spaces as %20
set "CURRENT_DIR=%cd%"
set "ENCODED_DIR=%CURRENT_DIR: =%%20%"

REM Replace placeholder with actual path in XML using PowerShell
powershell -Command "(Get-Content '{xml_filename}') -replace 'PLACEHOLDER_ROOT', '%ENCODED_DIR%' | Set-Content '{xml_filename}'"

echo Done!
echo.
echo Next steps:
echo 1. Open Rekordbox
echo 2. Go to Preferences ^> Advanced ^> Database
echo 3. Under 'rekordbox xml', click Browse and select:
echo    %cd%\\{xml_filename}
echo 4. The playlist will appear in your rekordbox xml section
echo 5. Right-click the playlist and select 'Import To Collection'
echo.
echo ======================================
pause
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
IMPORTANT NOTES
----------------------------------------------

- You MUST run the Setup script BEFORE importing into Rekordbox
- The Setup script only needs to be run once
- If you move this folder, you'll need to re-run the Setup script
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

    # Create folder structure
    playlist_folder = Path(output_base_folder) / safe_playlist_name
    if mode == "full":
        tracks_folder_name = f"{safe_playlist_name}_tracks"
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

        # Generate the playlist XML
        xml_filename = f"{safe_playlist_name}.xml"
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

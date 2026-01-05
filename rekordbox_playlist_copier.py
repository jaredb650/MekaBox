#!/usr/bin/env python3
"""
Rekordbox Playlist Copier (CLI)

Command-line interface for exporting Rekordbox playlists.
For GUI version, use mekabox_app.py

Usage:
    python3 rekordbox_playlist_copier.py
    python3 rekordbox_playlist_copier.py <xml_file> <playlist_name> [output_folder]
"""

import os
import sys

# Import core functionality
from mekabox_core import (
    get_playlists,
    export_playlist,
    ExportResult,
)


def check_quit(value):
    """Check if user wants to quit and exit if so."""
    if value.lower() == 'quit':
        print("\nExiting...")
        sys.exit(0)


def cli_progress_callback(current, total, track_name, status):
    """Progress callback that prints to console."""
    if status == "copying":
        pass  # Don't print "copying" status
    elif status == "success":
        print(f"  \u2713 Track {current}: {track_name}")
    elif status == "failed":
        print(f"  \u2717 Track {current}: {track_name}")
    elif status == "generating":
        print(f"\n{track_name}")
    elif status == "complete":
        pass  # Summary printed separately
    return True  # Continue export


def main():
    print("\n" + "="*60)
    print("Rekordbox Playlist Exporter")
    print("Export playlists with full metadata (cue points, beat grids, etc.)")
    print("="*60 + "\n")

    # Get XML file
    if len(sys.argv) > 1:
        xml_file = sys.argv[1].strip().strip("'\"")
    else:
        xml_file = input("Enter path to Rekordbox XML file (or 'quit'): ").strip().strip("'\"")
        check_quit(xml_file)

    if not os.path.exists(xml_file):
        print(f"Error: File not found - {xml_file}")
        return

    # Show available playlists
    print("\nScanning XML file...")
    playlists = get_playlists(xml_file)

    if not playlists:
        print("No playlists found in XML file")
        return

    print(f"\nFound {len(playlists)} playlist(s):\n")
    playlist_list = sorted(playlists.keys())
    for i, name in enumerate(playlist_list, 1):
        print(f"  {i}. {name}")

    # Get playlist selection
    print("\n" + "-"*60)
    if len(sys.argv) > 2:
        playlist_name = sys.argv[2]
    else:
        selection = input("\nEnter playlist number or name (or 'quit'): ").strip()
        check_quit(selection)

        # Check if it's a number
        try:
            idx = int(selection) - 1
            if 0 <= idx < len(playlist_list):
                playlist_name = playlist_list[idx]
            else:
                print("Invalid selection")
                return
        except ValueError:
            # It's a name
            playlist_name = selection

    # Get export mode
    print("\n" + "-"*60)
    print("\nWhat would you like to do?")
    print("  1. Copy tracks only")
    print('  2. Copy tracks + Generate XML (preserves Rekordbox metadata: hot cues, beat grids, etc.)')
    mode_selection = input("\nEnter choice (1 or 2, or 'quit'): ").strip()
    check_quit(mode_selection)

    if mode_selection == "1":
        mode = "copy_only"
    else:
        mode = "full"

    # Get output folder
    if len(sys.argv) > 3:
        output_folder = sys.argv[3].strip().strip("'\"")
    else:
        default_output = os.path.join(os.path.expanduser("~"), "Desktop", "rekordbox-exports")
        output_folder = input(f"\nEnter output folder (press Enter for Desktop, or 'quit'): ").strip().strip("'\"")
        check_quit(output_folder)
        if not output_folder:
            output_folder = default_output

    # Export the playlist
    print(f"\nSearching for playlist: {playlist_name}")

    result = export_playlist(
        xml_file,
        playlist_name,
        output_folder,
        mode=mode,
        progress_callback=cli_progress_callback
    )

    if result.cancelled:
        print("\nExport cancelled.")
        return

    if result.successful == 0 and result.failed == 0:
        print("No tracks found in playlist")
        return

    # Get names for display
    simple_playlist_name = playlist_name.split('/')[-1]
    from mekabox_core import sanitize_filename
    safe_playlist_name = sanitize_filename(simple_playlist_name)
    tracks_folder_name = f"{safe_playlist_name}_tracks"
    xml_filename = f"{safe_playlist_name}.xml"

    # Summary
    print(f"\n{'='*60}")
    print(f"Export Complete!")
    print(f"{'='*60}")
    print(f"  Tracks copied: {result.successful}")
    print(f"  Failed: {result.failed}")
    print(f"  Output folder: {result.output_folder}")

    if mode == "full":
        print(f"\nFolder contents:")
        print(f"  \U0001F4C1 {safe_playlist_name}/")
        print(f"     \U0001F4C1 {tracks_folder_name}/  ({result.successful} tracks)")
        print(f"     \U0001F4C4 {xml_filename}")
        print(f"     \U0001F34E Setup (Mac).command")
        print(f"     \U0001FAA8 Setup (Windows).bat")
        print(f"     \U0001F4DD README.txt")
        print(f"\nTo share this playlist:")
        print(f"  1. Zip the '{safe_playlist_name}' folder")
        print(f"  2. Send it to the recipient")
        print(f"  3. They can read README.txt for instructions")
    else:
        print(f"\nFolder contents:")
        print(f"  \U0001F4C1 {safe_playlist_name}/  ({result.successful} tracks)")

    print(f"{'='*60}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)

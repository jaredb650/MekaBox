#!/usr/bin/env python3
"""
MekaBox CLI - Command-line interface for the bundled executable.
This is the entry point that PyInstaller will bundle.
Accepts JSON commands and returns JSON responses.
"""

import json
import sys
from mekabox_core import get_playlists, get_playlist_track_count, export_playlist


def handle_get_playlists(args):
    """Get list of playlists from XML file."""
    xml_path = args.get('xml_path')
    if not xml_path:
        return {'success': False, 'error': 'xml_path is required'}

    try:
        playlists = get_playlists(xml_path)
        return {'success': True, 'playlists': list(playlists.keys())}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def handle_get_track_count(args):
    """Get track count for a playlist."""
    xml_path = args.get('xml_path')
    playlist_name = args.get('playlist_name')

    if not xml_path or not playlist_name:
        return {'success': False, 'error': 'xml_path and playlist_name are required'}

    try:
        count = get_playlist_track_count(xml_path, playlist_name)
        return {'success': True, 'count': count}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def handle_export(args):
    """Export a playlist with progress callbacks."""
    xml_path = args.get('xml_path')
    playlist_name = args.get('playlist_name')
    output_folder = args.get('output_folder')
    mode = args.get('mode', 'full')

    if not all([xml_path, playlist_name, output_folder]):
        return {'success': False, 'error': 'xml_path, playlist_name, and output_folder are required'}

    def progress_callback(current, total, track_name, status):
        # Print progress as JSON line (will be parsed by Electron)
        print(json.dumps({
            'type': 'progress',
            'current': current,
            'total': total,
            'track': track_name,
            'status': status
        }), flush=True)
        return True

    try:
        result = export_playlist(
            xml_path,
            playlist_name,
            output_folder,
            mode=mode,
            progress_callback=progress_callback,
            auto_run_setup=True
        )
        return {
            'type': 'complete',
            'success': True,
            'successful': result.successful,
            'failed': result.failed,
            'output_folder': str(result.output_folder),
            'failed_tracks': result.failed_tracks
        }
    except Exception as e:
        return {'type': 'error', 'success': False, 'error': str(e)}


def main():
    """Main entry point - reads command from argv or stdin."""
    if len(sys.argv) < 2:
        print(json.dumps({'success': False, 'error': 'No command provided'}))
        sys.exit(1)

    command = sys.argv[1]

    # Read JSON args from stdin or argv
    if len(sys.argv) > 2:
        try:
            args = json.loads(sys.argv[2])
        except json.JSONDecodeError:
            args = {}
    else:
        args = {}

    # Route to appropriate handler
    handlers = {
        'get_playlists': handle_get_playlists,
        'get_track_count': handle_get_track_count,
        'export': handle_export,
    }

    handler = handlers.get(command)
    if not handler:
        print(json.dumps({'success': False, 'error': f'Unknown command: {command}'}))
        sys.exit(1)

    result = handler(args)
    print(json.dumps(result))


if __name__ == '__main__':
    main()

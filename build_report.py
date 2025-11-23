#!/usr/bin/env python3
"""
Build script for UniMRCP Log Analyzer
Parses log files and generates HTML reports
"""

import os
import sys
import subprocess
import webbrowser
import argparse
from pathlib import Path
import re

SCRIPT_DIR = Path(__file__).resolve().parent
PARSER = SCRIPT_DIR / "main.py"
HTML_WRITER = SCRIPT_DIR / "update_html.py"

def check_security(log_file):
    """Check if the log file might contain confidential data"""
    log_name = log_file.lower()
    sensitive_keywords = ['blue', 'prod', 'production', 'live', 'internal']
    for keyword in sensitive_keywords:
        if keyword in log_name:
            # Only print a warning, do not prompt or block execution
            print(f"⚠️  WARNING: Log file '{log_file}' may contain confidential data!")
            print("   Make sure this file is not committed to version control.")
            print("   The .gitignore file should exclude this file.")
            break

def main():
    parser = argparse.ArgumentParser(description="Build UniMRCP log report")
    parser.add_argument("logfile", nargs='?', help="Path to the log file (optional - will auto-detect if not provided)")
    parser.add_argument("--no-server", action="store_true", help="Don't start the web server")
    parser.add_argument("--port", type=int, default=8000, help="Port for web server (default: 8000)")
    
    args = parser.parse_args()
    
    # Find log file
    log_file = None
    
    if args.logfile:
        # Use provided log file path
        log_file = Path(args.logfile)
        if not log_file.exists():
            print(f"❌ Error: Log file '{args.logfile}' not found")
            sys.exit(1)
    else:
        # Auto-detect log file in current directory
        log_files = []
        for ext in ['*.log', '*.CSV', '*.csv']:
            log_files.extend(Path('.').glob(ext))
        
        if not log_files:
            print("❌ No log files found. Please place your UniMRCP log file in this directory.")
            print("   Supported formats: .log, .CSV, .csv")
            print("   Or specify a path: python3 build_report.py /path/to/your/log.log")
            sys.exit(1)
        
        log_file = log_files[0]
    
    print(f"📄 Processing log file: {log_file}")
    
    # Security check
    check_security(log_file.name)
    
    # Parse the log file to a temp summary
    temp_summary = Path('summary.json.tmp')
    if temp_summary.exists():
        temp_summary.unlink()
    print(f"🔍 Parsing {log_file}...")
    try:
        result = subprocess.run([sys.executable, str(PARSER), str(log_file), '-o', str(temp_summary)],
                              capture_output=True, text=True, check=True)
        print("✅ Log parsing completed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error parsing log file: {e}")
        print(f"   Error output: {e.stderr}")
        sys.exit(1)
    
    # Check if temp summary was created
    if not temp_summary.exists():
        print("❌ No summary.json generated. Check the log file format.")
        sys.exit(1)
    
    # Move temp summary to summary.json
    Path('summary.json').unlink(missing_ok=True)
    temp_summary.rename('summary.json')

    # --- Compute extra stats for HTML ---
    import json
    with open('summary.json', 'r', encoding='utf-8') as f:
        summary = json.load(f)
    tts_sessions = 0
    asr_sessions = 0
    for s in summary.get('sessions', []):
        status = (s.get('session_data', {}) or {}).get('status', '').upper()
        if not status:
            info = s.get('session_info', '')
            m = re.search(r'Status:\s*([A-Z0-9 ()\-]+)', info)
            if m:
                status = m.group(1).strip().upper()
        if 'NO MRCP' in status:
            continue  # skip sessions with no MRCP
        if 'TTS-ONLY' in status:
            tts_sessions += 1
        elif 'COMPLETE' in status or 'INCOMPLETE' in status:
            asr_sessions += 1
    summary['stats'] = {
        'tts_sessions': tts_sessions,
        'asr_sessions': asr_sessions
    }
    with open('summary.json', 'w', encoding='utf-8', newline='') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    # Update HTML report to a temp file
    print("📊 Updating HTML report...")
    temp_html = Path('report.html.tmp')
    if temp_html.exists():
        temp_html.unlink()
    try:
        result = subprocess.run([sys.executable, str(HTML_WRITER), '--output', str(temp_html)],
                              capture_output=True, text=True, check=True)
        print("✅ HTML report updated successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error updating HTML: {e}")
        print(f"   Error output: {e.stderr}")
        sys.exit(1)
    
    # Move temp HTML to report.html
    Path('report.html').unlink(missing_ok=True)
    temp_html.rename('report.html')
    
    print(f"🎉 Report generated successfully!")
    print(f"   - JSON data: summary.json")
    print(f"   - HTML report: report.html")
    
    if not args.no_server:
        # Start local server
        print(f"🌐 Starting local server on port {args.port}...")
        print(f"   Open your browser to: http://localhost:{args.port}")
        print("   Press Ctrl+C to stop the server")
        
        try:
            subprocess.run([sys.executable, '-m', 'http.server', str(args.port)])
        except KeyboardInterrupt:
            print("\n👋 Server stopped")
    else:
        print("📁 Open report.html in your browser to view the report")

if __name__ == '__main__':
    main() 

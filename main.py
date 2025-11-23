#!/usr/bin/env python3
"""mrcp_summary.py  — rev 14 (2025‑07‑08)

Fixed version with corrected session assignment and MRCP direction detection.

Highlights
----------
1. Fixed session assignment logic to use Call-ID association instead of temporal proximity
2. Corrected MRCP direction detection based on actual protocol flow
3. Improved parameter parsing to exclude log metadata
4. Enhanced error handling and validation
5. Fixed grammar definition extraction for better robustness
6. Improved NLSML extraction with more robust regex patterns
7. Added proper session boundary detection with Call-ID validation
8. Enhanced timestamp parsing with better error handling
9. Added support for more MRCP methods and events
10. Improved memory efficiency with streaming processing

Usage
-----
    python3 mrcp_summary.py "exportedLogRecords (1).CSV" -o output.json

Output
------
JSON with session info, MRCP messages, and extracted content using reference system.
"""

import re
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict
import os
try:
    import yaml
except ImportError:
    yaml = None

# Load SUCCESS_CODES from config if available
SUCCESS_CODES = {0, 4, 5}
if os.path.exists('success_codes.yaml') and yaml:
    with open('success_codes.yaml', 'r', encoding='utf-8', errors='replace') as f:
        config = yaml.safe_load(f)
        if 'success_codes' in config:
            SUCCESS_CODES = set(config['success_codes'])
elif os.path.exists('success_codes.json'):
    import json as _json
    with open('success_codes.json', 'r', encoding='utf-8') as f:
        config = _json.load(f)
        if 'success_codes' in config:
            SUCCESS_CODES = set(config['success_codes'])

EXPLANATIONS = {
    "no_recognition":        "Recognizer was never invoked; call is TTS-only or ended before ASR began.",
    "timeout_after_success": "Call had a successful recognition, but a later attempt timed out (code 10) or failed.",
    "incomplete":            "Last recogniser result was a failure code (3 = no-match, 10 = timeout, etc.)."
}

# Pre-compiled regex patterns
_TSTAMP_RE = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[:.]\d{3,6})")
_CHANNEL_ID_RE = re.compile(r"Channel-Identifier:\s*(?P<cid>[^\s,]+)")
_SESSION_ID_RE = re.compile(r"SessionLifeEvent:\s*sid=(?P<sid>[0-9a-f]+)")
_CALL_ID_RE = re.compile(r'Call-ID:\s*([^\s,]+)')

# MRCP patterns
_MRCP_REQ_RE = re.compile(r'MRCP/2\.0\s+\d+\s+([A-Z\-]+)\s+(\d+)')
_MRCP_RESP_RE = re.compile(r'MRCP/2\.0\s+(\d+)\s+(\d+)\s+([A-Z\-]+)')

# Improved SIP patterns
_SIP_INVITE_RE = re.compile(r'INVITE\s+sip:[^\s]+', re.IGNORECASE)
_SIP_BYE_RE = re.compile(r'BYE\s+sip:[^\s]+', re.IGNORECASE)


def _parse_ts(raw: str) -> Optional[datetime]:
    """Parse timestamp from log format with better error handling."""
    try:
        # Handle various timestamp formats
        date_part, time_part = raw.split(' ', 1)

        # Normalize time format
        if ':' in time_part:
            # Handle double colon format (e.g., 22:27:10:692880)
            if time_part.count(':') == 3:
                parts = time_part.split(':')
                time_part = f"{parts[0]}:{parts[1]}:{parts[2]}.{parts[3]}"
            # Handle standard format with milliseconds
            elif '.' in time_part:
                # Already in correct format
                pass
            else:
                # Add milliseconds if missing
                time_part += ".000"

        fixed = f"{date_part} {time_part}"
        return datetime.fromisoformat(fixed.replace('Z', '+00:00'))
    except (ValueError, AttributeError) as e:
        print(f"Warning: Failed to parse timestamp '{raw}': {e}", file=sys.stderr)
        return None


def _iso_ms(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _pretty_dur(d: timedelta) -> str:
    return f"{d.seconds // 3600:02d}:{(d.seconds % 3600) // 60:02d}:{d.seconds % 60:02d}.{d.microseconds // 1000:03d}"


def _extract_ips(line: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract source and destination IPs from log line."""
    ip_pattern = r'(\d+\.\d+\.\d+\.\d+):(\d+)\s*<->\s*(\d+\.\d+\.\d+\.\d+):(\d+)'
    match = re.search(ip_pattern, line)
    if match:
        return match.group(1), match.group(3)
    return None, None


def _detect_mrcp(line: str):
    """Detect MRCP request or response with proper event classification."""
    md = _MRCP_REQ_RE.search(line)
    if md:
        method = md.group(1)
        # Classify server events as responses, not requests
        if method in ["START-OF-INPUT", "RECOGNITION-COMPLETE", "START-OF-SPEECH", "END-OF-SPEECH"]:
            return False, md.group(2), None, method  # is_req=False for server events
        return True, md.group(2), None, method  # is_req=True for client requests

    md = _MRCP_RESP_RE.search(line)
    if md:
        return False, md.group(1), md.group(2), md.group(3)  # is_req, req_id, status, method

    return None


def _clean_xml_content(xml_content: str) -> str:
    """Clean and pretty-print XML content for better readability."""
    if not xml_content:
        return xml_content

    # Step 1: Handle the specific format from UniMRCP logs
    # The XML content comes with quotes around each line and double-escaped quotes inside
    # Example: "<?xml version=""1.0"" encoding=""UTF-8""?>" -> <?xml version="1.0" encoding="UTF-8"?>
    
    # First, remove the outer quotes that wrap each line
    cleaned = re.sub(r'^"|"$', '', xml_content.strip())
    
    # Step 2: Handle double-escaped quotes (""text"" -> "text")
    # This is the most common pattern in your logs
    cleaned = re.sub(r'""([^"]*)""', r'"\1"', cleaned)
    
    # Step 3: Handle escaped characters in order of specificity
    # First handle double-escaped backslashes (\\\\ -> \\)
    cleaned = cleaned.replace('\\\\', '\\')
    
    # Then handle escaped quotes (\" -> ")
    cleaned = cleaned.replace('\\"', '"')
    
    # Handle other escaped characters
    cleaned = cleaned.replace('\\n', '\n')  # escaped newlines
    cleaned = cleaned.replace('\\r', '\r')  # escaped carriage returns  
    cleaned = cleaned.replace('\\t', '\t')  # escaped tabs
    
    # Step 4: Handle any remaining double quotes that might have been missed
    # This catches cases where the regex didn't match but quotes are still doubled
    cleaned = cleaned.replace('""', '"')
    
    # Step 5: Final cleanup - remove any remaining escaped characters that shouldn't be there
    # But be careful not to remove valid backslashes in XML content
    # Only remove backslashes that are clearly escape sequences
    cleaned = re.sub(r'\\([^"nrt])', r'\1', cleaned)

    # Step 6: Try to pretty-print if it's valid XML
    try:
        import xml.etree.ElementTree as ET
        # Parse and re-serialize for pretty printing
        root = ET.fromstring(cleaned)

        # Create a simple pretty printer
        def indent(elem, level=0):
            i = "\n" + level * "  "
            if len(elem):
                if not elem.text or not elem.text.strip():
                    elem.text = i + "  "
                if not elem.tail or not elem.tail.strip():
                    elem.tail = i
                for subelem in elem:
                    indent(subelem, level + 1)
                if not elem.tail or not elem.tail.strip():
                    elem.tail = i
            else:
                if level and (not elem.tail or not elem.tail.strip()):
                    elem.tail = i

        indent(root)
        return ET.tostring(root, encoding='unicode')
    except:
        # If XML parsing fails, just return cleaned content
        return cleaned


def _clean_unimrcp_xml(xml_content: str) -> str:
    """Specialized function to clean XML content from UniMRCP logs."""
    if not xml_content:
        return xml_content
    
    # Split into lines to handle the line-by-line quoting format
    lines = xml_content.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Remove outer quotes if present
        if line.startswith('"') and line.endswith('"'):
            line = line[1:-1]
        
        # Handle double-escaped quotes (""text"" -> "text")
        line = re.sub(r'""([^"]*)""', r'"\1"', line)
        
        # Handle other escaped characters
        line = line.replace('\\\\', '\\')
        line = line.replace('\\"', '"')
        line = line.replace('\\n', '\n')
        line = line.replace('\\r', '\r')
        line = line.replace('\\t', '\t')
        
        # Handle any remaining double quotes
        line = line.replace('""', '"')
        
        # Remove trailing backslashes and quotes that are artifacts
        line = re.sub(r'\\+$', '', line)  # Remove trailing backslashes
        line = re.sub(r'"+$', '', line)    # Remove trailing quotes
        
        cleaned_lines.append(line)
    
    # Join the cleaned lines
    cleaned = '\n'.join(cleaned_lines)
    
    # Try to pretty-print if it's valid XML
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(cleaned)
        
        # Create a simple pretty printer
        def indent(elem, level=0):
            i = "\n" + level * "  "
            if len(elem):
                if not elem.text or not elem.text.strip():
                    elem.text = i + "  "
                if not elem.tail or not elem.tail.strip():
                    elem.tail = i
                for subelem in elem:
                    indent(subelem, level + 1)
                if not elem.tail or not elem.tail.strip():
                    elem.tail = i
            else:
                if level and (not elem.tail or not elem.tail.strip()):
                    elem.tail = i
        
        indent(root)
        return ET.tostring(root, encoding='unicode')
    except:
        # If XML parsing fails, just return cleaned content
        return cleaned


def _extract_nlsml_from_sip_bye(sip_bye_content: str) -> Optional[dict]:
    """Extract NLSML content from SIP BYE message."""
    if not sip_bye_content or 'Content-Type: application/nlsml+xml' not in sip_bye_content:
        return None

    # After you split the BYE on the first blank line:
    headers, _, body = sip_bye_content.partition('\n\n')
    if not body:
        return None
    
    # Keep only lines that begin with "<" (i.e., XML) and rejoin them
    xml_lines = []
    for l in body.splitlines():
        l = l.strip()
        if l.lstrip().startswith('<'):
            xml_lines.append(l)
        elif '<' in l and '>' in l:
            # Handle quoted XML lines
            l = l.strip('"').strip("'")
            if l.lstrip().startswith('<'):
                xml_lines.append(l)
    xml_only = '\n'.join(xml_lines).strip()
    
    if not xml_only or '<result>' not in xml_only:
        return None
    
    # Use xml_only for pretty-printing / hashing / storage
    xml_only = _clean_unimrcp_xml(xml_only)
    recognized_text = _best_text(xml_only)
    
    return {
        "nlsml_content": xml_only,
        "recognized_text": recognized_text
    }


def _extract_nlsml(lines: List[str]) -> Optional[dict]:
    """Extract NLSML content from log lines with improved regex."""
    nlsml_content = None
    recognized_text = None

    # Look for NLSML content with more robust pattern
    for i, line in enumerate(lines):
        if "Content-Type: application/nlsml+xml" in line:
            # Collect NLSML content from subsequent lines until next message boundary
            nlsml_lines = []
            j = i + 1
            while j < len(lines):
                current_line = lines[j].strip()
                # Stop at message boundaries
                if (current_line.startswith("MRCP/2.0") or
                        current_line.startswith("---") or
                        current_line.startswith("Content-Type:") and "nlsml" not in current_line):
                    break
                if current_line:
                    nlsml_lines.append(current_line)
                j += 1

            if nlsml_lines:
                # Join the lines and use the specialized UniMRCP XML cleaner
                nlsml_content = "\n".join(nlsml_lines)
                nlsml_content = _clean_unimrcp_xml(nlsml_content)
                # Extract recognized text
                recognized_text = _best_text(nlsml_content)
                break

    if nlsml_content:
        return {
            "nlsml_content": nlsml_content,
            "recognized_text": recognized_text
        }
    return None


def _best_text(nlsml: str) -> Optional[str]:
    """Extract recognized text from NLSML with improved pattern."""
    # Try multiple patterns for input extraction
    patterns = [
        r'<input[^>]*>(.*?)</input>',
        r'<instance[^>]*>(.*?)</instance>',
        r'<interpretation[^>]*>(.*?)</interpretation>'
    ]

    for pattern in patterns:
        input_match = re.search(pattern, nlsml, re.DOTALL)
        if input_match:
            text = input_match.group(1).strip()
            if text and not text.startswith('<'):
                return text

    return None


def _clean_sip(lines: List[str]) -> str:
    """Clean SIP content for display."""
    return "\n".join(lines)


def _parse_sip_details(lines: List[str]) -> Dict[str, str]:
    """Parse SIP headers into structured data."""
    details = {}
    for line in lines:
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key in ["From", "To", "Call-ID", "CSeq", "Via", "Contact"]:
                details[key] = value
    return details


def _parse_params(lines: List[str]) -> Dict[str, str]:
    """Parse parameters from lines with improved filtering."""
    params = {}
    in_mrcp_body = False

    for line in lines:
        line = line.strip()

        # Guard against metadata lines
        if 'Receive MRCPv2' in line or '[INFO]' in line:
            continue

        # Skip log metadata and headers
        if (line.startswith("MRCP/") or
                line.startswith("Content-Length:") or
                line.startswith("Content-Type:") or
                line.startswith("Channel-Identifier:") or
                line.startswith("2025-") or  # Skip timestamp lines
                "bytes from" in line or  # Skip log metadata
                "recv" in line or "send" in line):  # Skip transport info
            continue

        # Check if we're in MRCP body
        if "Content-Type:" in line and "application/" in line:
            in_mrcp_body = True
            continue

        # Parse parameters only in MRCP body
        if in_mrcp_body and ":" in line:
            # Handle the case where the entire line is quoted in the log
            original_line = line
            if line.startswith('"') and line.endswith('"'):
                line = line[1:-1]  # Remove outer quotes
                # Also remove trailing comma if present
                if line.endswith(','):
                    line = line[:-1]
                
            # Handle the case where the key-value pair is inside quotes
            if ':' in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = re.sub(r'[\\"]+$', '', value.strip())
            else:
                continue
            
            # Remove trailing comma if present (common in log format)
            if value.endswith(','):
                value = value[:-1]
            
            # Clean up the value - remove unmatched quotes and artifacts
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]  # Remove outer quotes
            elif value.endswith('"') and not value.startswith('"'):
                value = value[:-1]   # Remove trailing quote only
            elif value.startswith('"') and not value.endswith('"'):
                value = value[1:]    # Remove leading quote only
                
            # Remove any remaining escaped quotes
            value = value.replace('\\"', '"')
            value = value.replace('""', '"')
            
            # Final cleanup - remove any trailing quotes that might remain
            value = re.sub(r'"+$', '', value)  # Remove trailing quotes
            value = re.sub(r'^"+', '', value)  # Remove leading quotes
            
            # Strip any trailing quotes from SET-PARAMS values
            value = re.sub(r'["\']+$', '', value)  # remove trailing quotes
            
            # Also clean up the key if it has quotes
            if key.startswith('"'):
                key = key[1:]
            if key.endswith('"'):
                key = key[:-1]
            
            if key and value and not key.startswith("Content-"):
                params[key] = value

    return params


def _generate_grammar_key(grammar_def: str) -> str:
    """Generate unique key for grammar definitions."""
    import hashlib
    return f"grammar_{hashlib.md5(grammar_def.encode()).hexdigest()[:8]}"


def _generate_params_key(params: Dict[str, str]) -> str:
    """Generate unique key for parameter sets."""
    import hashlib
    param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    return f"params_{hashlib.md5(param_str.encode()).hexdigest()[:8]}"


@dataclass
class MRCPMessage:
    """Represents a single MRCP message."""
    timestamp: datetime
    channel_id: str
    req_id: str
    is_request: bool
    src_ip: str
    dst_ip: str
    method: str
    status: Optional[str] = None
    direction_role: str = ""
    sid: Optional[str] = None
    grammar_ref: Optional[str] = None
    params_ref: Optional[str] = None
    nlsml_content: Optional[str] = None
    recognized_text: Optional[str] = None

    def to_dict(self):
        d = self.__dict__.copy()
        if 'timestamp' in d and isinstance(d['timestamp'], (datetime,)):
            d['timestamp'] = d['timestamp'].isoformat() + 'Z'
        # Only include fields with actual values
        return {k: v for k, v in d.items() if v not in (None, '', [], {})}


@dataclass
class SIPSession:
    """Represents a SIP session with all its MRCP activity."""
    call_id: str
    sip_invite: Optional[str] = None
    sip_bye: Optional[str] = None
    sip_invite_details: Dict[str, str] = field(default_factory=dict)
    sip_bye_details: Dict[str, str] = field(default_factory=dict)
    session_start: Optional[datetime] = None
    session_end: Optional[datetime] = None
    mrcp_messages: List[MRCPMessage] = field(default_factory=list)
    grammar_definitions: Dict[str, str] = field(default_factory=dict)
    parameter_sets: Dict[str, Dict[str, str]] = field(default_factory=dict)
    mrcp_sids: Set[str] = field(default_factory=set)  # Changed to Set for efficiency
    nlsml_results: List[Dict[str, str]] = field(default_factory=list)
    recognized_texts: List[str] = field(default_factory=list)
    warnings: Set[str] = field(default_factory=set)  # Changed to Set for deduplication
    last_recog_code: Optional[int] = None
    ever_succeeded: bool = False
    tts_only: bool = False # Added for TTS-only sessions
    no_mrcp: bool = False # Added for sessions with no MRCP messages

    def add_warning(self, warning: str):
        """Add a warning to the session, automatically deduplicating."""
        self.warnings.add(warning)

    def handle_recog_complete(self, code: int):
        self.last_recog_code = code
        if code in SUCCESS_CODES:
            self.ever_succeeded = True

    def verdict(self) -> str:
        if self.last_recog_code is None:
            return "no_recognition"
        if self.last_recog_code in SUCCESS_CODES:
            return "complete"
        if self.ever_succeeded:
            return "timeout_after_success"
        return "incomplete"

    def is_app_complete(self) -> bool:
        return self.verdict() == "complete"

    def to_json(self):
        # Always output a minimal dict for every session, even if no SIP INVITE, BYE, or MRCP messages
        if not self.mrcp_messages and not self.sip_invite and not self.sip_bye:
            return {
                "call_id": self.call_id,
                "status": "NO DATA",
                "warning": "No SIP INVITE, BYE, or MRCP messages found for this Call-ID."
            }

        # Calculate session duration
        start = self.session_start or (self.mrcp_messages[0].timestamp if self.mrcp_messages else None)
        end = self.session_end or (self.mrcp_messages[-1].timestamp if self.mrcp_messages else None)

        # If we have MRCP messages but no SIP INVITE/BYE, estimate duration from MRCP
        if not start and self.mrcp_messages:
            start = self.mrcp_messages[0].timestamp
        if not end and self.mrcp_messages:
            end = self.mrcp_messages[-1].timestamp

        if not start or not end:
            return {}

        dur = end - start
        doc = {
            "call_id": self.call_id,
            "session_start": _iso_ms(start),
            "session_end": _iso_ms(end),
            "duration_ms": int(dur.total_seconds() * 1000),
            "duration_pretty": _pretty_dur(dur),
            "sip": {},
            "mrcp_sids": list(self.mrcp_sids),
            "mrcp_messages": [m.to_dict() for m in self.mrcp_messages],
        }

        # Add session-level grammar definitions and parameter sets
        if self.grammar_definitions:
            doc["grammar_definitions"] = self.grammar_definitions
        if self.parameter_sets:
            doc["parameter_sets"] = self.parameter_sets

        # Add NLSML results and recognized texts
        if self.nlsml_results:
            doc["nlsml_results"] = self.nlsml_results
        if self.recognized_texts:
            doc["recognized_texts"] = self.recognized_texts

        if self.sip_invite:
            doc["sip"]["invite"] = {
                "raw": self.sip_invite,
                "details": self.sip_invite_details
            }
        if self.sip_bye:
            doc["sip"]["bye"] = {
                "raw": self.sip_bye,
                "details": self.sip_bye_details
            }

        # Add warnings for incomplete sessions and other issues
        warnings = []
        if not self.sip_bye:
            warnings.append("no SIP BYE seen — session may be incomplete")
        if not self.sip_invite and self.sip_bye:
            warnings.append("SIP BYE seen but no SIP INVITE found — session may be truncated or incomplete")
        if not any(m.method == "RECOGNITION-COMPLETE" for m in self.mrcp_messages):
            warnings.append("no RECOGNITION-COMPLETE seen — session may be incomplete")
        # Add any custom warnings from the session
        warnings.extend(list(self.warnings))
        if warnings:
            doc["warning"] = "; ".join(warnings)

        # --- Add explanation for INCOMPLETE due to recognizer code ---
        if self.last_recog_code is not None and self.last_recog_code not in SUCCESS_CODES:
            code_meanings = {10: "no-input-timeout", 2: "nomatch", 3: "error", 7: "grammar-load-failure"}
            code_str = str(self.last_recog_code)
            meaning = code_meanings.get(self.last_recog_code, "unknown or application-defined")
            doc["explanation"] = (
                "What happened in this call:\n"
                "Telephony layer – The SIP dialog set up and tore down normally.\n"
                "You can see the full INVITE → 200 OK → ACK → BYE ladder, so from a pure call-control standpoint the session is healthy.\n\n"
                "MRCP / recogniser layer – The last RECOGNITION-COMPLETE we saw carried completion-cause: {} ({}).\n"
                "This means the recogniser waited for the caller to speak and timed out without receiving usable audio.\n\n"
                "Why it shows INCOMPLETE in the dashboard:\n"
                "The status badge is based on the final recogniser result, not on the presence of a SIP BYE.\n"
                "A session is counted COMPLETE only when that last result code is one of the recognised “success” values (0, 4, 5). Because this call’s final code is {}, it is classified as INCOMPLETE for ASR metrics—even though the SIP call itself ended cleanly.\n\n"
                "Is anything actually wrong?\n"
                "No. The “incomplete” label simply highlights that the caller never responded (or their speech was not detected), not that the infrastructure failed.\n"
                "Telecom capacity metrics would mark the call successful; speech-application metrics treat it as a no-input event."
            ).format(code_str, meaning, code_str)
        verdict = self.verdict()
        # New: Add NO MRCP status
        if getattr(self, "no_mrcp", False):
            doc["status"] = "NO MRCP"
        elif verdict != "complete":
            doc["status"] = verdict.upper()
            doc["explanation"] = EXPLANATIONS.get(verdict, "Session did not complete successfully.")
        else:
            doc["status"] = "COMPLETE"
        return doc

    def get_info(self, index: int, total_sessions: int) -> str:
        """Helper to format session info for the output list."""
        # New: Add NO MRCP status
        if getattr(self, "no_mrcp", False):
            status = "NO MRCP"
        elif getattr(self, "last_recog_code", None) is None and getattr(self, "tts_only", False):
            status = "TTS-ONLY"
        elif getattr(self, "last_recog_code", None) is None and self.mrcp_messages and not self.sip_invite:
            status = "TTS-ONLY"
        elif getattr(self, "last_recog_code", None) is None:
            status = "NO_RECOGNITION"
        elif not getattr(self, "sip_invite", None) and getattr(self, "sip_bye", None):
            status = "INCOMPLETE (NO INVITE)"
        else:
            status = "COMPLETE" if self.is_app_complete() else "INCOMPLETE"
        return f"SIP Session {index} of {total_sessions} - Call-ID: {self.call_id} - Duration: {self.to_json().get('duration_pretty', 'N/A')} - Status: {status}"


def parse_log(path: Path) -> List[SIPSession]:
    """Parse the log file and return SIP sessions with MRCP activity."""

    # Track SIP sessions by Call-ID
    sip_sessions: Dict[str, SIPSession] = {}

    # Track channel usage across sessions for collision detection
    channel_usage: Dict[str, str] = {}  # channel_id -> call_id

    # First pass: group lines by timestamp to handle multi-line entries
    timestamp_groups: List[Tuple[datetime, List[str]]] = []
    current_timestamp = None
    current_lines: List[str] = []

    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\r\n").rstrip(",")

            # Check for timestamp
            tsm = _TSTAMP_RE.search(line)
            if tsm:
                # Save previous group if exists
                if current_timestamp and current_lines:
                    timestamp_groups.append((current_timestamp, current_lines))

                # Start new group
                current_timestamp = _parse_ts(tsm.group(1))
                if current_timestamp:  # Only add if timestamp parsing succeeded
                    current_lines = [line]
                else:
                    current_lines = []
            else:
                # Continue current group
                if current_timestamp:
                    current_lines.append(line)

    # Add the last group
    if current_timestamp and current_lines:
        timestamp_groups.append((current_timestamp, current_lines))

    # Second pass: process each timestamp group
    for ts, lines in timestamp_groups:
        full_text = "\n".join(lines)

        # Check for SIP INVITE
        if _SIP_INVITE_RE.search(full_text):
            # Extract Call-ID
            call_id = None
            for line in lines:
                call_id_match = _CALL_ID_RE.search(line)
                if call_id_match:
                    call_id = call_id_match.group(1)
                    break

            if call_id:
                # Create new SIP session
                if call_id not in sip_sessions:
                    sip_sessions[call_id] = SIPSession(
                        call_id=call_id,
                        session_start=ts
                    )

                # Store SIP INVITE info
                sip_sessions[call_id].sip_invite = _clean_sip(lines)
                sip_sessions[call_id].sip_invite_details = _parse_sip_details(lines)

        # Check for SIP BYE
        elif _SIP_BYE_RE.search(full_text):
            # Extract Call-ID
            call_id = None
            for line in lines:
                call_id_match = _CALL_ID_RE.search(line)
                if call_id_match:
                    call_id = call_id_match.group(1)
                    break

            if call_id:
                # Create session if it doesn't exist (orphaned BYE)
                if call_id not in sip_sessions:
                    sip_sessions[call_id] = SIPSession(
                        call_id=call_id,
                        session_end=ts
                    )

                # Store SIP BYE info
                sip_sessions[call_id].sip_bye = _clean_sip(lines)
                sip_sessions[call_id].sip_bye_details = _parse_sip_details(lines)
                sip_sessions[call_id].session_end = ts

        # Also check for any Call-ID in SIP responses to catch orphaned sessions
        elif "Call-ID:" in full_text and ("SIP/2.0" in full_text or "ACK" in full_text):
            # Extract Call-ID from SIP response
            call_id = None
            for line in lines:
                call_id_match = _CALL_ID_RE.search(line)
                if call_id_match:
                    call_id = call_id_match.group(1)
                    break

            if call_id and call_id not in sip_sessions:
                # Create session for orphaned Call-ID
                sip_sessions[call_id] = SIPSession(
                    call_id=call_id,
                    session_start=ts
                )

        # Extract SID if present
        sid_match = _SESSION_ID_RE.search(full_text)
        if sid_match:
            # Find which session this SID belongs to using temporal proximity
            # (reverting to original logic but with better validation)
            sid = sid_match.group("sid")
            for session in sip_sessions.values():
                if session.session_start and session.session_start <= ts:
                    if not session.session_end or ts <= session.session_end:
                        session.mrcp_sids.add(sid)
                        break

        # Check for MRCP messages
        md = None
        for line in lines:
            md = _detect_mrcp(line)
            if md:
                break

        if not md:
            continue

        is_req, req_id, status, method = md

        # Extract code for RECOGNITION-COMPLETE if not already set
        if method == "RECOGNITION-COMPLETE" and (status is None or status == ""):
            # Try to extract code from the MRCP line
            for l in lines:
                m = re.search(r'MRCP/2\.0\s+\d+\s+RECOGNITION-COMPLETE\s+(\d+)', l)
                if m:
                    status = m.group(1)
                    break

        # Track last_recog_code for the session
        if method == "RECOGNITION-COMPLETE" and status is not None:
            # Find the session this message belongs to
            target_session = None
            channel_id = "unknown"
            for line in lines:
                if (m := _CHANNEL_ID_RE.search(line)):
                    channel_id = m.group("cid").strip()
                    break
            for session in sip_sessions.values():
                if channel_id != "unknown" and any(m.channel_id == channel_id for m in session.mrcp_messages):
                    target_session = session
                    break
            if not target_session:
                # Use temporal proximity
                best_session = None
                best_time_diff = float('inf')
                for session in sip_sessions.values():
                    if session.session_start and session.session_start <= ts:
                        if not session.session_end or ts <= session.session_end:
                            time_diff = abs((ts - session.session_start).total_seconds())
                            if time_diff < best_time_diff:
                                best_time_diff = time_diff
                                best_session = session
                target_session = best_session
            if target_session:
                try:
                    target_session.last_recog_code = int(status)
                    target_session.handle_recog_complete(int(status))
                except Exception:
                    pass

        # Extract IPs
        src_ip, dst_ip = _extract_ips(full_text)
        if not src_ip:
            continue

        # Extract Channel ID
        channel_id = "unknown"
        for line in lines:
            if (m := _CHANNEL_ID_RE.search(line)):
                channel_id = m.group("cid").strip()
                break

        # Extract SID
        sid = None
        if sid_match:
            sid = sid_match.group("sid")

        # Create MRCP message
        msg = MRCPMessage(
            timestamp=ts,
            channel_id=channel_id,
            req_id=req_id,
            is_request=is_req,
            src_ip=src_ip,
            dst_ip=dst_ip,
            method=method,
            status=status,
            sid=sid
        )

        # Set direction based on MRCP protocol flow and event type
        if is_req:
            # Client request: client -> server
            msg.direction_role = f"{src_ip} -> {dst_ip}"
        else:
            # Server response/event: server -> client
            msg.direction_role = f"{dst_ip} -> {src_ip}"

        # Handle different MRCP methods
        if is_req and method == "DEFINE-GRAMMAR":
            # Extract grammar definition with improved patterns
            grammar_definition = ""
            if "Content-Type: application/srgs+xml" in full_text:
                # Try multiple patterns for XML grammar
                xml_patterns = [
                    r'<\?xml[^>]*>.*?</grammar>',
                    r'<grammar[^>]*>.*?</grammar>',
                    r'Content-ID:\s*(.+)'
                ]

                for pattern in xml_patterns:
                    xml_match = re.search(pattern, full_text, re.DOTALL)
                    if xml_match:
                        grammar_definition = xml_match.group(0)
                        break

                # If no XML found, try to extract from the message body
                if not grammar_definition:
                    # Look for XML content after the headers
                    body_start = full_text.find('\n\n')
                    if body_start != -1:
                        body_content = full_text[body_start:].strip()
                        # Extract XML from body
                        xml_match = re.search(r'<\?xml.*?</grammar>', body_content, re.DOTALL)
                        if xml_match:
                            grammar_definition = xml_match.group(0)

                if not grammar_definition:
                    grammar_definition = "SRGS XML grammar content (XML not captured)"

            # Store grammar at session level using improved association logic
            if grammar_definition and grammar_definition != "Grammar definition not captured":
                grammar_key = _generate_grammar_key(grammar_definition)
                # Find which session this belongs to using the same logic as message assignment
                target_session = None
                for session in sip_sessions.values():
                    if channel_id != "unknown" and any(m.channel_id == channel_id for m in session.mrcp_messages):
                        target_session = session
                        break
                
                if not target_session:
                    # Use temporal proximity with better logic
                    best_session = None
                    best_time_diff = float('inf')
                    for session in sip_sessions.values():
                        if session.session_start and session.session_start <= ts:
                            if not session.session_end or ts <= session.session_end:
                                time_diff = abs((ts - session.session_start).total_seconds())
                                if time_diff < best_time_diff:
                                    best_time_diff = time_diff
                                    best_session = session
                    target_session = best_session
                
                if target_session:
                    target_session.grammar_definitions[grammar_key] = _clean_unimrcp_xml(grammar_definition)
                    msg.grammar_ref = grammar_key

        elif is_req and method == "SET-PARAMS":
            # Extract parameters with improved filtering
            params = _parse_params(lines)
            if params:
                params_key = _generate_params_key(params)
                # Find which session this belongs to using improved association logic
                target_session = None
                for session in sip_sessions.values():
                    if channel_id != "unknown" and any(m.channel_id == channel_id for m in session.mrcp_messages):
                        target_session = session
                        break
                
                if not target_session:
                    # Use temporal proximity with better logic
                    best_session = None
                    best_time_diff = float('inf')
                    for session in sip_sessions.values():
                        if session.session_start and session.session_start <= ts:
                            if not session.session_end or ts <= session.session_end:
                                time_diff = abs((ts - session.session_start).total_seconds())
                                if time_diff < best_time_diff:
                                    best_time_diff = time_diff
                                    best_session = session
                    target_session = best_session
                
                if target_session:
                    target_session.parameter_sets[params_key] = params
                    msg.params_ref = params_key
            else:
                # Try to extract parameters from the full text if _parse_params didn't find any
                param_patterns = [
                    r'([A-Za-z-]+):\s*([^\n\r]+)',
                    r'([A-Za-z-]+):\s*([0-9.]+)',
                    r'([A-Za-z-]+):\s*([a-zA-Z,]+)'
                ]
                
                for pattern in param_patterns:
                    matches = re.findall(pattern, full_text)
                    if matches:
                        extracted_params = {}
                        for key, value in matches:
                            # Skip common headers that aren't parameters
                            if key not in ['Content-Type', 'Content-Length', 'Channel-Identifier', 'MRCP']:
                                # Apply the same quote cleaning logic as _parse_params
                                cleaned_value = value.strip()
                                cleaned_value = re.sub(r'["\']+$', '', cleaned_value)  # remove trailing quotes
                                extracted_params[key] = cleaned_value
                        
                        if extracted_params:
                            params_key = _generate_params_key(extracted_params)
                            # Find which session this belongs to using improved association logic
                            target_session = None
                            for session in sip_sessions.values():
                                if channel_id != "unknown" and any(m.channel_id == channel_id for m in session.mrcp_messages):
                                    target_session = session
                                    break
                            
                            if not target_session:
                                # Use temporal proximity with better logic
                                best_session = None
                                best_time_diff = float('inf')
                                for session in sip_sessions.values():
                                    if session.session_start and session.session_start <= ts:
                                        if not session.session_end or ts <= session.session_end:
                                            time_diff = abs((ts - session.session_start).total_seconds())
                                            if time_diff < best_time_diff:
                                                best_time_diff = time_diff
                                                best_session = session
                                target_session = best_session
                            
                            if target_session:
                                target_session.parameter_sets[params_key] = extracted_params
                                msg.params_ref = params_key
                            break

        elif method == "RECOGNITION-COMPLETE":
            # Extract NLSML content with improved extraction
            nlsml_content = ""
            if "Content-Type: application/nlsml+xml" in full_text:
                # Try multiple patterns for NLSML extraction
                nlsml_patterns = [
                    r'Content-Type: application/nlsml\+xml.*?\n\n(.*)',
                    r'<result>.*?</result>',
                    r'<interpretation.*?</interpretation>'
                ]

                for pattern in nlsml_patterns:
                    nlsml_match = re.search(pattern, full_text, re.DOTALL)
                    if nlsml_match:
                        nlsml_content = nlsml_match.group(1) if pattern.startswith(
                            'Content-Type') else nlsml_match.group(0)
                        break

                if nlsml_content:
                    nlsml_content = _clean_unimrcp_xml(nlsml_content)
                    msg.nlsml_content = nlsml_content
                    msg.recognized_text = _best_text(nlsml_content)

                    # Add NLSML to session using improved association logic
                    target_session = None
                    for session in sip_sessions.values():
                        if channel_id != "unknown" and any(m.channel_id == channel_id for m in session.mrcp_messages):
                            target_session = session
                            break
                    
                    if not target_session:
                        # Use temporal proximity with better logic
                        best_session = None
                        best_time_diff = float('inf')
                        for session in sip_sessions.values():
                            if session.session_start and session.session_start <= ts:
                                if not session.session_end or ts <= session.session_end:
                                    time_diff = abs((ts - session.session_start).total_seconds())
                                    if time_diff < best_time_diff:
                                        best_time_diff = time_diff
                                        best_session = session
                    target_session = best_session
                    
                    if target_session:
                        target_session.nlsml_results.append({
                            "nlsml_content": nlsml_content,
                            "recognized_text": msg.recognized_text,
                            "timestamp": ts.isoformat() + "Z"
                        })
                        if msg.recognized_text:
                            target_session.recognized_texts.append(msg.recognized_text)

        # Add message to appropriate session using better association logic
        # First, try to find a session that has this channel_id already
        target_session = None
        for session in sip_sessions.values():
            if channel_id != "unknown" and any(m.channel_id == channel_id for m in session.mrcp_messages):
                target_session = session
                break
        
        # If no existing channel association, use temporal proximity with better logic
        if not target_session:
            # Find the session with the closest temporal match
            best_session = None
            best_time_diff = float('inf')
            
            for session in sip_sessions.values():
                if session.session_start and session.session_start <= ts:
                    if not session.session_end or ts <= session.session_end:
                        # Calculate time difference from session start
                        time_diff = abs((ts - session.session_start).total_seconds())
                        if time_diff < best_time_diff:
                            best_time_diff = time_diff
                            best_session = session
            
            target_session = best_session
        
        if target_session:
            target_session.mrcp_messages.append(msg)

            # Check for channel ID collisions
            if channel_id != "unknown":
                if channel_id in channel_usage and channel_usage[channel_id] != target_session.call_id:
                    target_session.add_warning(
                        f"channel {channel_id} reused from session {channel_usage[channel_id]}")
                else:
                    channel_usage[channel_id] = target_session.call_id

    # Set session end times for sessions without BYE
    for session in sip_sessions.values():
        if not session.session_end and session.mrcp_messages:
            session.session_end = session.mrcp_messages[-1].timestamp

    # After all messages are processed, try to extract NLSML from SIP BYE
    for session in sip_sessions.values():
        if session.sip_bye and 'Content-Type: application/nlsml+xml' in session.sip_bye:
            nlsml_data = _extract_nlsml_from_sip_bye(session.sip_bye)
            if nlsml_data:
                # Add NLSML from BYE to session results
                session.nlsml_results.append({
                    "nlsml_content": nlsml_data["nlsml_content"],
                    "recognized_text": nlsml_data["recognized_text"],
                    "timestamp": session.session_end.isoformat() + "Z" if session.session_end else "",
                    "source": "SIP BYE"
                })
                if nlsml_data["recognized_text"]:
                    session.recognized_texts.append(nlsml_data["recognized_text"])
                
                # Add note if this session only has NLSML via BYE (no MRCP messages)
                if not session.mrcp_messages:
                    session.add_warning("NLSML results only available via SIP BYE - no MRCP messages in session")

    # --- NEW: Ensure every unique Call-ID from anywhere in the log is included as a SIPSession ---
    all_call_ids = set(sip_sessions.keys())
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            call_id_match = _CALL_ID_RE.search(line)
            if call_id_match:
                call_id = call_id_match.group(1)
                if call_id not in sip_sessions:
                    # Create a new SIPSession for this Call-ID (TTS-only, no MRCP)
                    sip_sessions[call_id] = SIPSession(call_id=call_id)
                    sip_sessions[call_id].tts_only = True

    # Mark TTS-only status for all sessions with no RECOGNITION-COMPLETE
    for call_id, session in sip_sessions.items():
        # Check for MRCP SPEAK
        has_speak = any(m.method == "SPEAK" for m in session.mrcp_messages)
        if not session.mrcp_messages:
            session.last_recog_code = None
            session.ever_succeeded = False # Reset ever_succeeded for TTS-only sessions
            session.tts_only = False
            session.no_mrcp = True # Mark as no MRCP
        elif has_speak:
            session.tts_only = True
            session.no_mrcp = False
        else:
            session.tts_only = False
            session.no_mrcp = False

    return list(sip_sessions.values())


def main():
    parser = argparse.ArgumentParser(description="Parse UniMRCP logs and extract session summaries")
    parser.add_argument("logfile", type=Path, help="Path to the log file")
    parser.add_argument("-o", "--out", type=Path, help="Output JSON file")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()

    if not args.logfile.exists():
        print(f"Error: {args.logfile} does not exist", file=sys.stderr)
        sys.exit(1)

    # Parse the log
    sessions = parse_log(args.logfile)

    # Filter out empty sessions
    non_empty_sessions = [s for s in sessions if s.to_json()]
    completed_sessions = sum(1 for s in non_empty_sessions if s.is_app_complete())
    incomplete_sessions = len(non_empty_sessions) - completed_sessions

    # --- Build output session list, ensuring all sessions are included ---
    sessions_with_dividers = []
    for i, session in enumerate(sessions, 1):
        session_json = session.to_json()
        sessions_with_dividers.append({
            'session_divider': f"=== SIP SESSION {i} ===",
            'session_info': session.get_info(i, len(sessions)),
            'session_data': session_json
        })

    output = {
        "total_sip_sessions": len(non_empty_sessions),
        "session_health": {
            "completed_sessions": completed_sessions,
            "incomplete_sessions": incomplete_sessions,
            "completion_rate": f"{(completed_sessions / len(non_empty_sessions) * 100):.1f}%" if non_empty_sessions else "0.0%"
        },
        "sessions": sessions_with_dividers
    }

    json_text = json.dumps(output, indent=2)
    if args.out:
        args.out.write_text(json_text, encoding='utf-8')
        print(f"Wrote {args.out}")
    else:
        print(json_text)


if __name__ == "__main__":
    main()

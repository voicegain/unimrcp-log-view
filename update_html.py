#!/usr/bin/env python3
"""
Update HTML report with JSON data
WARNING: Do NOT delete the HTML template file without explicit user confirmation!
"""

import json
import re
import argparse

def update_html_with_json(json_data, html_file="report.html"):
    """Update the HTML file with new JSON data."""
    
    # Read the current HTML file
    with open(html_file, 'r') as f:
        html_content = f.read()
    
    # Find the const data = ... section and replace it
    pattern = r'const data = \n\{[^}]*"sessions": \[[^\]]*\][^}]*\};'
    replacement = f'const data = \n{json.dumps(json_data, indent=2, ensure_ascii=False)};'
    
    # Replace the data section
    new_html = re.sub(pattern, replacement, html_content, flags=re.DOTALL)
    
    # Write the updated HTML file
    with open(html_file, 'w') as f:
        f.write(new_html)
    
    print(f"Updated {html_file} with new data")

def main():
    parser = argparse.ArgumentParser(description="Update HTML report with JSON data")
    parser.add_argument('--output', '-o', type=str, default='report.html', help='Output HTML file (default: report.html)')
    args = parser.parse_args()

    # Read the JSON data
    with open('summary.json', 'r') as f:
        data = json.load(f)
    
    # Create the HTML report with proper JavaScript escaping
    html_file = args.output
    
    # Use raw strings to avoid f-string issues with JavaScript template literals
    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UniMRCP Log Analysis Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
            color: #333;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }}
        .header p {{
            margin: 10px 0 0 0;
            opacity: 0.9;
            font-size: 1.1em;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            text-align: center;
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }}
        .stat-label {{
            color: #666;
            margin-top: 5px;
        }}
        .sessions {{
            padding: 30px;
        }}
        .session {{
            margin-bottom: 30px;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            overflow: hidden;
        }}
        .session-header {{
            background: #f8f9fa;
            padding: 15px 20px;
            border-bottom: 1px solid #e0e0e0;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .session-header:hover {{
            background: #e9ecef;
        }}
        .session-title {{
            font-weight: 600;
            color: #495057;
        }}
        .session-status {{
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 500;
        }}
        .status-complete {{
            background: #d4edda;
            color: #155724;
        }}
        .status-incomplete {{
            background: #f8d7da;
            color: #721c24;
        }}
        .status-nomrcp {{
            background: #e3f0fb;
            color: #1565c0;
        }}
        .session-content {{
            padding: 20px;
            display: none;
        }}
        .session-content.active {{
            display: block;
        }}
        .section {{
            margin-bottom: 25px;
        }}
        .section-title {{
            font-size: 1.2em;
            font-weight: 600;
            color: #495057;
            margin-bottom: 15px;
            padding-bottom: 8px;
            border-bottom: 2px solid #667eea;
        }}
        .message {{
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 6px;
            margin-bottom: 10px;
            overflow: hidden;
        }}
        .message-header {{
            background: #e9ecef;
            padding: 10px 15px;
            font-weight: 500;
            color: #495057;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .message-header:hover {{
            background: #dee2e6;
        }}
        .message-content {{
            padding: 15px;
            display: none;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            background: white;
            border-top: 1px solid #e9ecef;
        }}
        .message-content.active {{
            display: block;
        }}
        .timestamp {{
            color: #6c757d;
            font-size: 0.85em;
        }}
        .method {{
            font-weight: 600;
            color: #495057;
        }}
        .direction {{
            color: #6c757d;
            font-size: 0.85em;
        }}
        .nlsml-content {{
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 4px;
            padding: 10px;
            margin-top: 10px;
            font-family: 'Courier New', monospace;
            font-size: 0.85em;
            white-space: pre-wrap;
        }}
        .recognized-text {{
            background: #e7f3ff;
            border: 1px solid #b3d9ff;
            border-radius: 4px;
            padding: 10px;
            margin-top: 10px;
            font-style: italic;
        }}
        .grammar-def {{
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 4px;
            padding: 10px;
            margin-top: 10px;
            font-family: 'Courier New', monospace;
            font-size: 0.85em;
            white-space: pre-wrap;
        }}
        .params {{
            background: #d1ecf1;
            border: 1px solid #bee5eb;
            border-radius: 4px;
            padding: 10px;
            margin-top: 10px;
        }}
        .param-item {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 5px;
        }}
        .param-name {{
            font-weight: 500;
            color: #495057;
        }}
        .param-value {{
            color: #6c757d;
        }}
        .toggle-icon {{
            transition: transform 0.2s;
        }}
        .toggle-icon.rotated {{
            transform: rotate(90deg);
        }}
        .search-box {{
            margin: 20px 30px 0 30px;
            padding: 15px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }}
        .search-input {{
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 1em;
        }}
        .search-input:focus {{
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.2);
        }}
        .highlight {{
            background-color: yellow;
            font-weight: bold;
        }}
        .no-results {{
            text-align: center;
            padding: 40px;
            color: #6c757d;
            font-style: italic;
        }}
        .filter-box {{
            margin: 20px 30px 0 30px;
            padding: 15px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }}
        .filter-checkbox {{
            display: flex;
            align-items: center;
            cursor: pointer;
            font-weight: 500;
            color: #495057;
        }}
        .filter-checkbox input[type="checkbox"] {{
            margin-right: 10px;
            transform: scale(1.2);
        }}
        @media (max-width: 768px) {{
            .container {{
                margin: 10px;
                border-radius: 5px;
            }}
            .header {{
                padding: 20px;
            }}
            .header h1 {{
                font-size: 2em;
            }}
            .stats {{
                grid-template-columns: 1fr;
                padding: 20px;
            }}
            .sessions {{
                padding: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>UniMRCP Log Analysis Report</h1>
            <p>Interactive analysis of SIP and MRCP message flows</p>
        </div>
        
        <div class="search-box">
            <input type="text" id="searchInput" class="search-input" placeholder="Search for text, IP addresses, methods, or any content...">
        </div>
        
        <div class="filter-box">
            <label class="filter-checkbox">
                <input type="checkbox" id="hideNoMrcp" onchange="toggleNoMrcpFilter()">
                Hide NO MRCP sessions <span style="font-weight: normal; color: #888;">(SIP‑only sessions — calls that established signalling but never invoked an MRCP recognizer channel (no speech‑processing traffic).)</span>
            </label>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-number" id="ttsSessions">-</div>
                <div class="stat-label">Complete TTS-only Sessions</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="asrSessions">-</div>
                <div class="stat-label">Complete ASR Sessions</div>
            </div>
        </div>
        
        <div class="sessions" id="sessionsContainer">
            <!-- Sessions will be populated here -->
        </div>
    </div>

    <script>
        const data = {json.dumps(data, indent=2, ensure_ascii=False)};

        // Initialize the report
        document.addEventListener('DOMContentLoaded', function() {{
            updateStats();
            renderSessions();
            setupSearch();
        }});

        function updateStats() {{
            document.getElementById('ttsSessions').textContent = data.stats ? data.stats.tts_sessions : '-';
            document.getElementById('asrSessions').textContent = data.stats ? data.stats.asr_sessions : '-';
        }}

        function getSessionCompleteness(session) {{
            const recogMessages = (session.mrcp_messages || []).filter(m => m.method === 'RECOGNITION-COMPLETE');
            if (recogMessages.length === 0) {{
                return {{ complete: false, code: null }};
            }}
            const lastRecog = recogMessages[recogMessages.length - 1];
            const code = lastRecog.status !== undefined ? parseInt(lastRecog.status, 10) : null;
            const SUCCESS_CODES = [0, 4, 5];
            return {{ complete: SUCCESS_CODES.includes(code), code }};
        }}

        function renderSessions() {{
            const container = document.getElementById('sessionsContainer');
            container.innerHTML = '';

            let completedCount = 0;
            let incompleteCount = 0;

            data.sessions.forEach((sessionData, sessionIndex) => {{
                const session = sessionData.session_data;
                const statusString = (sessionData.session_info || '').toUpperCase();
                // Use backend status string as the primary source of truth
                if (statusString.includes('INCOMPLETE') || statusString.includes('TTS-ONLY')) {{
                    incompleteCount++;
                }} else if (statusString.includes('COMPLETE')) {{
                    completedCount++;
                }} else {{
                    // fallback to MRCP completeness if needed
                    const {{ complete }} = getSessionCompleteness(session);
                    if (complete) completedCount++; else incompleteCount++;
                }}
                const sessionDiv = document.createElement('div');
                sessionDiv.className = 'session';
                sessionDiv.id = `session-${{sessionIndex}}`;

                // Determine status class and text for display
                let statusClass = 'status-incomplete';
                let statusText = 'INCOMPLETE';
                if (statusString.includes('NO MRCP')) {{
                    statusClass = 'status-nomrcp';
                    statusText = 'NO MRCP';
                }} else if (statusString.includes('TTS-ONLY')) {{
                    statusClass = 'status-incomplete';
                    statusText = 'TTS-ONLY';
                }} else if (statusString.includes('INCOMPLETE')) {{
                    statusClass = 'status-incomplete';
                    statusText = 'INCOMPLETE';
                }} else if (statusString.includes('COMPLETE')) {{
                    statusClass = 'status-complete';
                    statusText = 'COMPLETE';
                }}

                sessionDiv.innerHTML = 
                    `<div class="session-header" onclick="toggleSession(${{sessionIndex}})">
                        <div class="session-title">${{sessionData.session_info}}</div>
                        <div class="session-status ${{statusClass}}">${{statusText}}</div>
                    </div>
                    <div class="session-content" id="session-content-${{sessionIndex}}">
                        ${{renderSessionContent(session, sessionIndex)}}
                    </div>`;

                if (session.explanation) {{
                  const explanationSection = document.createElement('details');
                  explanationSection.className = 'session-explanation';
                  const summary = document.createElement('summary');
                  summary.textContent = 'Why is this session marked INCOMPLETE?';
                  explanationSection.appendChild(summary);
                  const pre = document.createElement('pre');
                  pre.textContent = session.explanation;
                  explanationSection.appendChild(pre);
                  sessionDiv.appendChild(explanationSection);
                }}

                container.appendChild(sessionDiv);
            }});

            // Stats are now updated separately via updateStats()
        }}

        function renderSessionContent(session, sessionIndex) {{
            let html = '';

            // SIP Messages
            if (session.sip) {{
                html += '<div class="section">';
                html += '<div class="section-title">SIP Messages</div>';
                
                if (session.sip.invite) {{
                    html += createMessageHTML('SIP INVITE', session.sip.invite, `sip-invite-${{sessionIndex}}`);
                }}
                
                if (session.sip.bye) {{
                    html += createMessageHTML('SIP BYE', session.sip.bye, `sip-bye-${{sessionIndex}}`);
                }}
                
                html += '</div>';
            }}

            // MRCP Messages
            if (session.mrcp_messages && session.mrcp_messages.length > 0) {{
                html += '<div class="section">';
                html += '<div class="section-title">MRCP Messages</div>';
                
                session.mrcp_messages.forEach((msg, msgIndex) => {{
                    const messageType = msg.is_request ? 'REQUEST' : 'RESPONSE';
                    const title = `${{msg.method}} (${{messageType}}) - ${{msg.channel_id}}`;
                    html += createMRCPMessageHTML(title, msg, `mrcp-${{sessionIndex}}-${{msgIndex}}`);
                }});
                
                html += '</div>';
            }}

            // Grammar Definitions
            if (session.grammar_definitions && Object.keys(session.grammar_definitions).length > 0) {{
                html += '<div class="section">';
                html += '<div class="section-title">Grammar Definitions</div>';
                
                Object.entries(session.grammar_definitions).forEach(([ref, grammar]) => {{
                    html += `<div class="grammar-def"><strong>${{ref}}:</strong><br>${{escapeHtml(grammar)}}</div>`;
                }});
                
                html += '</div>';
            }}

            // Parameter Sets
            if (session.parameter_sets && Object.keys(session.parameter_sets).length > 0) {{
                html += '<div class="section">';
                html += '<div class="section-title">Parameter Sets</div>';
                
                Object.entries(session.parameter_sets).forEach(([ref, params]) => {{
                    html += '<div class="params">';
                    html += `<strong>${{ref}}:</strong><br>`;
                    Object.entries(params).forEach(([name, value]) => {{
                        html += `<div class="param-item"><span class="param-name">${{name}}:</span><span class="param-value">${{value}}</span></div>`;
                    }});
                    html += '</div>';
                }});
                
                html += '</div>';
            }}

            // NLSML Results
            if (session.nlsml_results && session.nlsml_results.length > 0) {{
                html += '<div class="section">';
                html += '<div class="section-title">NLSML Results</div>';
                session.nlsml_results.forEach((result, resultIndex) => {{
                    const nlsmlId = `nlsml-${{sessionIndex}}-${{resultIndex}}`;
                    html += '<div class="message">';
                    html += `<div class="message-header" onclick="toggleMessage('${{nlsmlId}}')">`;
                    html += `<span>NLSML Result ${{resultIndex + 1}} - ${{result.timestamp}}</span>`;
                    html += '<span class="toggle-icon">▶</span>';
                    html += '</div>';
                    html += `<div class="message-content" id="${{nlsmlId}}">`;
                    html += `<div class="recognized-text"><strong>Recognized Text:</strong><br>${{escapeHtml(result.recognized_text)}}</div>`;
                    html += `<div class="nlsml-content">${{escapeHtml(result.nlsml_content)}}</div>`;
                    if (result.source) {{
                        html += `<div><em>Source: ${{result.source}}</em></div>`;
                    }}
                    html += '</div>';
                    html += '</div>';
                }});
                html += '</div>';
            }}

            return html;
        }}

        function createMessageHTML(title, message, id) {{
            return (
                '<div class="message">' +
                    `<div class="message-header" onclick="toggleMessage('${{id}}')">` +
                        '<span>' + title + '</span>' +
                        '<span class="toggle-icon">▶</span>' +
                    '</div>' +
                    `<div class="message-content" id="${{id}}">` +
                        '<div class="nlsml-content">' + escapeHtml(message.raw) + '</div>' +
                        (message.details ? '<div class="params"><strong>Details:</strong><br>' + Object.entries(message.details).map(([k,v]) => '<div class="param-item"><span class="param-name">' + k + ':</span><span class="param-value">' + v + '</span></div>').join('') + '</div>' : '') +
                    '</div>' +
                '</div>'
            );
        }}

        function createMRCPMessageHTML(title, message, id) {{
            let content = `<div class="timestamp">${{message.timestamp}}</div>`;
            content += `<div class="method">${{message.method}}</div>`;
            content += `<div class="direction">${{message.direction_role}}</div>`;
            content += `<div><strong>Request ID:</strong> ${{message.req_id ?? ''}}</div>`;
            content += `<div><strong>Source IP:</strong> ${{message.src_ip ?? ''}}</div>`;
            content += `<div><strong>Destination IP:</strong> ${{message.dst_ip ?? ''}}</div>`;
            if (message.grammar_ref) {{
                content += `<div><strong>Grammar Ref:</strong> ${{message.grammar_ref}}</div>`;
            }}
            if (message.params_ref) {{
                content += `<div><strong>Params Ref:</strong> ${{message.params_ref}}</div>`;
            }}
            if (message.nlsml_content) {{
                content += `<div class="nlsml-content">${{escapeHtml(message.nlsml_content)}}</div>`;
            }}
            if (message.recognized_text) {{
                content += `<div class="recognized-text">${{escapeHtml(message.recognized_text)}}</div>`;
            }}

            return (
                '<div class="message">' +
                    `<div class="message-header" onclick="toggleMessage('${{id}}')">` +
                        '<span>' + title + '</span>' +
                        '<span class="toggle-icon">▶</span>' +
                    '</div>' +
                    `<div class="message-content" id="${{id}}">` +
                        content +
                    '</div>' +
                '</div>'
            );
        }}

        function toggleSession(index) {{
            const content = document.getElementById('session-content-' + index);
            content.classList.toggle('active');
        }}

        function toggleMessage(id) {{
            const content = document.getElementById(id);
            const header = content.previousElementSibling;
            const icon = header.querySelector('.toggle-icon');
            
            content.classList.toggle('active');
            icon.classList.toggle('rotated');
        }}

        function escapeHtml(text) {{
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}

        function setupSearch() {{
            const searchInput = document.getElementById('searchInput');
            let searchTimeout;

            searchInput.addEventListener('input', function() {{
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {{
                    performSearch(this.value);
                }}, 300);
            }});
        }}

        function performSearch(query) {{
            if (!query.trim()) {{
                clearHighlights();
                showAllSessions();
                return;
            }}

            const searchTerm = query.toLowerCase();
            const sessions = document.querySelectorAll('.session');
            let hasResults = false;

            sessions.forEach(session => {{
                const sessionText = session.textContent.toLowerCase();
                const matches = sessionText.includes(searchTerm);
                
                if (matches) {{
                    session.style.display = 'block';
                    hasResults = true;
                    highlightText(session, searchTerm);
                }} else {{
                    session.style.display = 'none';
                }}
            }});

            if (!hasResults) {{
                showNoResults();
            }}
        }}

        function highlightText(element, searchTerm) {{
            // Simple highlighting that doesn't interfere with existing HTML structure
            const regex = new RegExp('(' + searchTerm.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&') + ')', 'gi');
            
            // Only highlight text that's not already highlighted
            const walker = document.createTreeWalker(
                element,
                NodeFilter.SHOW_TEXT,
                {{
                    acceptNode: function(node) {{
                        // Skip if parent is already a highlight span
                        if (node.parentNode && node.parentNode.classList && node.parentNode.classList.contains('highlight')) {{
                            return NodeFilter.FILTER_REJECT;
                        }}
                        return NodeFilter.FILTER_ACCEPT;
                    }}
                }},
                false
            );

            const textNodes = [];
            let node;
            while (node = walker.nextNode()) {{
                textNodes.push(node);
            }}

            textNodes.forEach(textNode => {{
                const text = textNode.textContent;
                if (regex.test(text)) {{
                    const highlightedText = text.replace(regex, '<span class="highlight">$1</span>');
                    const span = document.createElement('span');
                    span.innerHTML = highlightedText;
                    textNode.parentNode.replaceChild(span, textNode);
                }}
            }});
        }}

        function clearHighlights() {{
            const highlights = document.querySelectorAll('.highlight');
            highlights.forEach(highlight => {{
                const parent = highlight.parentNode;
                if (parent) {{
                    // Replace the highlight span with its text content
                    const textNode = document.createTextNode(highlight.textContent);
                    parent.replaceChild(textNode, highlight);
                    // Merge adjacent text nodes
                    parent.normalize();
                }}
            }});
        }}

        function showAllSessions() {{
            const sessions = document.querySelectorAll('.session');
            sessions.forEach(session => {{
                session.style.display = 'block';
            }});
            
            const noResults = document.querySelector('.no-results');
            if (noResults) {{
                noResults.remove();
            }}
        }}

        function showNoResults() {{
            const container = document.getElementById('sessionsContainer');
            const existing = container.querySelector('.no-results');
            if (!existing) {{
                const noResults = document.createElement('div');
                noResults.className = 'no-results';
                noResults.textContent = 'No results found for your search.';
                container.appendChild(noResults);
            }}
        }}

        function toggleNoMrcpFilter() {{
            const hideNoMrcp = document.getElementById('hideNoMrcp').checked;
            const sessions = document.querySelectorAll('.session');
            
            sessions.forEach(session => {{
                const statusElement = session.querySelector('.session-status');
                if (statusElement && statusElement.textContent.includes('NO MRCP')) {{
                    session.style.display = hideNoMrcp ? 'none' : 'block';
                }}
            }});
        }}
    </script>
</body>
</html>'''

    # Write the HTML file
    with open(html_file, 'w') as f:
        f.write(html_content)
    
    print(f"Created {html_file} with clean data")

if __name__ == '__main__':
    main() 
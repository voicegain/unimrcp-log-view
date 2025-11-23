# UniMRCP Log Analyzer

A tool to parse UniMRCP logs and generate interactive HTML reports for analyzing SIP and MRCP message flows.

## Security Notice ⚠️

**IMPORTANT**: Log files may contain sensitive information including:
- Internal network details
- Session IDs and tokens
- Potentially sensitive application data
- System configuration details

**Never commit log files to version control!** The `.gitignore` file is configured to exclude:
- All `.log`, `.CSV`, and `.csv` files
- Generated JSON files

## Features

- **Session Detection**: Automatically identifies SIP sessions with MRCP activity
- **MRCP Analysis**: Parses MRCP messages, grammar definitions, and NLSML results
- **Interactive Reports**: Generates  HTML reports with collapsible sections
- **Multiple Log Formats**: Supports various UniMRCP log formats
- **Session Health**: Provides session statistics

## Quick Start

### Prerequisites

- Python 3.8 or higher
- UniMRCP log file

### Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/mrcp-log-analyzer.git
cd mrcp-log-analyzer
```

2. No additional dependencies required - uses only Python standard library!

### Usage

#### Option 1: Using the Build Script (Recommended)

**If you are inside the project directory:**
```bash
cd /path/to/MRCP\ Log\ Analyzer
python3 build_report.py "/path/to/your_log_file.log"
```

**If you are outside the project directory:**
```bash
python3 /full/path/to/MRCP\ Log\ Analyzer/build_report.py "/path/to/your_log_file.log"
```

- Output files (`summary.json`, `report.html`) will be created in your current working directory unless otherwise specified.
- For best results, it is recommended to run the script from within the project directory.

#### Option 2: Using Make (Even Easier)

**If you are inside the project directory:**
```bash
make build LOG="/path/to/your_log_file.log"
make serve
# Then open http://localhost:8000/report.html in your browser
```

**If you are outside the project directory:**
```bash
make -C /full/path/to/MRCP\ Log\ Analyzer build LOG="/path/to/your_log_file.log"
make -C /full/path/to/MRCP\ Log\ Analyzer serve
```

#### Option 3: Manual Steps

**If you are inside the project directory:**
```bash
python3 main.py "/path/to/your_log_file.log" -o summary.json
python3 update_html.py
make serve
```

**If you are outside the project directory:**
```bash
python3 /full/path/to/MRCP\ Log\ Analyzer/main.py "/path/to/your_log_file.log" -o summary.json
python3 /full/path/to/MRCP\ Log\ Analyzer/update_html.py
make -C /full/path/to/MRCP\ Log\ Analyzer serve
```



> **Note:** Never include or reference confidential logs in documentation, tests, or version control. Always use generic or anonymized sample logs for examples.

## Output Files

- **`summary.json`**: Structured data with all session information
- **`report.html`**: Interactive HTML report with collapsible sections

## Report Features

The generated HTML report includes:

- **Session Overview**: Total sessions, completion rates, health metrics
- **Per-Session Details**: 
  - SIP INVITE/BYE messages
  - MRCP messages grouped by channel
  - Grammar definitions and parameter sets
  - NLSML results with recognized text
  - Timestamps and session duration
- **Interactive Elements**: Collapsible sections for easy navigation
- **Raw Data**: Complete JSON data for further analysis


## Supported Log Formats

- UniMRCP server logs
- SIP/MRCP protocol messages
- Various timestamp formats
- Multiple channel configurations

## Troubleshooting

### Common Issues

1. **No sessions found**: Ensure your log contains SIP INVITE messages and MRCP activity
2. **Empty report**: Check that your log file is readable and contains the expected format
3. **Permission errors**: Make sure you have read access to the log file

### Debug Mode

```bash
# Run with debug output
python3 main.py "your_log_file.log" -d
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with different log formats
5. Submit a pull request


## Support

If you encounter issues or have questions:

1. Check the troubleshooting section above
2. Review the example logs included in the repository
3. Open an issue on GitHub with your log file (if possible) and error details 


## Future-Proofing and Advanced Features

- **Robust Session Verdicts**: The tool tracks both the final and any prior successful MRCP RECOGNITION-COMPLETE codes. Sessions are classified as:
  - `COMPLETE`: Last recognizer result is a success code (default: 0, 4, 5)
  - `TIMEOUT_AFTER_SUCCESS`: There was a successful recognition, but a later attempt timed out or failed
  - `INCOMPLETE`: Last recognizer result was a failure code, and there was no prior success
  - `NO_RECOGNITION`: Recognizer was never invoked (TTS-only or early hang-up)
- **Clear Explanations**: Every non-complete session includes a one-line, human-readable explanation in the JSON and dashboard, so users always know why a session is marked incomplete or red.
- **Configurable Success Codes**: You can define your own list of success codes by creating a `success_codes.yaml` or `success_codes.json` file in the project directory. Example YAML:
  ```yaml
  success_codes: [0, 4, 5, 6]
  ```
  If no config file is present, the tool defaults to `{0, 4, 5}`.
- **Safe Defaults**: If the config file is missing or malformed, the tool falls back to the default codes and continues working.
- **No Vendor Lock-In**: Easily adapt to new recognizer vendors or log formats by updating the config file—no code changes required.

## Using the Tool with Any Log File

You can analyze log files from any location, not just this folder. Simply provide the full or relative path to your log file:

```bash
python3 main.py "/path/to/your_log_file.log" -o summary.json
python3 update_html.py --output report.html
```

Or use the build script for convenience:

```bash
python3 build_report.py "/path/to/your_log_file.log"
```

- The tool will always generate a fresh `summary.json` and `report.html` based on the log you specify.
- **summary.json** is overwritten each time you run the parser, so you do not need to clear it manually. It will always reflect the most recent log you processed.
- **Confidentiality**: Do not commit any sensitive log files or generated summaries to version control. The tool does not retain or leak log data except in the output files you generate.

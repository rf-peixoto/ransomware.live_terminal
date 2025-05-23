# Ransomware.live Terminal

ALL CREDITS GO TO ransomware.live. I am not part of ransomware.live team.

## Description  
Ransomware.live Terminal is a command-line interface for querying the Ransomware.live API. It enables analysts to perform interactive searches for ransomware victims and groups, apply advanced filters, view detailed records, and generate time-series dashboards—all from a colored, intuitive terminal interface.

## Features  
- **Search by Keyword**: Retrieve victim records that match a free-text keyword.  
- **Date Queries**: List victims by year and month, or by an entire year.  
- **Country Queries**: List victims by ISO-2 country code.  
- **Combined Filters**: Query by country *and* date together.  
- **Group Queries**:  
  - List all known ransomware groups with descriptions and onion links.  
  - Retrieve all victims attributed to a specific group.  
  - Fetch detailed information about any group.  
- **Advanced Field Filters**: Optionally restrict results to records with press coverage, infostealer data, or recorded updates.  
- **Drill-Down Detail View**: After listing victims in a table, select any record index to view all fields for that entry.  
- **Dashboard Mode**: Render a terminal bar-chart of monthly incident counts for a specified country or group over a given year.  
- **Rate-Limit Handling**: Automatic detection of HTTP 429 responses, exponential backoff, and respect for `Retry-After` headers.  
- **Local Caching**: Responses cached in a local SQLite database (`~/.ransomware_cache.db`) with a default TTL of one hour to minimize repeated requests.  
- **Export Options**: Export any result set to JSON or CSV files via an interactive prompt.

## Requirements  
- Python 3.12 or later.  
- Dependencies (install via `pip`):  
  ```bash
  pip install requests rich
  ```

## Installation  
1. Clone or download the repository.  
2. Ensure Python 3.12+ is installed.  
3. Install dependencies:  
   ```bash
   pip install requests rich
   ```  
4. Make the main script executable:  
   ```bash
   chmod +x ransomwarelive_terminal.py
   ```

## Usage  
Run the CLI tool from a terminal:  
```bash
./ransomwarelive_terminal.py
```  
Select from the numbered menu to perform queries, apply filters, view details, or generate dashboards.

### Example Session  
```text
Ransomware.live Terminal

Menu
  1. Search victims by keyword
  2. List victims by date
  3. List victims by country
  4. List victims by country and date
  5. Search victims by group
  6. List all ransomware groups
  7. Fetch ransomware group details
  8. Dashboard (time-series)
  9. Exit

Select an option: 6
# ← Displays table of all groups with onion links
...
```

## Configuration  
- **Cache File**: Located at `~/.ransomware_cache.db`.  
- **Cache TTL**: Default is 3600 seconds; modify `CACHE_TTL` in the script if required.  
- **Backoff Parameters**: Controlled by `MAX_RETRIES`, `BACKOFF_INITIAL`, and `BACKOFF_MAX` constants.

## Project Structure  
```
ransomwarelive_terminal.py    # Main application script
README.md            # This documentation
```

## License  
Distributed under the MIT License.  

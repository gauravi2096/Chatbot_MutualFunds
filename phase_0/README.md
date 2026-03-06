# Phase 0 — Foundation & Data Contract

Defines the data model, source list, and update timestamp rules for the INDmoney Mutual Funds RAG chatbot.

## Outputs

| Output | Location | Description |
|--------|----------|-------------|
| **Data schema** | `schema.py` | Canonical `FundRecord` (Pydantic) for all supported factual fields |
| **Source list** | `source_registry.py` + `data/source_registry.json` | Phase 1 URLs with fund id and last-successful-update |
| **Update timestamp** | `update_timestamp.py` | Format (date + 12h am/pm) and rules for when "last update" is set |

## Schema (`schema.py`)

- **FundRecord**: All supported data points (Fund Name, NAV, NAV Date, Daily % Change, AUM, Expense Ratio, Min Lumpsum/SIP, Exit Load, 1Y/3Y/5Y CAGR, Since Inception, Equity %, Debt+Cash %, Market Cap Split, Top Holdings, Risk Level, Benchmark, ELSS Lock-in).
- Required: `fund_id`, `fund_name`, `source_url`. Rest optional for partial scrapes.
- **FIELD_DISPLAY_NAMES**: Map of field keys to display names for RAG/UI.

## Source registry (`source_registry.py`)

- **PHASE_1_SOURCES**: List of (slug, name) for the 10 INDmoney funds.
- **SourceRegistry**: List of `RegisteredSource` (fund_id, fund_name, url, last_successful_update) plus single `last_data_update` for chatbot responses.
- **get_default_registry()**: Builds registry with full URLs.
- **load_registry(path)** / **save_registry(registry, path)**: Persist to JSON (e.g. `data/source_registry.json`).

## Update timestamp (`update_timestamp.py`)

- **format_last_update(dt=None)**: Returns "last data update" string (e.g. `Mar 06, 2025 02:30 pm`). Uses `Asia/Kolkata`; if `dt` is None, uses current time.
- **parse_last_update(value)**: Parse stored string back to datetime.
- **Rules**: Set only after a successful ingestion run; Phase 4 scheduler will update daily.

## Usage

```bash
# Install dependencies
pip install -r requirements.txt

# From project root, use as package (optional)
export PYTHONPATH="${PYTHONPATH}:."
python -c "
from phase_0 import get_default_registry, save_registry, format_last_update
from pathlib import Path
r = get_default_registry()
save_registry(r, Path('phase_0/data/source_registry.json'))
print('Last update format example:', format_last_update())
"
```

## Dependencies

- Python 3.10+
- pydantic >= 2

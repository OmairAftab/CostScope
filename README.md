# CostScope desktop cost analysis

A Python/Tkinter desktop application for the Software Quality Engineering lab assignment.

## Run on Windows

Use Python 3.11 or later with Tkinter installed (included in the standard Windows Python installer).

```powershell
python -m pip install -r requirements.txt
python app.py
```

After installation, you can also double-click **run.bat**.

## Assignment features

1. Add, edit, and delete cost entries; import CSV or Excel (.xlsx).
2. Calculate estimated total, actual total, variance, and percentage variance automatically.
3. Compare estimated versus actual by category and visualize category variance in two bar charts.
4. Run local AI anomaly detection using scikit-learn's Isolation Forest. No API key or network service is needed.
5. Save a PDF report containing totals, analysis, both charts, and every detailed cost row. Export calculated rows as CSV too.

Click **Load demo** to try all features immediately, including an unusual consulting expense. Demo replaces current data after confirmation. Import appends records; importing the same file twice creates duplicates.

## File format

The first row must contain these case-insensitive headers, each exactly once:

```csv
item,category,estimated,actual
Development,Engineering,120000,126000
Testing,Engineering,30000,28000
```

Header order can vary; extra columns are ignored. XLSX imports use the first worksheet. Formula cells require values cached by Excel; formulas are never executed by the app. Blank rows are ignored. Every record is validated before any imported data is added. Use plain numeric amounts without commas or currency symbols; amounts are rounded to two decimal places. Maximum amount per entry is one trillion. Legacy .xls workbooks must be saved as .xlsx or CSV first.

All entries should use the same currency; the application labels amounts as currency units.

## Calculations

- Estimated total = sum of estimated amounts.
- Actual total = sum of actual amounts.
- Variance = actual minus estimated. Positive means over budget.
- Percentage variance = variance / estimated × 100.
- A zero estimate produces **N/A**, including a zero/zero row.
- Totals use Decimal arithmetic and round input amounts to two decimals.
- Total percentage is calculated from totals, rather than averaging row percentages.

## AI behavior and limits

The summary reports calculated facts. The AI feature is the separate Isolation Forest anomaly detector, which runs with at least six records. It analyzes log-transformed estimated and actual amounts plus relative variance, standardizes features, and uses 150 trees with a fixed random seed. Rows predicted as outliers receive a **Review** marker.

The model uses automatic contamination thresholding, so it does not force a fixed number of flags. Unusual costs may be legitimate; flags are review prompts, not fraud or error determinations. Results on small datasets are exploratory. Category labels are not model features. No data leaves the computer.

## Storage and reports

Changes save automatically to `%LOCALAPPDATA%\CostScope\costs.json`. A temporary file and atomic replacement protect normal saves. If saving fails, the app warns you so you can export before closing.

PDF reports include the current data and analysis, with charts and detailed rows paginated. CSV exports include variance and percentage variance. Potential formula prefixes in item/category text are escaped for spreadsheet safety. Report text uses the default Matplotlib font; some scripts or emoji may require a compatible font.

## Validation

```powershell
python -m unittest discover -s tests -v
```

Tests cover calculations, zero estimates, invalid data, transactional CSV imports, Excel imports, formula-safe exports, AI determinism, PDF generation, and desktop add/edit/delete persistence.

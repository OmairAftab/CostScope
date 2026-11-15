"""Validated cost records, file import, calculations, and local ML insights."""
from __future__ import annotations
import csv
import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

CENT = Decimal("0.01")
MAX_AMOUNT = Decimal("1000000000000")
HEADERS = ("item", "category", "estimated", "actual")


def money(value):
    try:
        result = Decimal(str(value).strip())
        if not result.is_finite() or result < 0 or result > MAX_AMOUNT:
            raise ValueError("Amounts must be between 0 and 1,000,000,000,000.")
        return result.quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError):
        raise ValueError("Enter a valid numeric amount (without currency symbols).") from None


@dataclass(frozen=True)
class Cost:
    item: str
    category: str
    estimated: Decimal
    actual: Decimal

    def __post_init__(self):
        item, category = str(self.item).strip(), str(self.category).strip()
        if not item or not category:
            raise ValueError("Item and category are required.")
        if len(item) > 120 or len(category) > 80:
            raise ValueError("Use at most 120 characters for item and 80 for category.")
        object.__setattr__(self, "item", item)
        object.__setattr__(self, "category", category)
        object.__setattr__(self, "estimated", money(self.estimated))
        object.__setattr__(self, "actual", money(self.actual))

    @property
    def variance(self):
        return self.actual - self.estimated

    @property
    def percentage(self):
        return self.variance / self.estimated * 100 if self.estimated else None

    def as_dict(self):
        return dict(item=self.item, category=self.category,
                    estimated=str(self.estimated), actual=str(self.actual))


def totals(records):
    estimated = sum((r.estimated for r in records), Decimal(0))
    actual = sum((r.actual for r in records), Decimal(0))
    variance = actual - estimated
    return estimated, actual, variance, variance / estimated * 100 if estimated else None


def percent(value):
    return "N/A" if value is None else f"{value:+.2f}%"


def categories(records):
    grouped = {}
    for record in records:
        amounts = grouped.setdefault(record.category, [Decimal(0), Decimal(0)])
        amounts[0] += record.estimated
        amounts[1] += record.actual
    return grouped


def import_costs(path):
    """Validate the entire file before returning any records; first XLSX sheet only."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            return _parse_rows(csv.reader(stream))
    if path.suffix.lower() == ".xlsx":
        try:
            import openpyxl
        except ImportError:
            raise ValueError("Excel support requires openpyxl. Run: pip install -r requirements.txt") from None
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            return _parse_rows(workbook.worksheets[0].iter_rows(values_only=True))
        finally:
            workbook.close()
    raise ValueError("Choose a CSV or XLSX file.")


def _parse_rows(rows):
    rows = iter(rows)
    header = next(rows, None)
    if header is None:
        raise ValueError("The file is empty.")
    header = [str(value or "").strip().lower() for value in header]
    if any(header.count(name) != 1 for name in HEADERS):
        raise ValueError("Include each required header once: item, category, estimated, actual.")
    positions = [header.index(name) for name in HEADERS]
    records = []
    for number, row in enumerate(rows, start=2):
        if all(value is None or str(value).strip() == "" for value in row):
            continue
        try:
            values = [row[index] if index < len(row) else None for index in positions]
            if any(value is None for value in values):
                raise ValueError("Required cell is empty.")
            records.append(Cost(*values))
        except ValueError as error:
            raise ValueError(f"Row {number}: {error}") from None
    if not records:
        raise ValueError("The file contains no cost records.")
    return records


def export_csv(path, records):
    # Spreadsheet programs may execute text beginning with formula characters.
    def safe(value):
        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value
    with open(path, "w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow((*HEADERS, "variance", "percentage_variance"))
        for record in records:
            writer.writerow((safe(record.item), safe(record.category), str(record.estimated),
                             str(record.actual), str(record.variance), percent(record.percentage)))


def analyze(records):
    if not records:
        return "Add or import costs to generate an analysis.", set()
    estimated, actual, variance, rate = totals(records)
    direction = "over budget" if variance > 0 else "under budget" if variance < 0 else "on budget"
    lines = [
        f"Actual cost is {actual:,.2f} against an estimate of {estimated:,.2f}.",
        f"The project is {direction}; variance is {variance:+,.2f} ({percent(rate)}).",
    ]
    largest = max(records, key=lambda r: r.variance)
    if largest.variance > 0:
        lines.append(f"Largest overrun: {largest.item} ({largest.category}), +{largest.variance:,.2f}.")
    unbudgeted = [r for r in records if not r.estimated and r.actual]
    if unbudgeted:
        lines.append(f"{len(unbudgeted)} expense(s) have actual spending with no estimate; percentage variance is undefined.")
    flagged = set()
    if len(records) < 6:
        lines.append("AI anomaly detection needs at least 6 records. Add more costs to run the model.")
        return "\n\n".join(lines), flagged
    try:
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler
        features = [[math.log1p(float(r.estimated)), math.log1p(float(r.actual)),
                     float(r.variance) / max(float(r.estimated), 1.0)] for r in records]
        scaled = StandardScaler().fit_transform(features)
        model = IsolationForest(n_estimators=150, contamination="auto", random_state=42)
        predictions = model.fit_predict(scaled)
        flagged = {i for i, label in enumerate(predictions) if label == -1}
        lines.append("AI: Isolation Forest analyzed estimated cost, actual cost, and relative variance.")
        if flagged:
            names = ", ".join(records[i].item for i in sorted(flagged))
            lines.append(f"Unusual expenses to review: {names}.")
        else:
            lines.append("The AI model did not flag unusual expenses.")
        lines.append("Flags indicate statistical differences, not confirmed errors. Review them with project context.")
    except ImportError:
        lines.append("AI unavailable: install requirements.txt to enable scikit-learn anomaly detection.")
    return "\n\n".join(lines), flagged

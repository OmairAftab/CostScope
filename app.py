"""CostScope desktop app. Run with: python app.py"""
import json
import os
import tempfile
import textwrap
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib import rcParams

from cost_model import Cost, totals, percent, categories, import_costs, export_csv, analyze

rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
DATA_FILE = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "CostScope" / "costs.json"
BLUE, TEAL, RED = "#4263eb", "#0d9488", "#dc5464"
SAMPLE = [
    ("Development", "Engineering", "120000", "126000"),
    ("Testing", "Engineering", "30000", "28000"),
    ("Design", "Product", "25000", "26000"),
    ("Research", "Product", "15000", "14500"),
    ("Cloud hosting", "Operations", "10000", "11000"),
    ("Licenses", "Operations", "8000", "8200"),
    ("Training", "People", "12000", "11500"),
    ("Consulting", "People", "10000", "48000"),
]


def cost_figure(records):
    grouped = categories(records)
    # Keep every category visible by expanding the figure when needed.
    fig = Figure(figsize=(11, max(3.6, len(grouped) * .35)), dpi=100, facecolor="#ffffff")
    left, right = fig.subplots(1, 2)
    if not grouped:
        for axis in (left, right):
            axis.text(.5, .5, "Add costs to see comparisons", ha="center", va="center", transform=axis.transAxes)
            axis.set_axis_off()
        fig.tight_layout(pad=2)
        return fig
    labels = list(grouped)
    y = list(range(len(labels)))
    estimated = [float(grouped[label][0]) for label in labels]
    actual = [float(grouped[label][1]) for label in labels]
    left.barh([v - .18 for v in y], estimated, height=.34, color=BLUE, label="Estimated")
    left.barh([v + .18 for v in y], actual, height=.34, color=TEAL, label="Actual")
    left.set_yticks(y, labels)
    left.invert_yaxis()
    left.set_title("Estimated vs actual by category", loc="left", weight="bold", pad=18)
    left.set_xlabel("Cost (currency units)")
    left.legend(frameon=False)
    variances = [a - e for a, e in zip(actual, estimated)]
    right.barh(y, variances, color=[RED if v > 0 else TEAL for v in variances])
    right.set_yticks(y, labels)
    right.invert_yaxis()
    right.axvline(0, color="#94a3b8", linewidth=.8)
    right.set_title("Cost variance by category", loc="left", weight="bold", pad=18)
    right.set_xlabel("Actual − estimated • positive = over budget")
    for axis in (left, right):
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(axis="x", alpha=.15)
        axis.set_axisbelow(True)
        axis.ticklabel_format(axis="x", style="plain", useOffset=False)
    fig.tight_layout(pad=2.5)
    return fig


def create_report(path, records, summary):
    with PdfPages(path) as pdf:
        fig = Figure(figsize=(8.27, 11.69), facecolor="white")
        fig.text(.08, .94, "CostScope | Cost analysis report", fontsize=21, weight="bold", color=BLUE)
        fig.text(.08, .905, datetime.now().strftime("Generated %d %b %Y, %H:%M") + " • All values in currency units", fontsize=9)
        estimated, actual, variance, rate = totals(records)
        metrics = f"Estimated: {estimated:,.2f}\nActual: {actual:,.2f}\nVariance: {variance:+,.2f}\nPercentage variance: {percent(rate)}"
        fig.text(.08, .85, metrics, fontsize=14, linespacing=1.8, va="top")
        fig.text(.08, .67, "Analysis & AI findings", fontsize=15, weight="bold")
        wrapped = "\n".join(textwrap.fill(p, 95) if p else "" for p in summary.split("\n"))
        # Long summaries continue on dedicated pages.
        summary_lines = wrapped.splitlines()
        fig.text(.08, .63, "\n".join(summary_lines[:25]), fontsize=10, va="top", linespacing=1.5)
        fig.text(.08, .07, "Variance = actual − estimated. Percentage = variance ÷ estimated × 100.\nA zero estimate produces N/A. AI flags require human review.", fontsize=9)
        pdf.savefig(fig)
        for start in range(25, len(summary_lines), 48):
            continuation = Figure(figsize=(8.27, 11.69))
            continuation.text(.08, .94, "Analysis continued", fontsize=18, weight="bold")
            continuation.text(.08, .88, "\n".join(summary_lines[start:start+48]), fontsize=10, va="top", linespacing=1.5)
            pdf.savefig(continuation)
        # Paginate categories so every category is readable in the exported charts.
        names = list(categories(records))
        for start in range(0, len(names), 12):
            subset = [r for r in records if r.category in names[start:start+12]]
            pdf.savefig(cost_figure(subset))
        for start in range(0, len(records), 8):
            fig = Figure(figsize=(11.69, 8.27))
            axis = fig.add_subplot(111)
            axis.axis("off")
            axis.set_title(f"Detailed costs • records {start+1}–{min(start+8, len(records))}", loc="left", pad=22, weight="bold")
            rows = [[textwrap.fill(r.item, 30), textwrap.fill(r.category, 20),
                     f"{r.estimated:,.2f}", f"{r.actual:,.2f}", f"{r.variance:+,.2f}", percent(r.percentage)]
                    for r in records[start:start+8]]
            table = axis.table(cellText=rows, colLabels=["Item", "Category", "Estimated", "Actual", "Variance", "Variance %"],
                               colWidths=[.25, .18, .15, .15, .15, .12], loc="upper center", cellLoc="left")
            table.auto_set_font_size(False)
            table.set_fontsize(8)
            for (row, col), cell in table.get_celld().items():
                cell.set_height(.035 if row == 0 else max(.035, .024 * max(len(str(value).splitlines()) for value in rows[row-1])))
                cell.set_edgecolor("#e2e8f0")
                if row == 0:
                    cell.set_facecolor(BLUE)
                    cell.set_text_props(color="white", weight="bold")
            fig.tight_layout(pad=2)
            pdf.savefig(fig)


class CostScope(tk.Tk):
    def __init__(self, data_file=DATA_FILE):
        super().__init__()
        self.data_file = Path(data_file)
        self.title("CostScope — Project cost analysis")
        self.geometry("1240x860")
        self.minsize(950, 680)
        self.configure(bg="#f3f5fa")
        self.records = []
        self.edit_index = None
        self.summary = ""
        self.flagged = set()
        self.status = tk.StringVar(value="Ready • Data is saved locally")
        self.inputs = {name: tk.StringVar() for name in ("item", "category", "estimated", "actual")}
        self.setup_style()
        self.build()
        self.load()
        self.refresh()

    def setup_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), background="#f3f5fa")
        style.configure("TButton", padding=(11, 7))
        style.configure("Accent.TButton", foreground="white", background=BLUE)
        style.map("Accent.TButton", background=[("active", "#304dcc")])
        style.configure("Treeview", rowheight=29, background="white", fieldbackground="white")
        style.configure("Treeview.Heading", padding=8, font=("Segoe UI", 10, "bold"))
        style.configure("Title.TLabel", font=("Segoe UI", 25, "bold"), foreground="#172238")
        style.configure("Sub.TLabel", foreground="#64748b")
        style.configure("Metric.TLabel", font=("Segoe UI", 20, "bold"), foreground="#172238")

    def build(self):
        outer = ttk.Frame(self, padding=22)
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x")
        ttk.Label(header, text="CostScope", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="PROJECT COST ANALYSIS", style="Sub.TLabel").pack(side="left", padx=18, pady=(10, 0))
        toolbar = ttk.Frame(outer)
        toolbar.pack(fill="x", pady=(14, 16))
        for label, command, accent in [
            ("Import Excel / CSV", self.import_file, True), ("Load demo", self.demo, False),
            ("Export PDF report", self.report, True), ("Export results CSV", self.export, False)]:
            ttk.Button(toolbar, text=label, command=command, style="Accent.TButton" if accent else "TButton").pack(side="left", padx=(0, 8))
        cards = ttk.Frame(outer)
        cards.pack(fill="x")
        self.metrics = []
        for index, title in enumerate(["ESTIMATED COST", "ACTUAL COST", "COST VARIANCE", "VARIANCE %"]):
            cards.columnconfigure(index, weight=1)
            frame = ttk.Frame(cards, padding=12)
            frame.grid(row=0, column=index, sticky="nsew", padx=(0, 12))
            ttk.Label(frame, text=title, style="Sub.TLabel").pack(anchor="w")
            value = ttk.Label(frame, text="0.00", style="Metric.TLabel")
            value.pack(anchor="w", pady=(5, 0))
            self.metrics.append(value)
        ttk.Label(outer, text="All amounts use the same currency unit. Positive variance means over budget; zero estimate gives N/A.", style="Sub.TLabel").pack(anchor="w", pady=(6, 12))
        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)
        data_tab, charts_tab, ai_tab = (ttk.Frame(notebook, padding=12) for _ in range(3))
        notebook.add(data_tab, text="  Cost entries  ")
        notebook.add(charts_tab, text="  Comparison charts  ")
        notebook.add(ai_tab, text="  AI insights  ")
        form = ttk.Frame(data_tab)
        form.pack(fill="x")
        for i, (name, variable) in enumerate(self.inputs.items()):
            form.columnconfigure(i, weight=1)
            ttk.Label(form, text=name.capitalize()).grid(row=0, column=i, sticky="w")
            ttk.Entry(form, textvariable=variable).grid(row=1, column=i, padx=(0, 10), pady=(5, 10), sticky="ew")
        actions = ttk.Frame(data_tab)
        actions.pack(fill="x", pady=(0, 12))
        self.save_button = ttk.Button(actions, text="Add cost", command=self.add, style="Accent.TButton")
        self.save_button.pack(side="left", padx=(0, 8))
        for title, command in [("Edit selected", self.edit), ("Cancel edit", self.cancel_edit), ("Delete selected", self.delete)]:
            ttk.Button(actions, text=title, command=command).pack(side="left", padx=(0, 8))
        table_frame = ttk.Frame(data_tab)
        table_frame.pack(fill="both", expand=True)
        columns = ("item", "category", "estimated", "actual", "variance", "percentage", "ai")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        for col, title, width in zip(columns, ["Item", "Category", "Estimated", "Actual", "Variance", "Variance %", "AI review"], [230, 150, 120, 120, 120, 105, 110]):
            self.table.heading(col, text=title)
            self.table.column(col, width=width, minwidth=85, anchor="w" if col in ("item", "category", "ai") else "e")
        self.table.tag_configure("over", foreground="#b83f50")
        self.table.bind("<Double-1>", lambda event: self.edit())
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.table.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.chart_area = tk.Canvas(charts_tab, bg="white", highlightthickness=0)
        chart_scroll = ttk.Scrollbar(charts_tab, orient="vertical", command=self.chart_area.yview)
        self.chart_area.configure(yscrollcommand=chart_scroll.set)
        chart_scroll.pack(side="right", fill="y")
        self.chart_area.pack(side="left", fill="both", expand=True)
        self.chart_inner = ttk.Frame(self.chart_area)
        self.chart_window = self.chart_area.create_window((0, 0), window=self.chart_inner, anchor="nw")
        self.chart_inner.bind("<Configure>", lambda event: self.chart_area.configure(scrollregion=self.chart_area.bbox("all")))
        self.chart_area.bind("<Configure>", lambda event: self.chart_area.itemconfigure(self.chart_window, width=event.width))
        ttk.Label(ai_tab, text="Local AI expense review", font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=(5, 10))
        ttk.Label(ai_tab, text="Isolation Forest • Runs on your computer • Automatically refreshes with your data", style="Sub.TLabel").pack(anchor="w", pady=(0, 14))
        self.ai_text = tk.Text(ai_tab, wrap="word", font=("Segoe UI", 12), relief="flat", padx=18, pady=18, bg="white")
        ai_scroll = ttk.Scrollbar(ai_tab, command=self.ai_text.yview)
        self.ai_text.configure(yscrollcommand=ai_scroll.set)
        ai_scroll.pack(side="right", fill="y")
        self.ai_text.pack(fill="both", expand=True)
        ttk.Label(outer, textvariable=self.status, style="Sub.TLabel").pack(anchor="w", pady=(12, 0))

    def load(self):
        if not self.data_file.exists():
            return
        try:
            rows = json.loads(self.data_file.read_text(encoding="utf-8"))
            self.records = [Cost(**row) for row in rows]
        except Exception as error:
            messagebox.showwarning("Could not restore saved data", f"The saved file could not be read:\n{error}\n\nIt will remain untouched until you change data.")

    def save(self):
        temp_path = None
        try:
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.data_file.parent, delete=False) as stream:
                temp_path = Path(stream.name)
                json.dump([r.as_dict() for r in self.records], stream, indent=2)
            os.replace(temp_path, self.data_file)
            return True
        except OSError as error:
            messagebox.showerror("Save failed", f"Changes remain in this session. Export them before closing.\n{error}")
            return False
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink()

    def refresh(self):
        self.summary, self.flagged = analyze(self.records)
        e, a, v, p = totals(self.records)
        for label, value in zip(self.metrics, [f"{e:,.2f}", f"{a:,.2f}", f"{v:+,.2f}", percent(p)]):
            label.configure(text=value)
        self.metrics[2].configure(foreground=RED if v > 0 else TEAL)
        self.table.delete(*self.table.get_children())
        for index, r in enumerate(self.records):
            self.table.insert("", "end", iid=str(index), values=(r.item, r.category, f"{r.estimated:,.2f}", f"{r.actual:,.2f}",
                              f"{r.variance:+,.2f}", percent(r.percentage), "Review" if index in self.flagged else "—"),
                              tags=("over",) if r.variance > 0 else ())
        self.ai_text.configure(state="normal")
        self.ai_text.delete("1.0", "end")
        self.ai_text.insert("1.0", self.summary)
        self.ai_text.configure(state="disabled")
        for widget in self.chart_inner.winfo_children():
            widget.destroy()
        self.figure = cost_figure(self.records)
        self.chart = FigureCanvasTkAgg(self.figure, master=self.chart_inner)
        self.chart.draw()
        self.chart.get_tk_widget().pack(fill="both", expand=True)

    def changed(self, message):
        saved = self.save()
        self.refresh()
        self.status.set(message + (f" • {len(self.records)} records • Saved locally" if saved else " • NOT SAVED"))

    def add(self):
        try:
            record = Cost(**{key: value.get() for key, value in self.inputs.items()})
        except ValueError as error:
            messagebox.showerror("Check cost details", str(error))
            return
        if self.edit_index is None:
            self.records.append(record)
        else:
            self.records[self.edit_index] = record
        self.cancel_edit()
        self.changed("Cost saved")

    def edit(self):
        selection = self.table.selection()
        if len(selection) != 1:
            messagebox.showinfo("Choose a cost", "Select exactly one cost to edit.")
            return
        self.edit_index = int(selection[0])
        record = self.records[self.edit_index]
        for key, value in record.as_dict().items():
            self.inputs[key].set(value)
        self.save_button.configure(text="Save changes")

    def cancel_edit(self):
        self.edit_index = None
        for value in self.inputs.values():
            value.set("")
        self.save_button.configure(text="Add cost")

    def delete(self):
        selection = self.table.selection()
        if not selection:
            messagebox.showinfo("Choose costs", "Select one or more rows to delete.")
            return
        if messagebox.askyesno("Delete costs", f"Delete {len(selection)} selected cost(s)?"):
            indices = {int(index) for index in selection}
            self.records = [r for i, r in enumerate(self.records) if i not in indices]
            self.cancel_edit()
            self.changed("Selected costs deleted")

    def import_file(self):
        path = filedialog.askopenfilename(filetypes=[("Cost files", "*.csv *.xlsx"), ("CSV", "*.csv"), ("Excel workbook", "*.xlsx")])
        if not path:
            return
        try:
            imported = import_costs(path)
            # Import is append-only, with whole-file validation before mutation.
            self.records.extend(imported)
            self.cancel_edit()
            self.changed(f"Imported {len(imported)} costs")
        except Exception as error:
            messagebox.showerror("Import failed", str(error))

    def demo(self):
        if self.records and not messagebox.askyesno("Load demo", "Replace current records with the demo dataset?"):
            return
        self.records = [Cost(*row) for row in SAMPLE]
        self.cancel_edit()
        self.changed("Demo loaded")

    def export(self):
        if not self.records:
            messagebox.showinfo("No costs", "Add or import costs first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="costscope_results.csv", filetypes=[("CSV", "*.csv")])
        if path:
            try:
                export_csv(path, self.records)
                self.status.set(f"CSV exported: {path}")
                messagebox.showinfo("Export complete", f"Results saved to:\n{path}")
            except Exception as error:
                messagebox.showerror("Export failed", str(error))

    def report(self):
        if not self.records:
            messagebox.showinfo("No costs", "Add or import costs first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile="costscope_report.pdf", filetypes=[("PDF report", "*.pdf")])
        if path:
            try:
                create_report(path, self.records, self.summary)
                self.status.set(f"PDF report exported: {path}")
                messagebox.showinfo("Report complete", f"Report saved to:\n{path}")
            except Exception as error:
                messagebox.showerror("Report failed", str(error))


if __name__ == "__main__":
    CostScope().mainloop()

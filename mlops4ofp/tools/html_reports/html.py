# mlops4ofp/tools/html_reports/html.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence, Tuple


# ----------------------------
# CSS (INLINE, siempre aplicado)
# ----------------------------
REPORT_CSS = r"""
/* DEBUG (deja esto solo mientras pruebas) */

:root{
  --bg: #ffffff;
  --card: #ffffff;
  --text: #1c1e21;
  --muted: #5f6368;
  --accent: #85bddd;
  --line: #dcdfe3;
  --figure-bg: #ffffff;
}

@media (prefers-color-scheme: dark){
  :root{
    --bg: #2b2b2b;
    --card: #333333;
    --text: #f2f2f2;
    --muted: #c7c7c7;
    --accent: #85bddd;
    --figure-bg: #2f2f2f;
  }
}

body{
  margin:0;
  padding:40px;
  font-family: Inter, Segoe UI, Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  /* outline: 8px solid red !important; */ /* DEBUG */
}

.container{
  max-width: 1400px;
  margin: 0 auto;
}

h1{ margin: 0 0 10px 0; font-size: 30px; }
h2{ margin-top: 36px; border-top: 1px solid var(--line); padding-top: 22px; }
h3{ margin-top: 22px; color: var(--muted); }

p{ color: var(--muted); line-height: 1.55; }
.small{ font-size: 12px; color: var(--muted); }

.card{
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 18px 20px;
  margin: 14px 0;
}

.kpi{
  display:flex;
  gap: 14px;
  flex-wrap: wrap;
}

.kpi .pill{
  background: rgba(110, 123, 243, 0.815);
  border: 1px solid rgba(135, 174, 248, 0.644);
  color: var(--text);
  padding: 8px 12px;
  border-radius: 999px;
  font-size: 13px;
}

table{
  border-collapse: collapse;
  width: 100%;
  margin: 14px 0;
  overflow: hidden;
  border-radius: 12px;
}

th, td{
  border-bottom: 1px solid var(--line);
  padding: 9px 12px;
  font-size: 12px;
}

th{
  text-align:left;
  background: rgba(0,0,0,.04);
  color: var(--text);
}

@media (prefers-color-scheme: dark){
  th{ background: rgba(255,255,255,.06); }
}

tr:hover td{
  background: rgba(0,0,0,.04);
}

hr{
  border: none;
  border-top: 1px solid var(--line);
  margin: 26px 0;
}

code{
  background: rgba(0,0,0,.05);
  padding: 2px 6px;
  border-radius: 6px;
}

@media (prefers-color-scheme: dark){
  code{ background: rgba(255,255,255,.08); }
}

.grid{
  display:grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 24px;
}

@media (max-width: 1200px){
  .grid{ grid-template-columns: 1fr; }
}

.figure-card{
  background: var(--figure-bg);
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 18px;
}

.figure-card img{
  width: 100%;
  height: auto;
  border-radius: 12px;
  display:block;
}

.caption{
  margin-top: 10px;
  font-size: 14px;
  color: var(--muted);
}

.events-grid{
  display:grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
  margin-top: 12px;
  align-items: start;
}

@media (max-width: 600px){
  .events-grid{ grid-template-columns: 1fr; }
}

.events-card{
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 12px 12px 10px 12px;
  background: var(--card);
  overflow-x: auto;
}

.events-card-header{
  display:flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.events-card-title{
  font-weight: 700;
  font-size: 14px;
  margin: 0;
}

.events-card-pill{
  font-size: 12px;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(0,0,0,.06);
  white-space: nowrap;
}

@media (prefers-color-scheme: dark){
  .events-card-pill{ background: rgba(255,255,255,.1); }
}

.events-muted{
  color: var(--muted);
  font-size: 12px;
  margin: 6px 0 0 0;
}

.kpi-grid{
  display:grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
  margin: 12px 0 6px 0;
}

.kpi-card{
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 14px 16px;
  position: relative;
  overflow: hidden;
}

.kpi-card::before{
  content:"";
  position:absolute;
  inset:0 0 auto 0;
  height: 5px;
  background: var(--accent);
  opacity: .9;
}

.kpi-label{ font-size: 12px; color: var(--muted); margin-bottom: 6px; }
.kpi-value{ font-size: 26px; font-weight: 800; line-height: 1.1; margin-bottom: 6px; }
.kpi-hint{ font-size: 12px; color: var(--muted); line-height: 1.45; }
.kpi-muted{ opacity: .75; }
/* === Tabla comparación OW vs PW === */
table.compare-events th:nth-child(3),
table.compare-events td:nth-child(3),
table.compare-events th:nth-child(4),
table.compare-events td:nth-child(4){
  background: rgba(67, 97, 238, 0.10);   /* azul OW */
}

table.compare-events th:nth-child(5),
table.compare-events td:nth-child(5),
table.compare-events th:nth-child(6),
table.compare-events td:nth-child(6){
  background: rgba(247, 37, 133, 0.10);  /* rosa PW */
}

table.compare-events th:nth-child(7),
table.compare-events td:nth-child(7){
  background: rgba(6, 214, 160, 0.18);   /* verde total */
  font-weight: 600;
}

"""


# ----------------------------
# Helpers
# ----------------------------
def html_escape(s: Any) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def h(tag: str, content: str, **attrs) -> str:
    attr_str = " ".join(f'{k}="{html_escape(v)}"' for k, v in attrs.items())
    return f"<{tag} {attr_str}>{content}</{tag}>" if attr_str else f"<{tag}>{content}</{tag}>"

def now_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    return datetime.now().strftime(fmt)

def smart_fmt(x: Any) -> Any:
    if not isinstance(x, (int, float)):
        return x
    if abs(x) >= 1:
        return f"{x:,.2f}"
    return f"{x:.4f}"

def _compact_value(v: Any, *, max_len: int = 80) -> str:
    if v is None:
        s = "—"
    elif isinstance(v, Path):
        s = str(v)
    elif isinstance(v, (list, tuple, set)):
        items = list(v)
        s = "[" + ", ".join(map(str, items[:10])) + (", …" if len(items) > 10 else "") + "]"
    elif isinstance(v, dict):
        items = list(v.items())
        head = ", ".join(f"{k}: {val}" for k, val in items[:8])
        s = "{" + head + (", …" if len(items) > 8 else "") + "}"
    else:
        s = str(v)
    return (s[: max_len - 1] + "…") if len(s) > max_len else s


# ----------------------------
# Layout blocks
# ----------------------------
def render_header(*, title: str) -> str:
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>{REPORT_CSS}</style>
</head>
<body>
<div class="container">
  <h1>{html_escape(title)}</h1>
  <p class="small">Generado el {now_str()}</p>
"""

def render_footer() -> str:
    return "</div></body></html>"

def render_pills(pairs: Iterable[tuple[str, object]]) -> str:
    pills = "\n".join(
        f"<span class='pill'><b>{html_escape(k)}:</b> {html_escape(_compact_value(v))}</span>"
        for k, v in pairs
    )
    return f"<div class='kpi'>{pills}</div>"

def render_pills_from_variant_params(ctx: dict, *, max_value_len: int = 80) -> str:
    vp = ctx.get("variant_params", {})
    if not isinstance(vp, dict) or not vp:
        return ""
    return render_pills([(k, _compact_value(v, max_len=max_value_len)) for k, v in vp.items()])

def open_grid(*, cols: int = 2, gap_rem: float = 1.0) -> str:
    return f"<div class='grid' style='grid-template-columns: repeat({cols}, minmax(0, 1fr)); gap:{gap_rem}rem;'>"

def close_div() -> str:
    return "</div>"

def render_figure_card(fig_title: str, fig_filename: str, *, max_width: str = "100%") -> str:
    return (
        "<div class='figure-card' style='text-align:center;'>"
        f"<img src='figures/{html_escape(fig_filename)}' alt='{html_escape(fig_title)}' style='max-width:{max_width};'>"
        f"<div class='caption'>{html_escape(fig_title)}</div>"
        "</div>"
    )

def figures_grid(figs: Sequence[Tuple[str, Path]], *, cols: int = 2, max_width: str = "100%") -> str:
    parts = [open_grid(cols=cols, gap_rem=1.0)]
    for title, path in figs:
        parts.append(render_figure_card(title, path.name, max_width=max_width))
    parts.append(close_div())
    return "\n".join(parts)

def events_card(measure: str, total: int, table_html: str, n_types: int) -> str:
    return f"""
<div class='events-card'>
  <div class='events-card-header'>
    <div class='events-card-title'>{html_escape(measure)}</div>
    <div class='events-card-pill'>Total: <b>{total:,}</b></div>
  </div>
  <div style='font-size: 10px;'>{table_html}</div>
  <p class='events-muted'>Tipos de eventos: {n_types}</p>
</div>
"""

def kpi_card(label: str, value: str, hint: str, *, muted: bool = False) -> str:
    cls = "kpi-card kpi-muted" if muted else "kpi-card"
    return f"""
<div class="{cls}">
  <div class="kpi-label">{html_escape(label)}</div>
  <div class="kpi-value">{html_escape(value)}</div>
  <div class="kpi-hint">{html_escape(hint)}</div>
</div>
"""

def kpi_grid(cards_html: list[str]) -> str:
    return "<div class='kpi-grid'>\n" + "\n".join(cards_html) + "\n</div>"


# Convenience blocks (mínimo HTML en reports)
def para(text: str, *, cls: str = "") -> str:
    c = f' class="{cls}"' if cls else ""
    return f"<p{c}>{text}</p>"

def card(inner_html: str) -> str:
    return f"<div class='card'>{inner_html}</div>"

def section(title: str, *, intro: Optional[str] = None) -> str:
    out = [h("h2", html_escape(title))]
    if intro:
        out.append(para(html_escape(intro)))
    return "\n".join(out)

def subsection(title: str, *, center: bool = False) -> str:
    style = "text-align: center;" if center else ""
    return h("h3", html_escape(title), style=style) if style else h("h3", html_escape(title))

def table_card(df, *, title: Optional[str] = None, index: bool = True, table_class: str= "") -> str:
    inner = ""
    if title:
        inner += h("h3", html_escape(title))
    
    html_table = df.to_html(index=index, escape=False)

    if table_class:
        html_table = html_table.replace("<table", f"<table class='{html_escape(table_class)}'", 1)

    inner += html_table
    return card(inner)

########################################################################################################################
# ----------------------------
# Report builder
# ----------------------------
########################################################################################################################
@dataclass
class HtmlReport:
    title: str
    ctx: dict
    sections: list[str] = field(default_factory=list)

    include_pills: bool = True
    include_hr_after_header: bool = True
    max_pill_value_len: int = 80

    _started: bool = False
    _finished: bool = False

    def start(self) -> "HtmlReport":
        if self._started:
            return self

        self.sections.append(render_header(title=self.title))

        if self.include_pills:
            pills = render_pills_from_variant_params(self.ctx, max_value_len=self.max_pill_value_len)
            if pills:
                self.sections.append(pills)

        if self.include_hr_after_header:
            self.sections.append("<hr>")

        self._started = True
        return self

    def add(self, html: str) -> "HtmlReport":
        self.sections.append(html)
        return self

    def hr(self) -> "HtmlReport":
        self.sections.append("<hr>")
        return self

    def finish(self) -> "HtmlReport":
        if not self._finished:
            self.sections.append(render_footer())
            self._finished = True
        return self

    def write(self, path: Path | str) -> Path:
        if not self._started:
            self.start()
        if not self._finished:
            self.finish()

        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(self.sections), encoding="utf-8")
        return out_path

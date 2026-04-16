"""
Styles — CSS Textual centralisé pour ORACLE v2.
Thème cyberpunk neural — bleu profond + cyan électrique.
"""

ORACLE_CSS = """
Screen {
    background: #0a0e1a;
}

Header {
    background: #0d1b2a;
    color: #00d4ff;
    text-style: bold;
}

Footer {
    background: #0d1b2a;
    color: #4a9eff;
}

#ascii-banner {
    color: #00d4ff;
    text-style: bold;
    text-align: center;
    padding: 0 1;
}

#main-grid {
    grid-size: 3 2;
    grid-rows: 1fr 1fr;
    grid-columns: 1fr 1fr 2fr;
    height: 1fr;
    padding: 1;
    grid-gutter: 1;
}

BrainstemWidget, ParliamentWidget, SignalsWidget {
    background: #0d1b2a;
    border: solid #1e3a5f;
    padding: 1 2;
    height: 100%;
}

BrainstemWidget:focus, ParliamentWidget:focus {
    border: solid #00d4ff;
}

PolymarketWidget {
    background: #0d1b2a;
    border: solid #1e3a5f;
    padding: 1;
    row-span: 2;
    height: 100%;
}

OracleLogWidget {
    background: #060d1a;
    border: solid #1a2a3a;
    padding: 1;
    height: 100%;
}

PnLPanel {
    background: #0d1b2a;
    border: solid #1e3a5f;
    padding: 1 2;
    height: 100%;
}

RiskMeterPanel {
    background: #0d1b2a;
    border: solid #2a1e1e;
    padding: 1 2;
    height: 100%;
}

TimezonePanel {
    background: #0d1b2a;
    border: solid #1e2a3f;
    padding: 1 2;
    height: 100%;
}

#brainstem-title, #parliament-title, #poly-title, #signals-title,
#pnl-title, #risk-title, #tz-title, #trades-title {
    color: #4a9eff;
    text-style: bold;
    padding-bottom: 1;
}

DataTable {
    background: #060d1a;
    border: none;
}

DataTable > .datatable--header {
    background: #0d1b2a;
    color: #4a9eff;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: #1e3a5f;
}

DataTable > .datatable--hover {
    background: #152535;
}

#bottom-bar {
    height: 3;
    background: #0d1b2a;
    border-top: solid #1e3a5f;
    padding: 0 2;
    color: #4a9eff;
}

Label {
    color: #4a9eff;
}

TabbedContent {
    height: 1fr;
}

TabPane {
    padding: 0;
}
"""

# Couleurs du thème
COLORS = {
    "background": "#0a0e1a",
    "surface": "#0d1b2a",
    "deep": "#060d1a",
    "border": "#1e3a5f",
    "accent": "#00d4ff",
    "primary": "#4a9eff",
    "long": "green",
    "short": "red",
    "neutral": "yellow",
    "warning": "orange",
    "dim": "#4a5568",
}

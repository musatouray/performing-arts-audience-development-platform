"""Generates rp_finance.Report (PBIR) for sm_finance.  Run: python3 build_rp_finance.py <report folder>

Design system (one place to change the look):
  canvas 1280x720, light slate page, white cards with soft shadow, navy nav bar with page tabs,
  header card (title, period, plain-English narrative, fiscal-year picker), KPI tiles with prior-year
  comparison in green/red, charts titled with a statement and subtitled with the question they answer.
"""
import json, sys, os, shutil

R = sys.argv[1]
VC = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.8.0/schema.json"
PAGE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"

# palette
NAV, NAVY, NAVY2, GOLD = "#0E1A2F", "#1B3A6B", "#5B7DB1", "#C9A227"
INK, MUTED, LINE, PAGE_BG, WHITE = "#1F2937", "#6B7280", "#E5E9F0", "#EEF2F7", "#FFFFFF"
GOOD, BAD, SOFT = "#15803D", "#B42318", "#A9B8CF"
FONT, FONT_B = "Segoe UI", "Segoe UI Semibold"
W, H, M = 1280, 720, 16           # page and outer margin
CW = W - 2 * M                     # content width

# ---------------------------------------------------------------- PBIR helpers
def lit(v):
    if isinstance(v, bool): s = "true" if v else "false"
    elif isinstance(v, int): s = f"{v}L"
    elif isinstance(v, float): s = f"{v}D"
    else: s = "'" + str(v).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": s}}}
def num(v): return {"expr": {"Literal": {"Value": f"{v}D"}}}
def col(c): return {"solid": {"color": lit(c)}}
def M_(n): return {"Measure": {"Expression": {"SourceRef": {"Entity": "_Measures"}}, "Property": n}}
def C(t, c): return {"Column": {"Expression": {"SourceRef": {"Entity": t}}, "Property": c}}
def mcol(n): return {"solid": {"color": {"expr": M_(n)}}}
def ref(f):
    k = "Measure" if "Measure" in f else "Column"
    return f"{f[k]['Expression']['SourceRef']['Entity']}.{f[k]['Property']}"
def proj(f, name=None):
    p = {"field": f, "queryRef": ref(f), "nativeQueryRef": f[list(f)[0]]["Property"]}
    if name: p["displayName"] = name
    return p
def props(**kw): return [{"properties": dict(kw)}]
def in_filter(name, table, column, values):
    return {"name": name, "field": C(table, column), "type": "Categorical",
            "filter": {"Version": 2, "From": [{"Name": "t", "Entity": table, "Type": 0}],
                       "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": column}}],
                                                         "Values": [[{"Literal": {"Value": f"'{v}'"}}] for v in values]}}}]}}
def series_sel(table, column, value):
    return {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0, "Left": C(table, column),
                                                 "Right": {"Literal": {"Value": f"'{value}'"}}}}}]}

def card_style(title=None, subtitle=None, bg=WHITE, transparent=False, shadow=True, radius=10, pad=10):
    o = {"background": props(show=lit(not transparent), color=col(bg), transparency=num(0)),
         "border": props(show=lit(False), radius=num(radius)),
         "dropShadow": props(show=lit(shadow and not transparent), color=col("#0F172A"), transparency=num(92),
                             position=lit("Outer"), preset=lit("Custom"), shadowSpread=num(0), shadowBlur=num(14),
                             angle=num(90), shadowDistance=num(2)),
         "padding": props(top=num(pad), bottom=num(pad), left=num(pad + 4), right=num(pad + 4)),
         "visualHeader": props(show=lit(not transparent))}
    if title:
        o["title"] = props(show=lit(True), text=lit(title), fontColor=col(INK), fontSize=num(12), bold=lit(True),
                           fontFamily=lit(FONT_B), alignment=lit("left"))
    else:
        o["title"] = props(show=lit(False))
    if subtitle:
        o["subTitle"] = props(show=lit(True), text=lit(subtitle), fontColor=col(MUTED), fontSize=num(9), fontFamily=lit(FONT))
    return o

pages = {}
def visual(page, name, vtype, x, y, w, h, query=None, objects=None, vco=None, filters=None, z=0, sort=None, extra=None):
    v = {"visualType": vtype, "drillFilterOtherVisuals": True}
    if query:
        v["query"] = {"queryState": {role: {"projections": ps} for role, ps in query.items()}}
        if sort: v["query"]["sortDefinition"] = {"sort": sort, "isDefaultSort": False}
    if objects: v["objects"] = objects
    v["visualContainerObjects"] = vco if vco is not None else card_style()
    if extra: v.update(extra)
    d = {"$schema": VC, "name": name, "position": {"x": x, "y": y, "z": z * 1000, "width": w, "height": h, "tabOrder": z * 1000}, "visual": v}
    if filters: d["filterConfig"] = {"filters": filters}
    pages[page]["visuals"].append(d)
    return d

def textbox(page, name, x, y, w, h, runs, bg=None, z=1, align="left", shadow=False, radius=10):
    paras = [{"textRuns": [{"value": t, "textStyle": s} for t, s in line], "horizontalTextAlignment": align} for line in runs]
    vco = card_style(bg=bg or WHITE, transparent=bg is None, shadow=shadow, radius=radius, pad=6)
    vco["visualHeader"] = props(show=lit(False))
    visual(page, name, "textbox", x, y, w, h, objects={"general": [{"properties": {"paragraphs": paras}}]}, vco=vco, z=z)

def panel(page, name, x, y, w, h, z=1, bg=WHITE, shadow=True, radius=10):
    """Empty rounded card used as a background behind grouped visuals."""
    textbox(page, name, x, y, w, h, [[(" ", {"fontSize": "8pt"})]], bg=bg, z=z, shadow=shadow, radius=radius)

def ts(size, color=INK, bold=False):
    return {"fontFamily": FONT_B if bold else FONT, "fontSize": f"{size}pt", "color": color}

def value_card(page, name, x, y, w, h, measure, size=11, color=INK, color_measure=None, z=3, units=0, bold=False):
    labels = {"color": mcol(color_measure) if color_measure else col(color), "fontSize": num(size),
              "fontFamily": lit(FONT_B if bold else FONT), "labelDisplayUnits": num(units), "labelPrecision": lit(1)}
    visual(page, name, "card", x, y, w, h, query={"Values": [proj(M_(measure), " ")]},
           objects={"labels": [{"properties": labels}], "categoryLabels": props(show=lit(False)),
                    "wordWrap": props(show=lit(True))},
           vco=card_style(transparent=True), z=z)

def multirow(page, name, x, y, w, h, measure, size=10, color=INK, z=3):
    """Left-aligned, wrapping text bound to a measure (narratives, period labels, banners)."""
    visual(page, name, "multiRowCard", x, y, w, h, query={"Values": [proj(M_(measure), " ")]},
           objects={"dataLabels": props(color=col(color), fontSize=num(size), fontFamily=lit(FONT)),
                    "categoryLabels": props(show=lit(False)),
                    "card": props(barShow=lit(False), outline=lit("None"), cardPadding=num(0), cardBackground=col(WHITE))},
           vco=card_style(transparent=True), z=z)

# ---------------------------------------------------------------- page chrome
ORDER = [("pg_overview", "Overview"), ("pg_recon", "Reconciliation"), ("pg_trust", "Data Trust")]

def new_page(pid, name):
    pages[pid] = {"page": {"$schema": PAGE, "name": pid, "displayName": name, "displayOption": "FitToPage",
                           "height": H, "width": W,
                           "objects": {"background": props(color=col(PAGE_BG), transparency=num(0)),
                                       "outspace": props(color=col(PAGE_BG), transparency=num(0))}},
                  "visuals": []}

def nav(page):
    textbox(page, f"{page}_nav", 0, 0, W, 48, [[(" ", {"fontSize": "8pt"})]], bg=NAV, z=1, radius=0)
    textbox(page, f"{page}_brand", 12, 6, 380, 36,
            [[("HARMONIA HALL", ts(9, GOLD, True)), ("   |   ", ts(11, "#5B6B85")), ("Finance", ts(13, WHITE, True))]], z=2)
    visual(page, f"{page}_tabs", "pageNavigator", 640, 9, 624, 30,
           objects={"fill": [{"properties": {"show": lit(True), "fillColor": col(NAV), "transparency": num(0)}, "selector": {"id": "default"}},
                             {"properties": {"fillColor": col("#1E2D49"), "transparency": num(0)}, "selector": {"id": "hover"}},
                             {"properties": {"fillColor": col(GOLD), "transparency": num(0)}, "selector": {"id": "selected"}}],
                    "text": [{"properties": {"fontColor": col("#C7D2E3"), "fontSize": num(10), "fontFamily": lit(FONT_B)}, "selector": {"id": "default"}},
                             {"properties": {"fontColor": col(WHITE)}, "selector": {"id": "hover"}},
                             {"properties": {"fontColor": col(NAV), "bold": lit(True)}, "selector": {"id": "selected"}}],
                    "outline": [{"properties": {"show": lit(False)}, "selector": {"id": "default"}}],
                    "shape": props(tileShape=lit("rectangleRounded"), rectangleRoundedCurve=num(14)),
                    "layout": props(cellPadding=num(8))},
           vco={"background": props(show=lit(False)), "border": props(show=lit(False)), "dropShadow": props(show=lit(False)),
                "title": props(show=lit(False)), "visualHeader": props(show=lit(False))},
           z=3, extra={})
    pages[page]["visuals"][-1]["howCreated"] = "InsertVisualButton"

def header(page, title, narrative_measure=None, narrative_text=None, slicer=True, period_text=None):
    y, h = 60, 78
    panel(page, f"{page}_hdr", M, y, CW, h)
    textbox(page, f"{page}_title", M + 12, y + 6, 360, 32, [[(title, ts(15, NAVY, True))]], z=3)
    if period_text:
        textbox(page, f"{page}_period", M + 12, y + 40, 380, 30, [[(period_text, ts(9, MUTED))]], z=3)
    else:
        multirow(page, f"{page}_period", M + 12, y + 38, 380, 34, "Period Label", size=9, color=MUTED)
    nx, nw = M + 404, (CW - 404 - 230) if slicer else (CW - 420)
    if narrative_measure:
        multirow(page, f"{page}_story", nx, y + 8, nw, h - 14, narrative_measure, size=10, color=INK)
    elif narrative_text:
        textbox(page, f"{page}_story", nx, y + 8, nw, h - 14, [[(narrative_text, ts(10, INK))]], z=3)
    if slicer:
        fy_slicer(page, M + CW - 214, y + 10)

def footer(page):
    multirow(page, f"{page}_fresh", M, H - 26, 900, 24, "Data Freshness Banner", size=8, color=MUTED)
    textbox(page, f"{page}_cert", W - M - 360, H - 26, 360, 24,
            [[("Certified model sm_finance  ·  Direct Lake on wh_gold", ts(8, MUTED))]], align="right", z=3)

def fy_slicer(page, x, y, default="FY2026"):
    sel = {"Version": 2, "From": [{"Name": "d", "Entity": "dim_date", "Type": 0}],
           "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "fiscal_year_label"}}],
                                             "Values": [[{"Literal": {"Value": f"'{default}'"}}]]}}}]}
    visual(page, f"{page}_fy", "slicer", x, y, 200, 58, query={"Values": [proj(C("dim_date", "fiscal_year_label"), "Fiscal year")]},
           objects={"data": props(mode=lit("Dropdown")), "selection": props(singleSelect=lit(True), strictSingleSelect=lit(True)),
                    "header": props(show=lit(True), fontColor=col(MUTED), textSize=num(9), fontFamily=lit(FONT)),
                    "items": props(fontColor=col(INK), textSize=num(11), fontFamily=lit(FONT_B), background=col("#F5F7FA")),
                    "general": [{"properties": {"filter": {"filter": sel}}}]},
           vco=card_style(transparent=True), z=4,
           extra={"syncGroup": {"groupName": "fiscal_year", "fieldChanges": True, "filterChanges": True}})

def kpi_tile(page, name, x, y, w, label, measure, caption_measure=None, caption=None, color_measure=None,
             accent=NAVY, units=0, value_color=INK):
    h = 104
    panel(page, f"{name}_bg", x, y, w, h, z=1)
    textbox(page, f"{name}_bar", x, y + 16, 4, h - 32, [[(" ", {"fontSize": "6pt"})]], bg=accent, z=2, radius=2)
    textbox(page, f"{name}_lbl", x + 12, y + 8, w - 20, 24, [[(label, ts(9, MUTED, True))]], z=3)
    value_card(page, f"{name}_val", x + 8, y + 28, w - 16, 44, measure, size=22, color=value_color, units=units, bold=True)
    if caption_measure:
        value_card(page, f"{name}_cap", x + 8, y + 72, w - 16, 26, caption_measure, size=9, color_measure=color_measure, color=MUTED)
    elif caption:
        textbox(page, f"{name}_cap", x + 8, y + 74, w - 16, 24, [[(caption, ts(9, MUTED))]], align="center", z=3)

def kpi_row(page, tiles, y=150):
    n, gap = len(tiles), 12
    w = (CW - gap * (n - 1)) // n
    for i, t in enumerate(tiles):
        kpi_tile(page, f"{page}_k{i}", M + i * (w + gap), y, w, **t)

def table_style():
    return {"columnHeaders": props(fontColor=col(MUTED), backColor=col(WHITE), fontFamily=lit(FONT_B), fontSize=num(9),
                                   outline=lit("BottomOnly"), outlineColor=col(LINE), wordWrap=lit(True)),
            "rowHeaders": props(fontColor=col(INK), fontSize=num(10), fontFamily=lit(FONT)),
            "values": props(fontColor=col(INK), fontSize=num(10), fontFamily=lit(FONT), backColorSecondary=col("#F8FAFC")),
            "grid": props(gridHorizontal=lit(True), gridHorizontalColor=col(LINE), gridVertical=lit(False), rowPadding=num(5),
                          outlineColor=col(LINE)),
            "total": props(fontColor=col(NAVY), fontFamily=lit(FONT_B), backColor=col("#F1F5F9"))}

def axis_style(units=0):
    return {"valueAxis": props(show=lit(True), labelDisplayUnits=num(units), fontSize=num(9), labelColor=col(MUTED),
                               gridlineShow=lit(True), gridlineColor=col(LINE), gridlineStyle=lit("dotted"), showAxisTitle=lit(False)),
            "categoryAxis": props(fontSize=num(9), labelColor=col(MUTED), showAxisTitle=lit(False)),
            "legend": props(show=lit(True), position=lit("TopRight"), fontSize=num(9), labelColor=col(MUTED))}

TI = ("Time Intelligence", "Calculation")

# ================================================================= Page 1: Overview
p = "pg_overview"
new_page(p, "Overview"); nav(p)
header(p, "Finance Performance Pulse", narrative_measure="Finance Narrative")
kpi_row(p, [
    dict(label="REVENUE", measure="Revenue FYTD", caption_measure="Revenue vs PY", color_measure="Revenue vs PY Color", accent=NAVY),
    dict(label="EXPENSES", measure="Expenses FYTD", caption_measure="Expenses vs PY", color_measure="Expenses vs PY Color", accent=NAVY2),
    dict(label="NET SURPLUS", measure="Net Surplus FYTD", caption_measure="Net Surplus vs PY", color_measure="Net Surplus vs PY Color", accent=GOLD),
    dict(label="SURPLUS MARGIN", measure="Surplus Margin FYTD", caption_measure="Surplus Margin vs PY", color_measure="Surplus Margin vs PY Color", accent=GOLD),
    dict(label="CONTRIBUTED REVENUE", measure="Contributed Revenue FYTD", caption_measure="Contributed Revenue vs PY", color_measure="Contributed Revenue vs PY Color", accent="#8FA9C9"),
    dict(label="EARNED REVENUE SHARE", measure="Earned Revenue % FYTD", caption_measure="Earned Revenue % vs PY", color_measure="Earned Revenue % vs PY Color", accent="#8FA9C9"),
])
r2y, r2h = 266, 206
visual(p, "ov_trend", "lineChart", M, r2y, 612, r2h,
       query={"Category": [proj(C("dim_date", "month_name"), "Month")], "Y": [proj(M_("Revenue"))],
              "Series": [proj(C(*TI), "Year")]},
       sort=[{"field": C("dim_date", "month_name"), "direction": "Ascending"}],
       filters=[in_filter("ov_trend_ti", *TI, ["Current", "PY"])],
       objects={**axis_style(1000000),
                "dataPoint": [{"properties": {"fill": col(NAVY)}, "selector": series_sel(*TI, "Current")},
                              {"properties": {"fill": col(SOFT)}, "selector": series_sel(*TI, "PY")}],
                "lineStyles": [{"properties": {"strokeWidth": num(3), "showMarker": lit(True), "markerSize": num(4)}},
                               {"properties": {"lineStyle": lit("dashed"), "strokeWidth": num(2)}, "selector": series_sel(*TI, "PY")}]},
       vco=card_style("Revenue by month, this year vs last", "Is the season pacing ahead of last year? Dashed line = prior year."), z=3)
visual(p, "ov_dept", "clusteredBarChart", M + 624, r2y, CW - 624, r2h,
       query={"Category": [proj(C("dim_department", "department_name"), "Department")], "Y": [proj(M_("Expenses"))],
              "Series": [proj(C(*TI), "Period")]},
       sort=[{"field": M_("Expenses"), "direction": "Descending"}],
       filters=[in_filter("ov_dept_ti", *TI, ["FYTD", "PY FYTD"])],
       objects={**axis_style(1000000),
                "dataPoint": [{"properties": {"fill": col(NAVY2)}, "selector": series_sel(*TI, "FYTD")},
                              {"properties": {"fill": col("#D5DDE8")}, "selector": series_sel(*TI, "PY FYTD")}],
                "labels": props(show=lit(False))},
       vco=card_style("Where the money goes", "Expenses by department, year to date vs the same period last year"), z=3)
r3y, r3h = 484, H - 26 - 8 - 484
visual(p, "ov_statement", "pivotTable", M, r3y, 740, r3h,
       query={"Rows": [proj(C("dim_account", "account_type"), "Line"), proj(C("dim_account", "account_group"), "Group")],
              "Columns": [proj(C(*TI), " ")],
              "Values": [proj(M_("Statement Amount"), "Amount")]},
       filters=[in_filter("ov_statement_ti", *TI, ["FYTD", "PY FYTD", "FYTD vs PY", "FYTD vs PY %"])],
       objects={**table_style(), "rowHeaders": props(fontColor=col(INK), fontSize=num(10), stepped=lit(True), fontFamily=lit(FONT))},
       vco=card_style("Income statement", "Year to date vs the same period last year · bottom row = net surplus"), z=3)
visual(p, "ov_fund", "donutChart", M + 752, r3y, CW - 752, r3h,
       query={"Category": [proj(C("dim_fund", "fund_name"), "Fund")], "Y": [proj(M_("Revenue"))]},
       objects={"legend": props(show=lit(True), position=lit("Right"), fontSize=num(9), labelColor=col(INK)),
                "labels": props(show=lit(True), labelStyle=lit("Percent of total"), fontSize=num(9), color=col(INK)),
                "slices": props(innerRadiusRatio=num(68))},
       vco=card_style("Revenue by fund", "How much of this year's revenue comes with donor restrictions?"), z=3)
footer(p)

# ================================================================= Page 2: Reconciliation
p = "pg_recon"
new_page(p, "Reconciliation"); nav(p)
header(p, "Revenue Reconciliation",
       narrative_text="Every night Tessitura (tickets, subscriptions, gifts) and Diese (hall rentals) are matched to the MIP ledger "
                      "by month, revenue stream and fund. A line ties out when the gap is within the larger of $1,000 or 1%. "
                      "Anything else lands below until finance records the cause.")
kpi_row(p, [
    dict(label="SOURCE SYSTEMS", measure="Source Amount", caption="Tessitura + Diese", accent=NAVY2),
    dict(label="GENERAL LEDGER", measure="Ledger Amount", caption="MIP fund accounting", accent=NAVY),
    dict(label="NET VARIANCE", measure="Variance", caption="Ledger minus source", accent=GOLD),
    dict(label="RECONCILED", measure="Reconciled %", caption="Lines within tolerance", accent=GOOD, value_color=GOOD),
    dict(label="TO INVESTIGATE", measure="Lines to Investigate", caption="Lines outside tolerance", accent=BAD, value_color=BAD),
    dict(label="STILL OPEN", measure="Open Items", caption="No cause recorded yet", accent=BAD, value_color=BAD),
])
visual(p, "rc_grid", "pivotTable", M, r2y, 612, r2h,
       query={"Rows": [proj(C("dim_date", "month_name"), "Month")],
              "Columns": [proj(C("recon_revenue_to_gl", "revenue_stream"), "Stream")],
              "Values": [proj(M_("Variance"))]},
       objects={**table_style(),
                "values": [{"properties": {"fontColor": col(INK), "fontSize": num(10), "fontFamily": lit(FONT)}},
                           {"properties": {"backColor": mcol("Recon Status Color")},
                            "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": "_Measures.Variance"}}]},
       vco=card_style("Variance heatmap", "Which months and streams don't tie out? Red = outside tolerance"), z=3)
visual(p, "rc_trend", "clusteredColumnChart", M + 624, r2y, CW - 624, r2h,
       query={"Category": [proj(C("dim_date", "month_name"), "Month")], "Y": [proj(M_("Variance"))],
              "Series": [proj(C("recon_revenue_to_gl", "revenue_stream"), "Stream")]},
       sort=[{"field": C("dim_date", "month_name"), "direction": "Ascending"}],
       objects={**axis_style(1000)},
       vco=card_style("Where the gaps are", "Ledger minus source by month · a cut-off shows as a pair of mirrored bars"), z=3)
visual(p, "rc_lines", "tableEx", M, r3y, CW, r3h,
       query={"Values": [proj(C("recon_revenue_to_gl", "month_start"), "Month"), proj(C("recon_revenue_to_gl", "revenue_stream"), "Stream"),
                         proj(C("recon_revenue_to_gl", "fund_code"), "Fund"), proj(M_("Source Amount"), "Source"),
                         proj(M_("Ledger Amount"), "Ledger"), proj(M_("Variance")), proj(C("recon_revenue_to_gl", "cause"), "Cause"),
                         proj(C("recon_revenue_to_gl", "resolution"), "Status")]},
       sort=[{"field": M_("Abs Variance"), "direction": "Descending"}],
       filters=[in_filter("rc_lines_status", "recon_revenue_to_gl", "status", ["Investigate"])],
       objects=table_style(),
       vco=card_style("Lines to investigate", "Biggest gaps first · finance records the cause in fin.recon_note and it shows here the next morning"), z=3)
footer(p)

# ================================================================= Page 3: Data Trust
p = "pg_trust"
new_page(p, "Data Trust"); nav(p)
header(p, "Data Trust",
       narrative_text="Can I rely on these numbers? This page shows when each source was last loaded, whether the ledger balances "
                      "and how much of the revenue reconciliation is still open. It is the same evidence the platform checks every night.",
       slicer=False, period_text="Live status · not filtered by fiscal year")
kpi_row(p, [
    dict(label="SOURCES ON TIME", measure="Sources Fresh", caption="Loaded within their expected refresh", accent=GOOD, value_color=GOOD),
    dict(label="LEDGER DATA THROUGH", measure="As Of Date", caption="Last date with activity in MIP", accent=NAVY),
    dict(label="OUT OF BALANCE", measure="Out of Balance", caption="Debits minus credits · must be $0.00", accent=GOOD),
    dict(label="RECONCILED", measure="Reconciled %", caption="Revenue lines within tolerance", accent=GOLD),
])
visual(p, "tr_fresh", "tableEx", M, r2y, CW, r2h,
       query={"Values": [proj(C("source_freshness", "source_name"), "Source"), proj(C("source_freshness", "expected_refresh"), "Expected"),
                         proj(C("source_freshness", "last_loaded_et"), "Last loaded (ET)"), proj(M_("Data Through"), "Data through"),
                         proj(M_("Hours Since Load"), "Hours since load"), proj(M_("Freshness Status"), "Status")]},
       objects={**table_style(),
                "values": [{"properties": {"fontColor": col(INK), "fontSize": num(11), "fontFamily": lit(FONT)}},
                           {"properties": {"fontColor": mcol("Freshness Color")},
                            "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": "_Measures.Freshness Status"}}]},
       vco=card_style("Source freshness", "Daily sources go Stale after 26 hours, weekly ones after 8 days"), z=3)
panel(p, "tr_notes_bg", M, r3y, CW, r3h, z=1)
textbox(p, "tr_notes", M + 12, r3y + 8, CW - 24, r3h - 16,
        [[("How these checks work", ts(12, INK, True))],
         [("•  Every journal in the ledger balances; Out of balance must be $0.00.", ts(10))],
         [("•  Tessitura and Diese revenue are reconciled to the ledger every night; lines outside tolerance stay on the Reconciliation page until finance explains them.", ts(10))],
         [("•  Freshness comes from the platform's run log: a source counts as current when the nightly run checked it, even if nothing changed.", ts(10))],
         [("•  Every number comes from the certified semantic model sm_finance, so Excel, this report and SQL users see the same figures.", ts(10))]],
        z=3)
footer(p)

# ================================================================= write
d = os.path.join(R, "definition"); pd = os.path.join(d, "pages")
if os.path.isdir(pd): shutil.rmtree(pd)
order = [pid for pid, _ in ORDER]
for pid in order:
    os.makedirs(os.path.join(pd, pid, "visuals"))
    json.dump(pages[pid]["page"], open(os.path.join(pd, pid, "page.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    for v in pages[pid]["visuals"]:
        vd = os.path.join(pd, pid, "visuals", v["name"]); os.makedirs(vd)
        json.dump(v, open(os.path.join(vd, "visual.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
json.dump({"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
           "pageOrder": order, "activePageName": order[0]}, open(os.path.join(pd, "pages.json"), "w"), indent=2)

theme = {"name": "Harmonia Finance",
         "dataColors": [NAVY, GOLD, "#8FA9C9", NAVY2, "#94A3B8", "#D9C27A", "#3F5E8C", "#CBD5E1", "#7C6A2E", "#A9B8CF"],
         "background": WHITE, "foreground": INK, "tableAccent": NAVY, "good": GOOD, "neutral": GOLD, "bad": BAD,
         "maximum": NAVY, "center": "#F8FAFC", "minimum": "#FDECEC",
         "textClasses": {"callout": {"fontSize": 22, "fontFace": FONT_B, "color": INK},
                         "title": {"fontSize": 12, "fontFace": FONT_B, "color": INK},
                         "header": {"fontSize": 10, "fontFace": FONT_B, "color": INK},
                         "label": {"fontSize": 9, "fontFace": FONT, "color": MUTED}},
         "visualStyles": {"page": {"*": {"background": [{"color": {"solid": {"color": PAGE_BG}}, "transparency": 0}],
                                         "outspace": [{"color": {"solid": {"color": PAGE_BG}}, "transparency": 0}]}},
                          "*": {"*": {"border": [{"show": False}],
                                      "title": [{"fontColor": {"solid": {"color": INK}}, "fontSize": 12, "fontFamily": FONT_B}]}}}}
rr = os.path.join(R, "StaticResources", "RegisteredResources"); os.makedirs(rr, exist_ok=True)
json.dump(theme, open(os.path.join(rr, "HarmoniaFinance.json"), "w"), indent=2)
rj = json.load(open(os.path.join(d, "report.json")))
rv = rj["themeCollection"]["baseTheme"]["reportVersionAtImport"]
rj["themeCollection"]["customTheme"] = {"name": "HarmoniaFinance.json", "reportVersionAtImport": rv, "type": "RegisteredResources"}
rj["resourcePackages"] = [x for x in rj["resourcePackages"] if x["name"] != "RegisteredResources"] + [
    {"name": "RegisteredResources", "type": "RegisteredResources", "items": [{"name": "HarmoniaFinance.json", "path": "HarmoniaFinance.json", "type": "CustomTheme"}]}]
json.dump(rj, open(os.path.join(d, "report.json"), "w"), indent=2)
json.dump({"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
           "version": "4.0", "datasetReference": {"byPath": {"path": "../sm_finance.SemanticModel"}}},
          open(os.path.join(R, "definition.pbir"), "w"), indent=2)
print("pages:", {pid: len(pages[pid]["visuals"]) for pid in order})

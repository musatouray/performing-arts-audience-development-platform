"""Generates rp_finance.Report (PBIR) for sm_finance.
Run from the repo root:  python scripts/bi/build_rp_finance.py fabric/bi-finance/rp_finance.Report

Layout standard (mirrors the team's reference report):
  page 1920 x 1080 (16:9), vertical alignment top, 30px outer margin left/right, 30px between visuals.
  every visual: 10px padding, 8px rounded corners (set once in the theme scripts/bi/harmonia_finance_theme.json).
  KPI strip: one new card visual (cardVisual), 1860 x 180, 2px accent bar, PY reference label + coloured change pill.
  main trend: line chart, at least 1230 x 340.
"""
import json, os, shutil, sys, uuid

R = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
VC = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.8.0/schema.json"
PAGE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"

# ---------------------------------------------------------------- design tokens
NAVY, BLUE, GOLD = "#1E3A5F", "#0078D4", "#C9A227"
INK, SLATE, LINE, WHITE, PAGE_BG = "#1E3A5F", "#607D8B", "#E0E0E0", "#FFFFFF", "#F3F5F8"
GOOD, BAD, PY_GREY = "#2E7D32", "#D84315", "#B0BEC5"
FONT, FONT_B = "Segoe UI", "Segoe UI Semibold"
W, H = 1920, 1080
M = G = 30                       # outer margin and gutter
CW = W - 2 * M                   # 1860 content width
NAV_H, STRIP_H = 64, 4
HDR_Y, HDR_H = NAV_H + STRIP_H + G, 82          # 98
KPI_Y, KPI_H = HDR_Y + HDR_H + G, 180           # 210
R2_Y, R2_H = KPI_Y + KPI_H + G, 340             # 420
R3_Y = R2_Y + R2_H + G                          # 790
R3_H = H - G - R3_Y                             # 260
LEFT_W = 1230                                   # main column (line chart minimum width)
RIGHT_X, RIGHT_W = M + LEFT_W + G, CW - LEFT_W - G   # 1290, 600

# ---------------------------------------------------------------- PBIR helpers
def lit(v):
    if isinstance(v, bool): s = "true" if v else "false"
    elif isinstance(v, int): s = f"{v}L"
    elif isinstance(v, float): s = f"{v}D"
    else: s = "'" + str(v).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": s}}}
def num(v): return {"expr": {"Literal": {"Value": f"{v}D"}}}
def col(c): return {"solid": {"color": lit(c)}}
def Mf(n): return {"Measure": {"Expression": {"SourceRef": {"Entity": "_Measures"}}, "Property": n}}
def Cf(t, c): return {"Column": {"Expression": {"SourceRef": {"Entity": t}}, "Property": c}}
def mexpr(n): return {"expr": Mf(n)}
def mcol(n): return {"solid": {"color": {"expr": Mf(n)}}}
def ref(f):
    k = "Measure" if "Measure" in f else "Column"
    return f"{f[k]['Expression']['SourceRef']['Entity']}.{f[k]['Property']}"
def proj(f, name=None):
    p = {"field": f, "queryRef": ref(f), "nativeQueryRef": f[list(f)[0]]["Property"]}
    if name: p["displayName"] = name
    return p
def props(**kw): return [{"properties": dict(kw)}]
def sel_props(selector, **kw): return {"properties": dict(kw), "selector": selector}
def meta(m): return {"metadata": f"_Measures.{m}"}
def in_filter(name, table, column, values):
    return {"name": name, "field": Cf(table, column), "type": "Categorical",
            "filter": {"Version": 2, "From": [{"Name": "t", "Entity": table, "Type": 0}],
                       "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": column}}],
                                                         "Values": [[{"Literal": {"Value": f"'{v}'"}}] for v in values]}}}]}}
def series_sel(table, column, value):
    return {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0, "Left": Cf(table, column),
                                                 "Right": {"Literal": {"Value": f"'{value}'"}}}}}]}
def fid(*parts): return "field-" + str(uuid.uuid5(uuid.NAMESPACE_URL, "rp_finance/" + "/".join(parts)))

def titled(title=None, subtitle=None, title_measure=None, subtitle_measure=None, divider=False):
    """Container formatting for a chart card. Background, border radius, shadow and padding come from the theme."""
    o = {}
    if title or title_measure:
        o["title"] = props(show=lit(True), text=mexpr(title_measure) if title_measure else lit(title))
    else:
        o["title"] = props(show=lit(False))
    if subtitle or subtitle_measure:
        o["subTitle"] = props(show=lit(True), text=mexpr(subtitle_measure) if subtitle_measure else lit(subtitle))
    else:
        o["subTitle"] = props(show=lit(False))
    o["divider"] = props(show=lit(divider))
    return o

def bare():
    return {"title": props(show=lit(False)), "subTitle": props(show=lit(False)), "background": props(show=lit(False)),
            "border": props(show=lit(False)), "dropShadow": props(show=lit(False)), "visualHeader": props(show=lit(False)),
            "padding": props(top=num(0), bottom=num(0), left=num(0), right=num(0))}

pages = {}
def visual(page, name, vtype, x, y, w, h, z, query=None, objects=None, vco=None, filters=None, sort=None, extra=None, how=None):
    v = {"visualType": vtype, "drillFilterOtherVisuals": True}
    if query:
        qs = {}
        for role, ps in query.items():
            qs[role] = ps if isinstance(ps, dict) else {"projections": ps}
        v["query"] = {"queryState": qs}
        if sort: v["query"]["sortDefinition"] = {"sort": sort, "isDefaultSort": False}
    if objects: v["objects"] = objects
    if vco is not None: v["visualContainerObjects"] = vco
    if extra: v.update(extra)
    d = {"$schema": VC, "name": name, "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z}, "visual": v}
    if filters: d["filterConfig"] = {"filters": filters}
    if how: d["howCreated"] = how
    pages[page]["visuals"].append(d)

def ts(size, color=INK, bold=False):
    return {"fontFamily": FONT_B if bold else FONT, "fontSize": f"{size}pt", "color": color}

def textbox(page, name, x, y, w, h, z, paragraphs, vco=None):
    """paragraphs: list of lists of (text | ('m', measure), style). Measure runs render the measure's current value."""
    paras, values = [], []
    for line in paragraphs:
        runs = []
        for content, style in line:
            if isinstance(content, tuple):
                sid = content[1].replace(" ", "").replace("%", "Pct")
                runs.append({"value": {"propertyIdentifier": {"objectName": "values", "propertyName": "expr"}, "selector": {"id": sid}},
                             "textStyle": style})
                values.append({"properties": {"expr": {"expr": {"Min": {"Expression": {"Column": {
                    "Expression": {"Subquery": {"Query": {"Version": 2, "From": [{"Name": "_", "Entity": "_Measures", "Type": 0}],
                                                          "Select": [{"Measure": {"Expression": {"SourceRef": {"Source": "_"}}, "Property": content[1]},
                                                                      "Name": f"_Measures.{content[1]}"}]}}},
                    "Property": f"_Measures.{content[1]}"}}, "IncludeAllTypes": 1}}}}, "selector": {"id": sid}})
            else:
                runs.append({"value": content, "textStyle": style})
        paras.append({"textRuns": runs})
    obj = {"general": [{"properties": {"paragraphs": paras}}]}
    if values: obj["values"] = values
    visual(page, name, "textbox", x, y, w, h, z, objects=obj, vco=vco or bare())

def shape(page, name, x, y, w, h, z, fill, rounded=True, shadow=False, outline=None):
    visual(page, name, "shape", x, y, w, h, z,
           objects={"shape": props(tileShape=lit("rectangleRounded" if rounded else "rectangle"), roundEdge=num(8 if rounded else 0)),
                    "fill": [sel_props({"id": "default"}, fillColor=col(fill), transparency=num(0)), {"properties": {"show": lit(True)}}],
                    "outline": [{"properties": {"show": lit(bool(outline))}}] + ([sel_props({"id": "default"}, lineColor=col(outline), weight=num(1))] if outline else [])},
           vco={**bare(), "dropShadow": props(show=lit(shadow), preset=lit("Custom"), position=lit("Outer"), color=col(LINE),
                                              transparency=num(92), shadowBlur=num(4), shadowDistance=num(2), angle=num(90), shadowSpread=num(0))})

# ---------------------------------------------------------------- page chrome
# Page order. The tabs show the first four; the last three are hidden and opened from buttons.
ORDER = [("pg_overview", "Overview"), ("pg_statement", "Statement of Activities"), ("pg_cash", "Cash Flow"),
         ("pg_recon", "Reconciliation"), ("pg_revenue", "Revenue Detail"), ("pg_expense", "Expense Detail"),
         ("pg_trust", "About the Data")]
HIDDEN = {"pg_revenue", "pg_expense", "pg_trust"}

def new_page(pid, name):
    pages[pid] = {"page": {"$schema": PAGE, "name": pid, "displayName": name, "displayOption": "FitToPage", "height": H, "width": W,
                           "objects": {"background": props(color=col(PAGE_BG), transparency=num(0)),
                                       "outspace": props(color=col(PAGE_BG), transparency=num(0)),
                                       "displayArea": props(verticalAlignment=lit("Top"))}},
                  "visuals": []}
    if pid in HIDDEN:
        pages[pid]["page"]["visibility"] = "HiddenInViewMode"

def button(page, name, x, y, w, h, text, target=None, back=False, icon=None, solid=False, z=4000, tooltip=None):
    """A button that opens another page (target) or goes back. Solid = filled blue, otherwise a light outline."""
    link = {"show": lit(True), "type": lit("Back" if back else "PageNavigation"), "showDefaultTooltip": lit(False)}
    if target:
        link["navigationSection"] = lit(target)
    if tooltip:
        link["tooltip"] = lit(tooltip)
    fg, bg = (WHITE, BLUE) if solid else (BLUE, WHITE)
    visual(page, name, "actionButton", x, y, w, h, z, how="InsertVisualButton",
           objects={"icon": [sel_props({"id": "default"}, shapeType=lit(icon or "blank"), lineColor=col(fg), lineWeight=num(2)),
                             {"properties": {"show": lit(bool(icon))}}],
                    "text": [sel_props({"id": "default"}, show=lit(bool(text)), text=lit(text or ""), fontColor=col(fg), fontSize=num(10),
                                       fontFamily=lit(FONT_B), horizontalAlignment=lit("center"), verticalAlignment=lit("middle")),
                             sel_props({"id": "hover"}, fontColor=col(WHITE))],
                    "fill": [sel_props({"id": "default"}, show=lit(True), fillColor=col(bg), transparency=num(0)),
                             sel_props({"id": "hover"}, fillColor=col("#106EBE"), transparency=num(0))],
                    "outline": [sel_props({"id": "default"}, show=lit(True), lineColor=col(BLUE), weight=num(1), roundEdge=num(6))],
                    "shape": props(roundEdge=num(6))},
           vco={**bare(), "visualLink": props(**link)})

def tile_x(i, n):
    """Left edge of tile i in a KPI strip of n tiles (card padding 12, 30px between tiles)."""
    w = (CW - 24 - 30 * (n - 1)) / n
    return M + 12 + i * (w + 30), w

def detail_button(page, name, i, n, target):
    x, w = tile_x(i, n)
    button(page, name, round(x + w - 96), KPI_Y + 12, 88, 26, "Details  \u203a", target=target, tooltip="Open the breakdown")

def nav(page):
    shape(page, f"{page}_navbg", 0, 0, W, NAV_H, 0, NAVY, rounded=False)
    shape(page, f"{page}_strip", 0, NAV_H, W, STRIP_H, 0, GOLD, rounded=False)
    textbox(page, f"{page}_brand", M, 8, 300, 48, 1000,
            [[("HARMONIA HALL", ts(9, GOLD, True))], [("Finance", ts(14, WHITE, True))]])
    visual(page, f"{page}_tabs", "pageNavigator", 600, 0, W - 600 - M, NAV_H, 2000, how="InsertVisualButton",
           objects={"shape": props(tileShape=lit("rectangleRoundedByPixel"), rectangleRoundedCurve=num(4), roundEdge=num(4)),
                    "fill": [sel_props({"id": "default"}, show=lit(True), fillColor=col(NAVY), transparency=num(100)),
                             sel_props({"id": "selected"}, show=lit(True), fillColor=col(BLUE), transparency=num(0)),
                             sel_props({"id": "hover"}, show=lit(True), fillColor=col("#106EBE"), transparency=num(0))],
                    "outline": [{"properties": {"show": lit(False)}}],
                    "text": [sel_props({"id": "default"}, show=lit(True), fontFamily=lit(FONT_B), fontSize=num(10), fontColor=col("#C9D3E0"),
                                       horizontalAlignment=lit("center"), verticalAlignment=lit("middle"), bold=lit(False)),
                             sel_props({"id": "selected"}, fontColor=col(WHITE)),
                             sel_props({"id": "hover"}, fontColor=col(WHITE))],
                    "layout": props(cellPadding=num(12))},
           vco={**bare(), "padding": props(top=num(12), bottom=num(12), left=num(0), right=num(0))})

def header(page, title, narrative=None, narrative_measure=None, slicer=True, period_text=None, back=False, info=True):
    shape(page, f"{page}_hdrbg", M, HDR_Y, CW, HDR_H, 0, WHITE, shadow=True, outline=LINE)
    if back:
        bx = M + CW - (250 if slicer else 0) - 120
        button(page, f"{page}_back", bx, HDR_Y + 24, 104, 34, "\u2039  Back", back=True)
    elif info:
        bx = M + CW - (250 if slicer else 0) - 56
        button(page, f"{page}_about", bx, HDR_Y + 24, 40, 34, "i", target="pg_trust", tooltip="About the data")
    period = [(period_text, ts(10, SLATE))] if period_text else [(("m", "Period Label"), ts(10, SLATE))]
    textbox(page, f"{page}_title", M + 20, HDR_Y + 12, 360, 60, 1000, [[(title, ts(14, INK, True))], period])
    # narrative between the title and the buttons/slicer on the right
    right = (250 if slicer else 0) + (130 if back else 70 if info else 0)
    nx, nw = M + 400, CW - 400 - right - 20
    story = [(("m", narrative_measure), ts(11, INK))] if narrative_measure else [(narrative, ts(11, INK))]
    textbox(page, f"{page}_story", nx, HDR_Y + 8, nw, 46, 1000, [story])
    textbox(page, f"{page}_fresh", nx, HDR_Y + 54, nw, 22, 1000, [[(("m", "Data Freshness Banner"), ts(9, SLATE))]])
    if slicer:
        fy_slicer(page, M + CW - 250, HDR_Y + 10)

def fy_slicer(page, x, y, default="FY2026"):
    sel = {"Version": 2, "From": [{"Name": "d", "Entity": "dim_date", "Type": 0}],
           "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "fiscal_year_label"}}],
                                             "Values": [[{"Literal": {"Value": f"'{default}'"}}]]}}}]}
    visual(page, f"{page}_fy", "slicer", x, y, 230, 62, 3000, query={"Values": [proj(Cf("dim_date", "fiscal_year_label"), "Fiscal year")]},
           objects={"data": props(mode=lit("Dropdown")), "selection": props(singleSelect=lit(True), strictSingleSelect=lit(True)),
                    "header": props(show=lit(True), fontColor=col(SLATE), textSize=num(9)),
                    "items": props(fontColor=col(INK), textSize=num(11), background=col(WHITE)),
                    "general": [{"properties": {"filter": {"filter": sel}}}]},
           filters=[{"name": f"{page}_fy_real_years", "field": Cf("dim_date", "fiscal_year_label"), "type": "Categorical",
                     "filter": {"Version": 2, "From": [{"Name": "d", "Entity": "dim_date", "Type": 0}],
                                "Where": [{"Condition": {"Not": {"Expression": {"In": {
                                    "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "fiscal_year_label"}}],
                                    "Values": [[{"Literal": {"Value": "'Unknown'"}}], [{"Literal": {"Value": "null"}}]]}}}}}]}}],
           vco=bare(), extra={"syncGroup": {"groupName": "fiscal_year", "fieldChanges": True, "filterChanges": True}})

def kpi_strip(page, name, kpis):
    """New card visual: one tile per measure. kpis: dicts with measure, label, accent, units, precision,
    and optionally py (reference value), detail / detail_color / detail_bg (change pill)."""
    o = {k: [] for k in ("value", "label", "accentBar", "referenceLabel", "referenceLabelTitle", "referenceLabelValue",
                         "referenceLabelDetail")}
    o["value"].append(sel_props({"id": "default"}, fontSize=num(25), fontFamily=lit(FONT_B), fontColor=col(INK)))
    o["label"].append(sel_props({"id": "default"}, position=lit("aboveValue"), fontSize=num(12), fontColor=col(SLATE), fontFamily=lit(FONT), bold=lit(False)))
    o["accentBar"].append(sel_props({"id": "default"}, show=lit(True), color=col(BLUE), width=num(2)))
    o["referenceLabel"].append(sel_props({"id": "default"}, paddingUniform=lit(10)))
    o["referenceLabelTitle"].append(sel_props({"id": "default"}, titleFontSize=num(11), titleFontFamily=lit(FONT), titleFontColor=col(SLATE)))
    o["referenceLabelValue"].append(sel_props({"id": "default"}, valueFontSize=num(11), valueFontFamily=lit(FONT), valueFontColor=col(INK), valueBold=lit(True)))
    o["referenceLabelDetail"].append(sel_props({"id": "default"}, show=lit(True), detailFontSize=num(11), detailFontFamily=lit(FONT)))
    for k in kpis:
        m = k["measure"]
        o["value"].append(sel_props(meta(m), labelDisplayUnits=num(k.get("units", 1)), labelPrecision=lit(k.get("precision", 0)),
                                    **({"fontColor": col(k["value_color"])} if k.get("value_color") else {})))
        o["label"].append(sel_props(meta(m), text=lit(k["label"])))
        o["accentBar"].append(sel_props(meta(m), color=col(k.get("accent", BLUE)), width=num(2)))
        if k.get("py"):
            f = fid(page, m)
            o["referenceLabel"].append(sel_props({"data": [{"dataViewWildcard": {"matchingOption": 0}}], **meta(m), "id": f, "order": 0},
                                                 value=mexpr(k["py"])))
            o["referenceLabelTitle"].append(sel_props({**meta(m), "id": f}, titleContentType=lit("custom"), titleText=lit(k.get("ref_title", "PY"))))
            o["referenceLabelValue"].append(sel_props({**meta(m), "id": f}, valueDisplayUnits=num(k.get("units", 1)),
                                                      valuePrecision=lit(k.get("precision", 0)), valueBold=lit(True)))
            o["referenceLabelDetail"].append(sel_props({**meta(m), "id": f}, show=lit(True), detailTransparency=num(0)))
            o["referenceLabelDetail"].append(sel_props({"data": [{"dataViewWildcard": {"matchingOption": 0}}], **meta(m), "id": f},
                                                       detailValue=mexpr(k["detail"]), detailFontColor=mcol(k["detail_color"]),
                                                       detailBackgroundColor=mcol(k["detail_bg"])))
        elif k.get("caption"):
            # caption-only reference label: custom title text, empty value
            f = fid(page, m, "caption")
            o["referenceLabel"].append(sel_props({"data": [{"dataViewWildcard": {"matchingOption": 0}}], **meta(m), "id": f, "order": 0},
                                                 value=mexpr("Caption")))
            o["referenceLabelTitle"].append(sel_props({**meta(m), "id": f}, titleContentType=lit("custom"), titleText=lit(k["caption"])))
            o["referenceLabelValue"].append(sel_props({**meta(m), "id": f}, valueFontColor=col(WHITE), valueFontSize=num(6)))
            o["referenceLabelDetail"].append(sel_props({**meta(m), "id": f}, show=lit(False)))
    o["referenceLabelLayout"] = [sel_props({"id": "default"}, labelSpace=num(2), style=lit("sentence"), verticalAlignment=lit("top"),
                                           arrangement=lit("rows"), horizontalAlignment=lit("left"))]
    o["layout"] = [sel_props({"id": "default"}, paddingUniform=lit(0)), {"properties": {"cellPadding": lit(30), "maxTiles": lit(len(kpis))}}]
    o["padding"] = [sel_props({"id": "default"}, paddingUniform=lit(12), paddingIndividual=lit(True), topMargin=lit(10), bottomMargin=lit(10))]
    o["cardCalloutArea"] = [sel_props({"id": "default"}, paddingUniform=lit(10))]
    o["divider"] = [sel_props({"id": "default"}, show=lit(False))]
    o["outline"] = [sel_props({"id": "default"}, show=lit(False))]
    o["shadowCustom"] = [sel_props({"id": "default"}, show=lit(False))]
    o["fillCustom"] = [{"properties": {"show": lit(False)}}]
    o["shapeCustomRectangle"] = [sel_props({"id": "default"}, rectangleRoundedCurve=lit(0))]
    o = {k: v for k, v in o.items() if v}
    visual(page, name, "cardVisual", M, KPI_Y, CW, KPI_H, 3000, query={"Data": [proj(Mf(k["measure"])) for k in kpis]},
           objects=o, vco={**titled(), "visualHeader": props(show=lit(False))})

def axis(units=0):
    return {"valueAxis": props(show=lit(True), labelDisplayUnits=num(units), gridlineShow=lit(True), gridlineStyle=lit("dotted")),
            "categoryAxis": props(show=lit(True)),
            "legend": props(show=lit(True), position=lit("TopRight"))}

def table_fmt(totals=True):
    return {"columnHeaders": props(fontColor=col(WHITE), backColor=col(NAVY), fontFamily=lit(FONT_B), fontSize=num(11), wordWrap=lit(True),
                                   columnAdjustment=lit("growToFit")),
            "rowHeaders": props(fontColor=col(INK), fontSize=num(11), fontFamily=lit(FONT_B)),
            "values": props(fontColor=col(INK), fontSize=num(11), backColorSecondary=col("#F7F9FB")),
            "grid": props(gridHorizontal=lit(True), gridHorizontalColor=col(LINE), gridVertical=lit(False), rowPadding=num(6)),
            "total": props(totals=lit(totals), fontColor=col(INK), fontFamily=lit(FONT_B), backColor=col("#EEF2F6"))}

TI = ("Time Intelligence", "Calculation")
def money_kpi(label, base, accent):
    return dict(measure=f"{base} FYTD", label=label, py=f"{base} PY FYTD", detail=f"{base} vs PY",
                detail_color=f"{base} vs PY Color", detail_bg=f"{base} vs PY Background", units=1000000, precision=1, accent=accent)
def budget_kpi(label, actual, budget, pill, accent, units=1000000, precision=1):
    """Year to date against budget: the value, the budget as reference and a green/red pill."""
    return dict(measure=actual, label=label, py=budget, ref_title="Budget", detail=pill, detail_color=f"{pill} Color",
                detail_bg=f"{pill} Background", units=units, precision=precision, accent=accent)
def py_kpi(label, measure, py, pill, accent, units=1000000, precision=1):
    return dict(measure=measure, label=label, py=py, ref_title="PY", detail=pill, detail_color=f"{pill} Color",
                detail_bg=f"{pill} Background", units=units, precision=precision, accent=accent)
def pct_kpi(label, base, accent):
    return dict(measure=f"{base} FYTD", label=label, py=f"{base} PY FYTD", detail=f"{base} vs PY",
                detail_color=f"{base} vs PY Color", detail_bg=f"{base} vs PY Background", units=1, precision=1, accent=accent)

REV = budget_kpi("Revenue", "Revenue FYTD", "Revenue Budget FYTD", "Revenue vs Budget", BLUE)
EXP = budget_kpi("Expenses", "Expenses FYTD", "Expense Budget FYTD", "Expenses vs Budget", BLUE)
NET = budget_kpi("Change in net assets", "Net Surplus FYTD", "Net Surplus Budget FYTD", "Net Surplus vs Budget", GOLD)
MARGIN = budget_kpi("Surplus margin", "Surplus Margin FYTD", "Surplus Margin Budget FYTD", "Surplus Margin vs Budget", GOLD, units=1)
CONTRIB = budget_kpi("Contributed revenue", "Contributed Revenue FYTD", "Contributed Revenue Budget FYTD", "Contributed Revenue vs Budget", NAVY)
EARNED = budget_kpi("Earned revenue", "Earned Revenue FYTD", "Earned Revenue Budget FYTD", "Earned Revenue vs Budget", NAVY)
CASH = py_kpi("Cash balance", "Cash Balance", "Cash Balance PY", "Cash Balance vs PY", NAVY)
DAYS = py_kpi("Days cash on hand", "Days Cash on Hand", "Days Cash on Hand PY", "Days Cash on Hand vs PY", NAVY, units=1, precision=0)

def series_line(measure, color, dashed=False, area=False, width=3):
    sel = {"metadata": f"_Measures.{measure}"}
    return ([sel_props(sel, fill=col(color))],
            [sel_props(sel, strokeWidth=num(width), lineStyle=lit("dashed" if dashed else "solid"), showMarker=lit(False),
                       **({"areaShow": lit(True), "areaTransparency": num(85)} if area else {}))])

def lines_chart(page, name, x, y, w, h, category, measures, title=None, subtitle=None, title_measure=None, units=1000000):
    """A line chart of explicit measures: [(measure, label, color, dashed, area)]."""
    fills, styles = [], [{"properties": {"lineChartType": lit("smooth")}}]
    for m, _, c, dashed, area in measures:
        f, st = series_line(m, c, dashed, area, 2 if dashed else 3)
        fills += f; styles += st
    visual(page, name, "lineChart", x, y, w, h, 2000,
           query={"Category": [proj(category, "Month")], "Y": [proj(Mf(m), lbl) for m, lbl, *_ in measures]},
           sort=[{"field": category, "direction": "Ascending"}],
           objects={**axis(units), "dataPoint": fills, "lineStyles": styles},
           vco=titled(title, subtitle, title_measure=title_measure, subtitle_measure="Period Label" if not subtitle else None, divider=True))

def bars(page, name, x, y, w, h, category, cat_label, measures, title, subtitle, units=1000000, horizontal=True, stacked=False, sort_by=None):
    """Clustered (or stacked) bars of explicit measures: [(measure, label, color)]."""
    vtype = ("stackedBarChart" if stacked else "clusteredBarChart") if horizontal else ("columnChart" if stacked else "clusteredColumnChart")
    visual(page, name, vtype, x, y, w, h, 2000,
           query={"Category": [proj(category, cat_label)], "Y": [proj(Mf(m), lbl) for m, lbl, _ in measures]},
           sort=[{"field": Mf(sort_by), "direction": "Descending"}] if sort_by else [{"field": category, "direction": "Ascending"}],
           objects={**axis(units), "dataPoint": [sel_props({"metadata": f"_Measures.{m}"}, fill=col(c)) for m, _, c in measures],
                    "labels": props(show=lit(False))},
           vco=titled(title, subtitle, divider=True))

MONTH = Cf("dim_date", "month_name")
BUDGET_C, LY_C = GOLD, PY_GREY

# ================================================================= Overview
p = "pg_overview"
new_page(p, "Overview"); nav(p)
header(p, "Finance Performance Pulse", narrative_measure="Finance Narrative")
kpi_strip(p, "ov_kpis", [REV, EXP, NET, MARGIN, CASH, DAYS])
detail_button(p, "ov_rev_details", 0, 6, "pg_revenue")
detail_button(p, "ov_exp_details", 1, 6, "pg_expense")
lines_chart(p, "ov_trend", M, R2_Y, LEFT_W, R2_H, MONTH,
            [("Trend Actual", "Actual", BLUE, False, True), ("Trend Budget", "Budget", BUDGET_C, True, False),
             ("Trend Last Year", "Last year", LY_C, True, False)], title_measure="Trend Title")
pages[p]["visuals"][-1]["visual"]["visualContainerObjects"]["subTitle"] = props(
    show=lit(True), text=lit("Actual against the adopted budget and last year, by month of the fiscal year"))
visual(p, "ov_metric", "advancedSlicerVisual", M + LEFT_W - 400, R2_Y + 12, 380, 34, 2500,
       query={"Values": [proj(Cf("Trend Metric", "Trend Metric"), "Metric")]},
       objects={"layout": props(orientation=num(2), maxTiles=lit(3)),
                "selection": props(strictSingleSelect=lit(True)),
                "fillCustom": [sel_props({"id": "selection:selected"}, fillColor=col(BLUE))],
                "value": [sel_props({"id": "selection:selected"}, fontColor=col(WHITE)), sel_props({"id": "interaction:rest"}, fontColor=col(SLATE))],
                "general": [{"properties": {"filter": {"filter": {"Version": 2, "From": [{"Name": "m", "Entity": "Trend Metric", "Type": 0}],
                    "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "m"}}, "Property": "Trend Metric"}}],
                                                      "Values": [[{"Literal": {"Value": "'Revenue'"}}]]}}}]}}}}]},
       vco=bare())
bars(p, "ov_dept", RIGHT_X, R2_Y, RIGHT_W, R2_H, Cf("dim_department", "department_name"), "Department",
     [("Expenses FYTD", "Actual", NAVY), ("Expense Budget FYTD", "Budget", "#C9D3E0")],
     "Spending against budget", "Expenses by department, year to date", sort_by="Expenses FYTD")
lines_chart(p, "ov_cash", M, R3_Y, LEFT_W, R3_H, MONTH,
            [("Cash Balance", "This year", NAVY, False, True), ("Cash Balance Last Year", "Last year", LY_C, True, False)],
            title="Cash balance at month end", subtitle="Operating cash this fiscal year against the same month last year")
visual(p, "ov_fund", "clusteredBarChart", RIGHT_X, R3_Y, RIGHT_W, R3_H, 2000,
       query={"Category": [proj(Cf("dim_fund", "fund_name"), "Fund")], "Y": [proj(Mf("Revenue FYTD"), "Revenue")]},
       sort=[{"field": Mf("Revenue FYTD"), "direction": "Descending"}],
       objects={"dataPoint": props(fill=col(NAVY)),
                "labels": props(show=lit(True), labelDisplayUnits=num(1000000), labelPrecision=lit(1)),
                "valueAxis": props(show=lit(False), gridlineShow=lit(False)),
                "categoryAxis": props(show=lit(True)), "legend": props(show=lit(False))},
       vco=titled("Revenue by fund", "How much of this year's revenue comes with donor restrictions?", divider=True))

# ================================================================= Statement of Activities
p = "pg_statement"
new_page(p, "Statement of Activities"); nav(p)
header(p, "Statement of Activities",
       narrative="Revenue and expenses for the year to date against the adopted budget and the same period last year. "
                 "Variances are favourable when positive: revenue above budget, or expenses below it.")
kpi_strip(p, "st_kpis", [REV, EXP, NET, MARGIN, CONTRIB, EARNED])
detail_button(p, "st_rev_details", 0, 6, "pg_revenue")
detail_button(p, "st_exp_details", 1, 6, "pg_expense")
SL = "Statement Line"
st_cols = [("Actual", "Actual"), ("Budget", "Budget"), ("vs Budget", "vs Budget"), ("vs Budget %", "vs Budget %"),
           ("Last Year", "Last year"), ("vs Last Year", "vs Last Year"), ("vs Last Year %", "vs Last Year %")]
def every_column(prop, measure):
    out = [sel_props({"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": f"_Measures.{m}"}, **{prop: mcol(measure)})
           for m, _ in st_cols]
    out.append(sel_props({"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": f"{SL}.Line"}, **{prop: mcol(measure)}))
    return out
font = every_column("fontColor", "SoA Row Font")
for m, f in (("vs Budget", "SoA vs Budget Font"), ("vs Budget %", "SoA vs Budget Font"),
             ("vs Last Year", "SoA vs PY Font"), ("vs Last Year %", "SoA vs PY Font")):
    font = [x for x in font if x["selector"].get("metadata") != f"_Measures.{m}"]
    font.append(sel_props({"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": f"_Measures.{m}"}, fontColor=mcol(f)))
visual(p, "st_table", "tableEx", M, R2_Y, CW, H - G - R2_Y, 2000,
       query={"Values": [proj(Cf(SL, "Line"), " ")] + [proj(Mf(m), lbl) for m, lbl in st_cols]},
       sort=[{"field": Cf(SL, "Line"), "direction": "Ascending"}],
       objects={"columnHeaders": props(fontColor=col(WHITE), backColor=col(NAVY), fontFamily=lit(FONT_B), fontSize=num(12),
                                       columnAdjustment=lit("growToFit")),
                "values": [{"properties": {"fontSize": num(12), "fontFamily": lit(FONT)}}] + every_column("backColor", "SoA Row Background") + font,
                "grid": props(gridHorizontal=lit(True), gridHorizontalColor=col(LINE), gridVertical=lit(False), rowPadding=num(7)),
                "total": props(totals=lit(False))},
       vco=titled(title_measure="Statement Title",
                  subtitle="Fiscal year to date  |  favourable variances in green, unfavourable in red  |  last line: change in net assets as a share of revenue",
                  divider=True))

# ================================================================= Cash Flow
p = "pg_cash"
new_page(p, "Cash Flow"); nav(p)
header(p, "Cash Flow",
       narrative="Where the cash came from and where it went. Ticketing, subscriptions, gifts and hall rentals arrive as cash; "
                 "staff are paid every other Friday and artists and suppliers 30 days after month end.")
kpi_strip(p, "cf_kpis", [
    CASH, DAYS,
    py_kpi("Cash received", "Cash Received FYTD", "Cash Received PY FYTD", "Cash Received vs PY", BLUE),
    py_kpi("Cash paid", "Cash Paid FYTD", "Cash Paid PY FYTD", "Cash Paid vs PY", BLUE),
    py_kpi("Net cash flow", "Net Cash Flow FYTD", "Net Cash Flow PY FYTD", "Net Cash Flow vs PY", GOLD),
    py_kpi("Owed to suppliers and staff", "Owed to Suppliers and Staff", "Owed to Suppliers and Staff PY", "Owed vs PY", GOLD)])
lines_chart(p, "cf_balance", M, R2_Y, LEFT_W, R2_H, MONTH,
            [("Cash Balance", "This year", NAVY, False, True), ("Cash Balance Last Year", "Last year", LY_C, True, False)],
            title="Cash balance at month end", subtitle="Operating cash this fiscal year against the same month last year")
bars(p, "cf_inout", RIGHT_X, R2_Y, RIGHT_W, R2_H, MONTH, "Month",
     [("Cash Received", "Received", BLUE), ("Cash Paid", "Paid", "#C9D3E0")],
     "Cash in and out", "By month of the fiscal year", horizontal=False)
CFL = ("dim_source_module", "cash_flow_line")
visual(p, "cf_statement", "pivotTable", M, R3_Y, LEFT_W, R3_H, 2000,
       query={"Rows": [proj(Cf(*CFL), "Cash flow line")],
              "Values": [proj(Mf("Cash Flow Amount FYTD"), "This year to date"), proj(Mf("Cash Flow Amount PY FYTD"), "Same period last year")]},
       filters=[in_filter("cf_statement_lines", "dim_source_module", "cash_direction", ["In", "Out"])],
       sort=[{"field": Cf(*CFL), "direction": "Ascending"}],
       objects={**table_fmt(), "subTotals": props(rowSubtotals=lit(True)),
                "rowHeaders": props(fontColor=col(INK), fontSize=num(12), fontFamily=lit(FONT_B))},
       vco=titled("Cash flow statement", "Receipts and payments, year to date  |  total = net cash flow", divider=True))
bars(p, "cf_owed", RIGHT_X, R3_Y, RIGHT_W, R3_H, MONTH, "Month",
     [("Accounts Payable", "Suppliers and artists", NAVY), ("Accrued Payroll", "Staff (earned, not yet paid)", GOLD)],
     "Owed at month end", "Bills and pay not yet paid", horizontal=False, stacked=True)

# ================================================================= Reconciliation
p = "pg_recon"
new_page(p, "Reconciliation"); nav(p)
header(p, "Revenue Reconciliation",
       narrative="Each night Tessitura (tickets, subscriptions, gifts) and Diese (hall rentals) are matched to the MIP ledger by month, "
                 "revenue stream and fund. A line ties out when the gap is within the larger of $1,000 or 1%; anything else stays below until finance records the cause.")
kpi_strip(p, "rc_kpis", [
    dict(measure="Source Amount", label="Source revenue", caption="Tessitura + Diese", units=1000000, precision=1, accent=BLUE),
    dict(measure="Ledger Amount", label="Ledger revenue", caption="MIP general ledger", units=1000000, precision=1, accent=BLUE),
    dict(measure="Variance", label="Net variance", caption="Ledger minus source", units=1000, precision=1, accent=GOLD),
    dict(measure="Reconciled %", label="Reconciled", caption="Lines within tolerance", units=1, precision=1, accent=GOOD, value_color=GOOD),
    dict(measure="Lines to Investigate", label="To investigate", caption="Lines outside tolerance", units=1, precision=0, accent=BAD, value_color=BAD),
    dict(measure="Open Items", label="Still open", caption="No cause recorded yet", units=1, precision=0, accent=BAD, value_color=BAD)])
RC2_H = 260; RC3_Y = R2_Y + RC2_H + G; RC3_H = H - G - RC3_Y   # streams heatmap is short, the lines table gets the room
visual(p, "rc_grid", "pivotTable", M, R2_Y, LEFT_W, RC2_H, 2000,
       query={"Rows": [proj(Cf("recon_revenue_to_gl", "revenue_stream"), "Stream")],
              "Columns": [proj(Cf("dim_date", "month_name"), "Month")],
              "Values": [proj(Mf("Variance"))]},
       objects={**table_fmt(),
                "values": [{"properties": {"fontColor": col(INK), "fontSize": num(11)}},
                           sel_props({"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": "_Measures.Variance"},
                                     backColor=mcol("Recon Status Color"))]},
       vco=titled("Variance heatmap", "Which months and streams don't tie out? Red = outside tolerance", divider=True))
visual(p, "rc_trend", "clusteredColumnChart", RIGHT_X, R2_Y, RIGHT_W, RC2_H, 2000,
       query={"Category": [proj(Cf("dim_date", "month_name"), "Month")], "Y": [proj(Mf("Variance"))],
              "Series": [proj(Cf("recon_revenue_to_gl", "revenue_stream"), "Stream")]},
       sort=[{"field": Cf("dim_date", "month_name"), "direction": "Ascending"}],
       objects={**axis(1000), "labels": props(show=lit(False))},
       vco=titled("Where the gaps are", "Ledger minus source by month  |  a cut-off shows as mirrored bars", divider=True))
visual(p, "rc_lines", "tableEx", M, RC3_Y, CW, RC3_H, 2000,
       query={"Values": [proj(Cf("recon_revenue_to_gl", "month_start"), "Month"), proj(Cf("recon_revenue_to_gl", "revenue_stream"), "Stream"),
                         proj(Cf("recon_revenue_to_gl", "fund_code"), "Fund"), proj(Mf("Source Amount"), "Source"),
                         proj(Mf("Ledger Amount"), "Ledger"), proj(Mf("Variance")), proj(Cf("recon_revenue_to_gl", "cause"), "Cause"),
                         proj(Cf("recon_revenue_to_gl", "resolution"), "Status")]},
       sort=[{"field": Mf("Abs Variance"), "direction": "Descending"}],
       filters=[in_filter("rc_lines_status", "recon_revenue_to_gl", "status", ["Investigate"])],
       objects=table_fmt(),
       vco=titled("Lines to investigate", "Biggest gaps first  |  finance records the cause in fin.recon_note and it shows here the next morning", divider=True))

# ================================================================= Revenue Detail (hidden)
p = "pg_revenue"
new_page(p, "Revenue Detail"); nav(p)
header(p, "Revenue Detail", back=True,
       narrative="Every revenue line against the adopted budget and last year. Earned revenue is what the hall sells "
                 "(tickets, subscriptions, rentals); contributed revenue is what donors give.")
kpi_strip(p, "rv_kpis", [REV, EARNED, CONTRIB,
                         dict(pct_kpi("Earned revenue share", "Earned Revenue %", NAVY))])
lines_chart(p, "rv_trend", M, R2_Y, LEFT_W, R2_H, MONTH,
            [("Revenue Actual to Date", "Actual", BLUE, False, True), ("Revenue Budget", "Budget", BUDGET_C, True, False),
             ("Revenue Last Year", "Last year", LY_C, True, False)],
            title="Revenue by month", subtitle="Actual against the adopted budget and last year")
bars(p, "rv_fund", RIGHT_X, R2_Y, RIGHT_W, R2_H, Cf("dim_fund", "fund_name"), "Fund",
     [("Revenue FYTD", "Actual", NAVY), ("Revenue Budget FYTD", "Budget", "#C9D3E0")],
     "Revenue by fund", "Year to date against budget", sort_by="Revenue FYTD")
visual(p, "rv_matrix", "pivotTable", M, R3_Y, CW, R3_H, 2000,
       query={"Rows": [proj(Cf("dim_account", "account_group"), "Group"), proj(Cf("dim_account", "account_name"), "Revenue line")],
              "Values": [proj(Mf("Revenue FYTD"), "Actual"), proj(Mf("Revenue Budget FYTD"), "Budget"),
                         proj(Mf("Revenue vs Budget FYTD"), "vs Budget"), proj(Mf("Revenue vs Budget FYTD %"), "vs Budget %"),
                         proj(Mf("Revenue PY FYTD"), "Last year")]},
       filters=[in_filter("rv_matrix_type", "dim_account", "account_type", ["Revenue"])],
       objects={**table_fmt(), "rowHeaders": props(fontColor=col(INK), fontSize=num(11), fontFamily=lit(FONT_B), stepped=lit(True)),
                "values": [{"properties": {"fontColor": col(INK), "fontSize": num(11)}},
                           sel_props({"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": "_Measures.Revenue vs Budget FYTD"},
                                     fontColor=mcol("Revenue vs Budget Color"))]},
       vco=titled("Revenue lines", "Year to date  |  expand a group to see its lines", divider=True))

# ================================================================= Expense Detail (hidden)
p = "pg_expense"
new_page(p, "Expense Detail"); nav(p)
header(p, "Expense Detail", back=True,
       narrative="Spending by department and expense line against the adopted budget and last year. "
                 "Under budget shows as a positive (favourable) variance.")
kpi_strip(p, "ex_kpis", [
    EXP,
    dict(measure="Expense Budget Full Year", label="Full-year budget", caption="Adopted for the whole fiscal year", accent=GOLD,
         units=1000000, precision=1),
    dict(measure="Expense Budget Used %", label="Budget used", caption="Share of the year's budget spent so far", accent=GOLD,
         units=1, precision=1),
    py_kpi("Owed to suppliers and staff", "Owed to Suppliers and Staff", "Owed to Suppliers and Staff PY", "Owed vs PY", NAVY)])
lines_chart(p, "ex_trend", M, R2_Y, LEFT_W, R2_H, MONTH,
            [("Expenses Actual to Date", "Actual", BLUE, False, True), ("Expense Budget", "Budget", BUDGET_C, True, False),
             ("Expenses Last Year", "Last year", LY_C, True, False)],
            title="Expenses by month", subtitle="Actual against the adopted budget and last year")
bars(p, "ex_dept", RIGHT_X, R2_Y, RIGHT_W, R2_H, Cf("dim_department", "department_name"), "Department",
     [("Expenses FYTD", "Actual", NAVY), ("Expense Budget FYTD", "Budget", "#C9D3E0")],
     "Spending by department", "Year to date against budget", sort_by="Expenses FYTD")
visual(p, "ex_matrix", "pivotTable", M, R3_Y, CW, R3_H, 2000,
       query={"Rows": [proj(Cf("dim_department", "department_name"), "Department"), proj(Cf("dim_account", "account_name"), "Expense line")],
              "Values": [proj(Mf("Expenses FYTD"), "Actual"), proj(Mf("Expense Budget FYTD"), "Budget"),
                         proj(Mf("Expenses vs Budget FYTD"), "vs Budget"), proj(Mf("Expenses vs Budget FYTD %"), "vs Budget %"),
                         proj(Mf("Expenses PY FYTD"), "Last year")]},
       filters=[in_filter("ex_matrix_type", "dim_account", "account_type", ["Expense"])],
       objects={**table_fmt(), "rowHeaders": props(fontColor=col(INK), fontSize=num(11), fontFamily=lit(FONT_B), stepped=lit(True)),
                "values": [{"properties": {"fontColor": col(INK), "fontSize": num(11)}},
                           sel_props({"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": "_Measures.Expenses vs Budget FYTD"},
                                     fontColor=mcol("Expenses vs Budget Color"))]},
       vco=titled("Spending by department and line", "Year to date  |  expand a department to see its lines", divider=True))

# ================================================================= About the Data (hidden)
p = "pg_trust"
new_page(p, "About the Data"); nav(p)
header(p, "About the Data", slicer=False, back=True, period_text="Live status, not filtered by fiscal year",
       narrative="Can I rely on these numbers? When each source was last loaded, whether the ledger balances and how much of the "
                 "revenue reconciliation is still open. It is the same evidence the platform checks every night.")
kpi_strip(p, "tr_kpis", [
    dict(measure="Sources Fresh", label="Sources on time", caption="Loaded within their expected refresh", accent=GOOD, value_color=GOOD),
    dict(measure="As Of Date", label="Ledger data through", caption="Last date with activity in MIP", accent=BLUE),
    dict(measure="Out of Balance", label="Out of balance", caption="Debits minus credits, must be $0.00", units=1, precision=2, accent=GOOD),
    dict(measure="Reconciled %", label="Reconciled", caption="Revenue lines within tolerance", units=1, precision=1, accent=GOLD)])
TR2_H = 300; TR3_Y = R2_Y + TR2_H + G; TR3_H = H - G - TR3_Y
visual(p, "tr_fresh", "tableEx", M, R2_Y, CW, TR2_H, 2000,
       query={"Values": [proj(Cf("source_freshness", "source_name"), "Source"), proj(Cf("source_freshness", "expected_refresh"), "Expected"),
                         proj(Cf("source_freshness", "last_loaded_et"), "Last loaded (ET)"), proj(Mf("Data Through"), "Data through"),
                         proj(Mf("Hours Since Load"), "Hours since load"), proj(Mf("Freshness Status"), "Status")]},
       objects={**table_fmt(totals=False),
                "values": [{"properties": {"fontColor": col(INK), "fontSize": num(12)}},
                           sel_props({"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": "_Measures.Freshness Status"},
                                     fontColor=mcol("Freshness Color"))]},
       vco=titled("Source freshness", "Daily sources go Stale after 26 hours, weekly ones after 8 days", divider=True))
textbox(p, "tr_notes", M, TR3_Y, CW, TR3_H, 2000,
        [[("How these checks work", ts(14, INK, True))],
         [("•  Every journal in the ledger balances; out of balance must be $0.00.", ts(12))],
         [("•  Tessitura and Diese revenue are reconciled to the ledger every night; lines outside tolerance stay on the Reconciliation page until finance explains them.", ts(12))],
         [("•  Freshness comes from the platform's run log: a source counts as current when the nightly run checked it, even if nothing changed.", ts(12))],
         [("•  Every number comes from the certified semantic model sm_finance, so Excel, this report and SQL users see the same figures.", ts(12))]],
        vco={"title": props(show=lit(False)), "background": props(show=lit(True), color=col(WHITE), transparency=num(0)),
             "border": props(show=lit(True), color=col(LINE), radius=num(8)),
             "dropShadow": props(show=lit(True), preset=lit("Custom"), position=lit("Outer"), color=col(LINE), transparency=num(92),
                                 shadowBlur=num(4), shadowDistance=num(2), angle=num(90), shadowSpread=num(0)),
             "padding": props(top=num(10), bottom=num(10), left=num(10), right=num(10)), "visualHeader": props(show=lit(False))})

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

rr = os.path.join(R, "StaticResources", "RegisteredResources"); os.makedirs(rr, exist_ok=True)
shutil.copyfile(os.path.join(HERE, "harmonia_finance_theme.json"), os.path.join(rr, "HarmoniaFinance.json"))
rj = json.load(open(os.path.join(d, "report.json")))
rv = rj["themeCollection"]["baseTheme"]["reportVersionAtImport"]
rj["themeCollection"]["customTheme"] = {"name": "HarmoniaFinance.json", "reportVersionAtImport": rv, "type": "RegisteredResources"}
rj["resourcePackages"] = [x for x in rj["resourcePackages"] if x["name"] != "RegisteredResources"] + [
    {"name": "RegisteredResources", "type": "RegisteredResources", "items": [{"name": "HarmoniaFinance.json", "path": "HarmoniaFinance.json", "type": "CustomTheme"}]}]
rj.setdefault("objects", {})["section"] = [{"properties": {"verticalAlignment": lit("Top")}}]
json.dump(rj, open(os.path.join(d, "report.json"), "w"), indent=2)
json.dump({"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
           "version": "4.0", "datasetReference": {"byPath": {"path": "../sm_finance.SemanticModel"}}},
          open(os.path.join(R, "definition.pbir"), "w"), indent=2)

# layout guard: everything inside the page and the 30px side margins (nav chrome excepted)
for pid in order:
    for v in pages[pid]["visuals"]:
        x, y, w, h = (v["position"][k] for k in ("x", "y", "width", "height"))
        assert x + w <= W and y + h <= H, (pid, v["name"])
        chrome = v["name"].endswith(("_navbg", "_strip"))
        assert chrome or (x >= M and x + w <= W - M), (pid, v["name"], x, w)
print("pages:", {pid: len(pages[pid]["visuals"]) for pid in order})

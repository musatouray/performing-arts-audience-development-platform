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
ORDER = [("pg_overview", "Overview"), ("pg_recon", "Reconciliation"), ("pg_trust", "Data Trust")]

def new_page(pid, name):
    pages[pid] = {"page": {"$schema": PAGE, "name": pid, "displayName": name, "displayOption": "FitToPage", "height": H, "width": W,
                           "objects": {"background": props(color=col(PAGE_BG), transparency=num(0)),
                                       "outspace": props(color=col(PAGE_BG), transparency=num(0)),
                                       "displayArea": props(verticalAlignment=lit("Top"))}},
                  "visuals": []}

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

def header(page, title, narrative=None, narrative_measure=None, slicer=True, period_text=None):
    shape(page, f"{page}_hdrbg", M, HDR_Y, CW, HDR_H, 0, WHITE, shadow=True, outline=LINE)
    period = [(period_text, ts(10, SLATE))] if period_text else [(("m", "Period Label"), ts(10, SLATE))]
    textbox(page, f"{page}_title", M + 20, HDR_Y + 12, 360, 60, 1000, [[(title, ts(14, INK, True))], period])
    nx, nw = M + 400, (CW - 400 - 280) if slicer else (CW - 420)
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
            o["referenceLabelTitle"].append(sel_props({**meta(m), "id": f}, titleContentType=lit("custom"), titleText=lit("PY")))
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
def pct_kpi(label, base, accent):
    return dict(measure=f"{base} FYTD", label=label, py=f"{base} PY FYTD", detail=f"{base} vs PY",
                detail_color=f"{base} vs PY Color", detail_bg=f"{base} vs PY Background", units=1, precision=1, accent=accent)

# ================================================================= Page 1: Overview
p = "pg_overview"
new_page(p, "Overview"); nav(p)
header(p, "Finance Performance Pulse", narrative_measure="Finance Narrative")
kpi_strip(p, "ov_kpis", [money_kpi("Revenue", "Revenue", BLUE), money_kpi("Expenses", "Expenses", BLUE),
                         money_kpi("Net Surplus", "Net Surplus", GOLD), pct_kpi("Surplus Margin", "Surplus Margin", GOLD),
                         money_kpi("Contributed Revenue", "Contributed Revenue", NAVY), pct_kpi("Earned Revenue Share", "Earned Revenue %", NAVY)])
visual(p, "ov_trend", "lineChart", M, R2_Y, LEFT_W, R2_H, 2000,
       query={"Category": [proj(Cf("dim_date", "month_name"), "Month")],
              "Y": {"projections": [proj(Mf("Revenue"))],
                    "fieldParameters": [{"parameterExpr": Cf("Trend Metric", "Trend Metric"), "index": 0, "length": 1}]},
              "Series": [proj(Cf(*TI), "Year")]},
       sort=[{"field": Cf("dim_date", "month_name"), "direction": "Ascending"}],
       filters=[in_filter("ov_trend_ti", *TI, ["Current", "PY"])],
       objects={**axis(1000000),
                "dataPoint": [sel_props(series_sel(*TI, "Current"), fill=col(BLUE)), sel_props(series_sel(*TI, "PY"), fill=col(PY_GREY))],
                "lineStyles": [{"properties": {"strokeWidth": num(3), "showMarker": lit(False), "lineChartType": lit("smooth")}},
                               sel_props(series_sel(*TI, "Current"), areaShow=lit(True), areaTransparency=num(85)),
                               sel_props(series_sel(*TI, "PY"), lineStyle=lit("dashed"), strokeWidth=num(2))]},
       vco=titled(title_measure="Trend Title", subtitle_measure="Period Label", divider=True))
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
visual(p, "ov_dept", "clusteredBarChart", RIGHT_X, R2_Y, RIGHT_W, R2_H, 2000,
       query={"Category": [proj(Cf("dim_department", "department_name"), "Department")], "Y": [proj(Mf("Expenses"))],
              "Series": [proj(Cf(*TI), "Period")]},
       sort=[{"field": Mf("Expenses"), "direction": "Descending"}],
       filters=[in_filter("ov_dept_ti", *TI, ["FYTD", "PY FYTD"])],
       objects={**axis(1000000),
                "dataPoint": [sel_props(series_sel(*TI, "FYTD"), fill=col(NAVY)), sel_props(series_sel(*TI, "PY FYTD"), fill=col(PY_GREY))]},
       vco=titled("Where the money goes", "Expenses by department, year to date vs the same period last year", divider=True))
visual(p, "ov_statement", "pivotTable", M, R3_Y, LEFT_W, R3_H, 2000,
       query={"Rows": [proj(Cf("dim_account", "account_type"), "Line"), proj(Cf("dim_account", "account_group"), "Group")],
              "Values": [proj(Mf("Statement FYTD"), "This year to date"), proj(Mf("Statement PY FYTD"), "Same period last year"),
                         proj(Mf("Statement vs PY"), "Change"), proj(Mf("Statement vs PY %"), "Change %")]},
       sort=[{"field": Cf("dim_account", "account_type"), "direction": "Descending"}],
       objects={**table_fmt(), "rowHeaders": props(fontColor=col(INK), fontSize=num(11), fontFamily=lit(FONT_B), stepped=lit(True))},
       vco=titled("Income statement", "Revenue and expenses, year to date vs the same period last year  |  total row = net surplus", divider=True))
visual(p, "ov_fund", "clusteredBarChart", RIGHT_X, R3_Y, RIGHT_W, R3_H, 2000,
       query={"Category": [proj(Cf("dim_fund", "fund_name"), "Fund")], "Y": [proj(Mf("Revenue"))]},
       sort=[{"field": Mf("Revenue"), "direction": "Descending"}],
       objects={"dataPoint": props(fill=col(NAVY)),
                "labels": props(show=lit(True), labelDisplayUnits=num(1000000), labelPrecision=lit(1)),
                "valueAxis": props(show=lit(False), gridlineShow=lit(False)),
                "categoryAxis": props(show=lit(True)), "legend": props(show=lit(False))},
       vco=titled("Revenue by fund", "How much of this year's revenue comes with donor restrictions?", divider=True))

# ================================================================= Page 2: Reconciliation
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

# ================================================================= Page 3: Data Trust
p = "pg_trust"
new_page(p, "Data Trust"); nav(p)
header(p, "Data Trust", slicer=False, period_text="Live status, not filtered by fiscal year",
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

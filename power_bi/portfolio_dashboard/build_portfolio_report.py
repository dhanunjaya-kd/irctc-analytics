"""Build a native six-page Power BI report. Standard library only; no data changes."""
import json
import uuid
from portfolio_repairs import repair_visual
from portfolio_design import upgrade_definitions
from portfolio_polish import polish_definitions
from pathlib import Path

BASE = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition'
NAVY, BLUE, TEAL, GREY, BG = '#14263D', '#2563EB', '#00877A', '#526277', '#F3F6FA'
M = lambda name: ('Measure', '_Measures', name)
C = lambda table, name: ('Column', table, name)
YM = C('Dim_Date', 'YearMonth')
CL = C('Dim_Class', 'ClassKey')
TRAIN = C('Dim_Train', 'TrainName')
ROUTE = C('Dim_Route', 'RouteName')

def uid(text):
    return uuid.uuid5(uuid.NAMESPACE_URL, 'irctc-portfolio-v1/' + text).hex[:20]

def lit(value):
    return {'expr': {'Literal': {'Value': value}}}

def string(value):
    return lit("'" + value.replace("'", "''") + "'")

def color(value):
    return {'solid': {'color': string(value)}}

def props(**values):
    return [{'properties': values}]

def field(f):
    kind, table, name = f
    return {kind: {'Expression': {'SourceRef': {'Entity': table}}, 'Property': name}}

def projection(f):
    d = {'field': field(f), 'queryRef': f'{f[1]}.{f[2]}', 'nativeQueryRef': f[2]}
    if f[0] == 'Column':
        d['active'] = True
    return d

def container(title=None, background='#FFFFFF'):
    d = {'background': props(show=lit('true'), color=color(background), transparency=lit('0D')),
         'border': props(show=lit('false'))}
    if title:
        d['title'] = props(show=lit('true'), text=string(title), fontColor=color(NAVY), fontSize=lit('11D'), bold=lit('true'), titleWrap=lit('true'))
    else:
        d['title'] = props(show=lit('false'))
    return d

def visual(key, kind, x, y, w, h, title=None, roles=None, sort=None):
    v = {'visualType': kind, 'drillFilterOtherVisuals': True,
         'visualContainerObjects': container(title)}
    if roles:
        v['query'] = {'queryState': {role: {'projections': [projection(f) for f in fs]} for role, fs in roles.items()}}
        if sort:
            v['query']['sortDefinition'] = {'sort': [{'field': field(sort[0]), 'direction': sort[1]}], 'isDefaultSort': True}
    return {'$schema': BASE+'/visualContainer/2.4.0/schema.json', 'name': uid(key),
            'position': {'x': x, 'y': y, 'width': w, 'height': h, 'z': 0, 'tabOrder': 0}, 'visual': v}

def textbox(key, text, x, y, w, h, size=12, fg=GREY, bg=BG, bold=False):
    d = visual(key, 'textbox', x, y, w, h)
    d['visual']['visualContainerObjects'] = container(background=bg)
    d['visual']['objects'] = {'general': props(paragraphs=[{'textRuns': [{'value': text, 'textStyle': {
        'fontFamily': 'Segoe UI', 'fontSize': str(size)+'pt', 'color': fg,
        'fontWeight': 'bold' if bold else 'normal'}}]}])}
    return d

def card(key, name, title, x, y, w=296, h=100):
    d = visual(key, 'card', x, y, w, h, title, {'Values': [M(name)]})
    d['visual']['objects'] = {
        'labels': props(color=color(BLUE), fontSize=lit('27D'), labelDisplayUnits=lit('1D')),
        'categoryLabels': props(show=lit('false'))}
    return d

def chart(key, kind, title, category, measures, x, y, w, h, descending=False):
    d = visual(key, kind, x, y, w, h, title,
                {'Category': [category], 'Y': [M(m) for m in measures]},
                (M(measures[0]), 'Descending') if descending else (category, 'Ascending'))
    d['visual']['objects'] = {'categoryAxis': props(show=lit('true'), fontSize=lit('9D')),
                            'valueAxis': props(show=lit('true'), fontSize=lit('9D'))}
    return d

def table(key, title, fields, x, y, w, h):
    d = visual(key, 'tableEx', x, y, w, h, title, {'Values': fields})
    d['visual']['objects'] = {'grid': props(textSize=lit('10D'))}
    return d

def slicer(key, f, title, x, w):
    d = visual(key, 'slicer', x, 90, w, 62, title, {'Values': [f]})
    d['visual']['objects'] = {'data': props(mode=string('Dropdown')), 'header': props(show=lit('false'))}
    return d

def page(n, title, subtitle, cards, note, filters=True):
    name = uid('page-'+str(n))
    pg = {'$schema': BASE+'/page/2.0.0/schema.json', 'name': name, 'displayName': f'{n:02d}  {title}',
          'displayOption': 'FitToPage', 'width': 1280, 'height': 800,
          'objects': {'background': props(color=color(BG), transparency=lit('0D'))}}
    vs = [textbox(f'{n}-header', 'IRCTC  /  '+title.upper(), 0, 0, 1280, 54, 23, '#FFFFFF', NAVY, True),
          textbox(f'{n}-subtitle', subtitle, 24, 58, 1232, 28, 10),
          textbox(f'{n}-foot', 'SYNTHETIC DATA  |  768 simulated runs / 19,708 scheduled  |  No forecasts or network-wide claims', 24, 766, 1232, 26, 9)]
    if filters:
        vs += [slicer(f'{n}-month-slicer' if n == 1 else f'{n}-month', YM, 'Journey month', 24, 400),
               slicer(f'{n}-class-slicer' if n == 1 else f'{n}-class', CL, 'Travel class', 440, 400),
               slicer(f'{n}-type', C('Dim_Train', 'TrainType'), 'Train type', 856, 400)]
    else:
        vs.append(textbox(f'{n}-check-note', 'Validation is evaluated against the reference dataset. Expected: 31 KPI checks and 11 row-count checks pass.', 24, 96, 1232, 50, 12, NAVY))
    for i, (name_, label) in enumerate(cards):
        vs.append(card(f'{n}-card-{i}', name_, label, 24+i*312, 166))
    vs.append(textbox(f'{n}-note', note, 24, 714, 1232, 44, 10))
    return pg, vs

def build_pages():
    out=[]
    pg,v=page(1,'Overview','Passenger demand, capacity and booking value | Select month, class and train type to explore.',
        [('Total Bookings','Total bookings'),('Total Passengers','Total passengers'),('Seat Occupancy','Seat occupancy'),('Passenger Cancellation Rate','Passenger cancellation rate')],
        'READ THIS FIRST  •  These are sample totals. Use passengers per simulated run to compare demand; occupancy includes RAC at 0.5 seat per passenger.')
    v += [chart('1-demand','lineChart','Passenger demand per simulated run',YM,['Passengers per Run'],24,282,764,220),
          chart('1-class','clusteredBarChart','Seat occupancy by class',CL,['Seat Occupancy'],804,282,452,220),
          table('1-month','Monthly operating scorecard',[YM,M('Simulated Runs'),M('Passengers per Run'),M('On-Time Performance'),M('Net Booking Value')],24,518,1232,180)]
    out.append((pg,v))
    pg,v=page(2,'Demand & capacity','Compare demand with the seat supply of the same simulated train-class runs.',
        [('Simulated Runs','Simulated runs'),('Seat Supply','Seat supply'),('Bookings per Run','Bookings per simulated run'),('Waitlist Pressure','Waitlist pressure')],
        'CAPACITY NOTE  •  Waitlisted passengers hold no seat. Waitlist pressure is a separate demand signal, not occupancy. These results depend on the simulation design.')
    v += [chart('2-demand','lineChart','Monthly bookings per simulated run',YM,['Bookings per Run'],24,282,608,220),
          chart('2-occupancy','lineChart','Monthly seat occupancy',YM,['Seat Occupancy'],648,282,608,220),
          table('2-classes','Class capacity and demand',[CL,M('Seat Supply'),M('Booked Seats'),M('Total Passengers'),M('Seat Occupancy'),M('Waitlist Pressure')],24,518,1232,180)]
    out.append((pg,v))
    pg,v=page(3,'Booking value','Amounts are simulated booking values and refunds, not revenue or profit.',
        [('Gross Booking Value','Gross booking value · INR million'),('Refunds','Refunds · INR million'),('Net Booking Value','Net booking value · INR million'),('Refund Share of Gross','Refund share of gross value')],
        'REFUND NOTE  •  Refunds include passenger cancellations and synthetic system auto-refunds for uncleared waitlists. Net booking value = gross booking value − refunds.')
    v += [chart('3-values','lineChart','Gross and net booking value · INR million',YM,['Gross Booking Value','Net Booking Value'],24,282,764,220),
          chart('3-refunds','clusteredColumnChart','Refunds by class · INR million',CL,['Refunds'],804,282,452,220),
          table('3-monthly','Monthly value reconciliation · INR million',[YM,M('Gross Booking Value'),M('Refunds - Passenger Cancellations'),M('Refunds - System Auto-Refunds'),M('Net Booking Value')],24,518,1232,180)]
    out.append((pg,v))
    pg,v=page(4,'Train & route performance','Compare per-run demand, occupancy and punctuality across the simulated services.',
        [('Simulated Runs','Simulated runs'),('Passengers per Run','Passengers per simulated run'),('On-Time Performance','On-time performance'),('Average Delay (min)','Average arrival delay · minutes')],
        'OPERATIONS NOTE  •  On time means arrival delay ≤15 minutes (project threshold). Missing delays are excluded. Train-run metrics do not vary with the class filter.')
    v += [chart('4-route','clusteredBarChart','Route demand · passengers per run (scroll for all routes)',ROUTE,['Passengers per Run'],24,282,608,220,True),
          chart('4-train','clusteredBarChart','Train occupancy (scroll for all trains)',TRAIN,['Seat Occupancy'],648,282,608,220,True),
          table('4-performance','Train performance scorecard',[TRAIN,M('Simulated Runs'),M('Passengers per Run'),M('Seat Occupancy'),M('On-Time Performance'),M('Average Delay (min)')],24,518,1232,180)]
    out.append((pg,v))
    pg,v=page(5,'Waitlist & cancellations','Track initial waitlist demand through final passenger status; cancellation rates are passenger-based.',
        [('Initial Waitlist Demand','Initially waitlisted passengers'),('Waitlist Clearance Rate','Waitlist clearance rate'),('Uncleared Waitlist Passengers','Uncleared waitlist passengers'),('Passenger Cancellation Rate','Passenger cancellation rate')],
        'STATUS NOTE  •  Clearance means initially waitlisted passengers finishing Confirmed or RAC. System auto-refunds are distinct from passenger cancellations.')
    v += [chart('5-clearance','lineChart','Monthly waitlist clearance rate',YM,['Waitlist Clearance Rate'],24,282,608,220),
          chart('5-cancellations','clusteredColumnChart','Passenger cancellation rate by class',CL,['Passenger Cancellation Rate'],648,282,608,220),
          table('5-funnel','Waitlist outcomes by class',[CL,M('Initial Waitlist Demand'),M('Waitlist Cleared'),M('Uncleared Waitlist Passengers'),M('Waitlist Clearance Rate')],24,518,1232,180)]
    out.append((pg,v))
    pg,v=page(6,'KPI validation','Native DAX results are compared with the existing reference values after refresh.',
        [('KPIs in Reference','Reference KPIs · expected 31'),('KPIs Reconciled','KPIs passing · expected 31'),('Checks Passed','Reference checks marked passed'),('Simulated Runs','Simulated runs · expected 768')],
        'VALIDATION NOTE  •  PASS is computed by the model, never hardcoded. Investigate FAIL or NOT COMPUTED before publishing. Python test success does not verify DAX results.',False)
    v += [table('6-kpi','KPI checks · native units from the reference',[C('Ref_KPI','KpiKey'),M('KPI Reference Value'),M('KPI Check Value'),M('KPI Difference'),M('KPI Status')],24,282,760,416),
          table('6-rows','Model row-count checks',[C('Ref_RowCounts','ModelTable'),C('Ref_RowCounts','ExpectedRows'),M('Model Row Count'),M('Row Count Status')],800,282,456,416)]
    out.append((pg,v))
    return out

def files():
    report='IRCTC_Portfolio.Report'
    d={}
    def put(rel, value):
        d[rel]=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    put('IRCTC_Portfolio.pbip',{'version':'1.0','artifacts':[{'report':{'path':report}}],'settings':{'enableAutoRecovery':True}})
    put(report+'/definition.pbir',{'$schema':'https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json','version':'4.0','datasetReference':{'byPath':{'path':'../IRCTC_Portfolio.SemanticModel'}}})
    put(report+'/definition/version.json',{'$schema':BASE+'/versionMetadata/1.0.0/schema.json','version':'2.0.0'})
    put(report+'/definition/report.json',{
        '$schema':BASE+'/report/3.1.0/schema.json',
        'themeCollection':{'baseTheme':{'name':'CY24SU10','reportVersionAtImport':{'visual':'1.8.95','report':'2.0.95','page':'1.3.95'},'type':'SharedResources'}},
        'resourcePackages':[{'name':'SharedResources','type':'SharedResources','items':[{'name':'CY24SU10','path':'BaseThemes/CY24SU10.json','type':'BaseTheme'}]}],
        'settings':{'useStylableVisualContainerHeader':True,'exportDataMode':'AllowSummarized','defaultDrillFilterOtherVisuals':True,'useEnhancedTooltips':True}})
    pages=build_pages()
    put(report+'/definition/pages/pages.json',{'$schema':BASE+'/pagesMetadata/1.0.0/schema.json','pageOrder':[p['name'] for p,_ in pages],'activePageName':pages[0][0]['name']})
    for p,vs in pages:
        assert len({v['name'] for v in vs}) == len(vs), 'Duplicate visual IDs'
        base=report+'/definition/pages/'+p['name']
        put(base+'/page.json',p)
        for i,v in enumerate(vs):
            v['position']['z']=i*1000
            v['position']['tabOrder']=i*1000
            v = repair_visual(v)
            put(base+'/visuals/'+v['name']+'/visual.json',v)
    return polish_definitions(upgrade_definitions(d))

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);args=ap.parse_args()
    out=Path(args.out)
    if out.exists():raise SystemExit('Output already exists; choose a new folder to preserve your edits.')
    for rel,b in files().items():
        p=out/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    print('Report definitions created. Attach the semantic model before opening.')

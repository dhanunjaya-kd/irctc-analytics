"""Presentation-only polish for the Desktop-verified v2 report layout."""
import json
from portfolio_design import uid, newuid, REPORT, lit, string, color, setp, title, pos

NAVY='#14263D';TEAL='#00877A';BLUE='#2563EB';RED='#C25067';AMBER='#D78B18'
ALIASES={
 'YearMonth':'Month','ClassKey':'Class','TrainName':'Train','Simulated Runs':'Runs',
 'Passengers per Run':'Passengers/run','On-Time Performance':'On time',
 'Average Delay (min)':'Delay (min)','Seat Supply':'Seat supply','Booked Seats':'Weighted seats',
 'Total Passengers':'Passengers','Seat Occupancy':'Occupancy','Waitlist Pressure':'Waitlist pressure',
 'Gross Booking Value (INR million)':'Gross value','Net Booking Value (INR million)':'Net value',
 'Passenger Refunds (INR million)':'Passenger refunds','System Refunds (INR million)':'System refunds',
 'Initial Waitlist Demand':'Initially waitlisted','Waitlist Cleared':'Cleared',
 'Uncleared Waitlist Passengers':'Still waitlisted','Waitlist Clearance Rate':'Clearance rate',
 'KpiKey':'KPI','KPI Reference Value':'Reference','KPI Check Value':'Calculated',
 'KPI Difference':'Difference','KPI Status':'Status','ModelTable':'Model table',
 'ExpectedRows':'Expected','Model Row Count':'Actual','Row Count Status':'Status',
 'Confirmed Passengers':'Confirmed','RAC Passengers':'RAC','Cancelled Passengers':'Cancelled',
}

def set_text(d,lines,size=11):
    general=d['visual']['objects']['general'][0]['properties']
    general['paragraphs']=[{'textRuns':[{'value':line,'textStyle':{'fontFamily':'Segoe UI','fontSize':str(size)+'pt','color':NAVY}}]} for line in lines]

def width_table(d,widths):
    v=d['visual'];projs=v['query']['queryState']['Values']['projections'];o=v.setdefault('objects',{})
    if len(projs)!=len(widths):raise ValueError('Unexpected table columns: '+d['name'])
    setp(o,'columnHeaders',autoSizeColumnWidth=lit('false'),columnAdjustment=string('fixedWidth'),wordWrap=lit('true'))
    o['columnWidth']=[{'selector':{'metadata':p['queryRef']},'properties':{'value':lit(str(w)+'D')}} for p,w in zip(projs,widths)]

def polish_definitions(source):
    out=dict(source)
    for n in range(1,7):
        prefix=REPORT+uid('page-'+str(n))+'/'
        vs={json.loads(b)['name']:json.loads(b) for p,b in source.items() if p.startswith(prefix+'visuals/') and p.endswith('/visual.json')}
        def get(key,new=False):return vs[(newuid if new else uid)(key)]
        for d in vs.values():
            v=d['visual'];kind=v['visualType'];o=v.setdefault('objects',{});co=v.setdefault('visualContainerObjects',{})
            if kind=='textbox':continue
            setp(co,'title',fontSize=lit('13D'),fontColor=color(NAVY))
            if kind in {'tableEx','pivotTable'}:
                setp(co,'stylePreset',name=string('None'))
                setp(o,'columnHeaders',fontSize=lit('12D'),fontColor=color(NAVY),backColor=color('#E7EEF6'))
                setp(o,'values',fontSize=lit('12D'),fontColorPrimary=color(NAVY),fontColorSecondary=color(NAVY),backColorPrimary=color('#FFFFFF'),backColorSecondary=color('#F3F6FA'),wordWrap=lit('true'))
                setp(o,'grid',rowPadding=lit('1D'),textSize=lit('12D'))
                for role in v['query']['queryState'].values():
                    for p in role['projections']:
                        field=next(iter(p['field'].values()));name=field.get('Property','')
                        if name in ALIASES:p['displayName']=ALIASES[name]
            if kind in {'lineChart','columnChart','hundredPercentStackedBarChart'}:
                for role in v.get('query',{}).get('queryState',{}).values():
                    for p in role.get('projections',[]):
                        field=next(iter(p['field'].values()));name=field.get('Property','')
                        if name in ALIASES:p['displayName']=ALIASES[name]
            if kind in {'clusteredBarChart','clusteredColumnChart'}:
                setp(o,'labels',show=lit('true'),fontSize=lit('11D'),color=color(NAVY))
            # Keep all 24 month observations and the existing chronological grouping.
            if kind=='lineChart':
                setp(o,'categoryAxis',fontSize=lit('10D'))
            if kind=='scatterChart':
                setp(o,'bubbles',bubbleSize=lit('-10D'))
                # Auto limits preserve visibility when slicers alter the range.
                for axis in ('categoryAxis','valueAxis'):
                    for item in o.get(axis,[]):
                        item.get('properties',{}).pop('start',None)
                        item.get('properties',{}).pop('end',None)
        pos(get(f'{n}-subtitle'),24,68,1392,36)
        pos(get(f'{n}-note'),24,816,1392,42)
        pos(get(f'{n}-foot'),24,862,1392,34)
        set_text(get(f'{n}-foot'),['SYNTHETIC DATA | 768 simulated runs sampled from 19,708 scheduled runs | No actual IRCTC results or forecasts'],10)
        if n<6:
            for i,key in enumerate([f'{n}-month-slicer' if n==1 else f'{n}-month',f'{n}-class-slicer' if n==1 else f'{n}-class',f'{n}-type']):
                pos(get(key),24+i*472,110,448,56)
            for i in range(4):pos(get(f'{n}-card-{i}'),24+i*352,182,336,88)
            for d in vs.values():
                if d['position']['y']==268: d['position'].update(y=286,height=260)
        if n==1:
            set_text(get('1-subtitle'),['Explore sample demand, seat use and final passenger outcomes. Filter by month, class or train type.'])
            title(get('1-demand'),'Passenger demand trend | passengers per simulated run')
            title(get('1-class'),'Seat occupancy by travel class')
            title(get('1-month'),'Monthly scorecard | net booking value in INR million')
            width_table(get('1-month'),[140,120,180,180,230])
            bar=get('1-class')['visual']['objects'];setp(bar,'dataPoint',defaultColor=color(TEAL));
            for entry in bar.get('dataPoint',[]):entry.setdefault('properties',{})['fill']=color(TEAL)
            setp(bar,'labels',labelPrecision=lit('1D'),labelDisplayUnits=lit('1D'))
            status=get('status-summary',True);title(status,'Final passenger status | passenger count')
            setp(status['visual']['objects'],'valueAxis',labelDisplayUnits=lit('1000D'),labelPrecision=lit('0D'))
            setp(status['visual']['objects'],'labels',labelDisplayUnits=lit('1000D'),labelPrecision=lit('1D'))
            set_text(get('1-note'),['Sample totals only. Compare demand per simulated run; occupancy counts each RAC passenger as 0.5 seat.'])
        elif n==2:
            set_text(get('2-subtitle'),['Compare passenger records with seat supply; use weighted occupancy to measure seat use.'])
            title(get('2-occupancy'),'Seat supply vs passenger records | includes cancellations and waitlists')
            setp(get('2-occupancy')['visual']['objects'],'labels',show=lit('false'))
            width_table(get('2-classes'),[55,120,125,120,115,123])
            set_text(get('2-note'),['Weighted seats = confirmed + 0.5 × RAC passengers. Waitlisted passengers hold no seat; pressure is a separate metric.'])
        elif n==3:
            set_text(get('3-subtitle'),['Simulated booking values and refunds in INR million. Net booking value = gross value − refunds.'])
            width_table(get('3-monthly'),[160,300,300,300,300])
            title(get('3-refunds'),'Refund sources by class | INR million')
            set_text(get('3-note'),['Passenger refunds and system auto-refunds are separate components. Booking value is not revenue or profit.'])
        elif n==4:
            set_text(get('4-subtitle'),['Compare sample demand, seat use and punctuality. Hover to inspect simulated-run counts before ranking services.'])
            width_table(get('4-performance'),[290,70,125,110,120,135])
            title(get('4-performance'),'Train scorecard | arrival delay in minutes')
            for key in ('4-route','4-train'):
                setp(get(key)['visual']['objects'],'labels',labelDisplayUnits=lit('1D'),labelPrecision=lit('1D'))
            title(get('train-scatter',True),'Train comparison | occupancy vs cancellations')
            set_text(get('4-note'),['On time: arrival delay ≤15 min; missing delays excluded. Run metrics ignore class. Scatter: bubble size = passengers.'])
        elif n==5:
            set_text(get('5-subtitle'),['Track initially waitlisted passengers and compare final passenger outcomes across travel classes.'])
            width_table(get('5-funnel'),[75,215,135,230,195])
            setp(get('5-cancellations')['visual']['objects'],'dataPoint',defaultColor=color(RED))
            for entry in get('5-cancellations')['visual']['objects'].get('dataPoint',[]):entry.setdefault('properties',{})['fill']=color(RED)
            setp(get('5-cancellations')['visual']['objects'],'labels',labelDisplayUnits=lit('1D'),labelPrecision=lit('1D'))
            set_text(get('5-note'),['Cleared = initially waitlisted passengers finishing Confirmed/RAC. Remaining initial waitlist cases may include cancellations.'])
        else:
            set_text(get('6-subtitle'),['Model calculations compared with imported reference values. Inspect every KPI and table status before publishing.'])
            for i in range(4):pos(get(f'6-card-{i}'),24+i*352,112,336,88)
            pos(get('6-kpi'),24,216,804,596);pos(get('6-rows'),844,216,572,366)
            width_table(get('6-kpi'),[250,160,160,110,90]);width_table(get('6-rows'),[205,105,110,120])
            title(get('6-kpi'),'KPI reconciliation | native reference units')
            title(get('6-rows'),'Model row counts | expected vs actual')
            note=get('6-check-note');pos(note,844,598,572,214)
            set_text(note,['HOW TO READ THESE CHECKS','Reference = imported expected value.','Calculated = model result; Difference = calculated − reference.','Rates use decimal ratios (example: 0.75 = 75%).','Booking-value checks use raw INR, not INR million.','Imported check counts are separate from live KPI comparisons.'],12)
            set_text(get('6-note'),['PASS is computed by the model. Investigate FAIL, NOT COMPUTED or blank results before publication.'])
        for ident,d in vs.items():out[prefix+'visuals/'+ident+'/visual.json']=(json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    return out

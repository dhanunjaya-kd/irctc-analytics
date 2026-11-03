"""IRCTC portfolio visual upgrade. Existing DAX/data remain untouched."""
import copy, json, uuid

NAVY,BLUE,TEAL,AMBER,RED,BG='#14263D','#2563EB','#00877A','#D78B18','#C25067','#F3F6FA'
REPORT='IRCTC_Portfolio.Report/definition/pages/'

def uid(key):return uuid.uuid5(uuid.NAMESPACE_URL,'irctc-portfolio-v1/'+key).hex[:20]
def newuid(key):return uuid.uuid5(uuid.NAMESPACE_URL,'irctc-portfolio-design-v2/'+key).hex[:20]
def lit(v):return {'expr':{'Literal':{'Value':v}}}
def string(v):return lit("'"+v.replace("'","''")+"'")
def color(v):return {'solid':{'color':string(v)}}
def props(**v):return [{'properties':v}]
def field(kind,table,name):return {kind:{'Expression':{'SourceRef':{'Entity':table}},'Property':name}}
def M(name):return field('Measure','_Measures',name)
def C(table,name):return field('Column',table,name)
def projection(f):
 v=next(iter(f.values()));name=v['Property'];table=v['Expression']['SourceRef']['Entity']
 return {'field':f,'queryRef':table+'.'+name,'nativeQueryRef':name}
def qs(**roles):return {'queryState':{r:{'projections':[projection(f) for f in fs]} for r,fs in roles.items()}}
def setp(objs,key,**v):
 arr=objs.setdefault(key,[])
 for item in arr:
  if not item.get('selector'):item.setdefault('properties',{}).update(v);return
 arr.insert(0,{'properties':v})
def title(d,text):setp(d['visual'].setdefault('visualContainerObjects',{}),'title',show=lit('true'),text=string(text))
def pos(d,x,y,w,h):d['position'].update(x=x,y=y,width=w,height=h)
def measures(v):
 return [p['field']['Measure']['Property'] for r in v.get('query',{}).get('queryState',{}).values() for p in r.get('projections',[]) if 'Measure' in p.get('field',{})]
def palette(name):
 if 'System' in name or 'Waitlist' in name:return AMBER
 if 'Cancelled' in name or 'Cancellation Rate' in name:return RED
 if 'Occupancy' in name or 'Net Booking' in name or 'Confirmed Passengers' in name:return TEAL
 return BLUE

def series_colors(d):
 v=d['visual'];o=v.setdefault('objects',{});entries=[]
 for p in v.get('query',{}).get('queryState',{}).get('Y',{}).get('projections',[]):
  n=p['field'].get('Measure',{}).get('Property','')
  entries.append({'selector':{'metadata':p['queryRef']},'properties':{'fill':color(palette(n))}})
 if entries:o['dataPoint']=entries

def restyle(d):
 v=d['visual'];kind=v['visualType'];o=v.setdefault('objects',{});vco=v.setdefault('visualContainerObjects',{})
 if kind=='textbox':return
 setp(vco,'title',fontSize=lit('13D'),fontColor=color(NAVY),bold=lit('true'))
 setp(vco,'border',show=lit('true'),color=color('#DFE7F0'),radius=lit('6D'))
 if kind=='card':
  names=measures(v);shade=palette(names[0]) if names else BLUE
  setp(o,'labels',fontSize=lit('30D'),color=color(shade))
 elif kind=='slicer':
  setp(o,'items',textSize=lit('12D'))
  for entry in o.get('general',[]):entry.get('properties',{}).pop('filter',None)
  # A portfolio opens on the full synthetic sample; retain empty filter definitions.
  for filt in d.get('filterConfig',{}).get('filters',[]):filt.pop('filter',None)
 elif kind in {'tableEx','pivotTable'}:
  for role in v['query']['queryState'].values():
   for p in role['projections']:p.pop('active',None)
  setp(o,'grid',textSize=lit('11D'),rowPadding=lit('3D'))
  setp(o,'columnHeaders',fontSize=lit('11D'),wordWrap=lit('true'),autoSizeColumnWidth=lit('true'),columnAdjustment=string('growToFit'))
  setp(o,'values',fontSize=lit('11D'))
 elif kind in {'lineChart','clusteredBarChart','clusteredColumnChart','columnChart','hundredPercentStackedBarChart','scatterChart'}:
  setp(o,'categoryAxis',fontSize=lit('11D'),showAxisTitle=lit('false'))
  setp(o,'valueAxis',fontSize=lit('11D'),showAxisTitle=lit('false'),gridlineColor=color('#E7EDF4'),start=lit('0D'))
  setp(o,'legend',fontSize=lit('10D'),showTitle=lit('false'))
  if kind=='lineChart':
   setp(o,'lineStyles',strokeWidth=lit('3D'))
   # Keep all 24 points; reduce categorical label density only.
   setp(o,'categoryAxis',labelDensity=lit('35D'))
  series_colors(d)

def base_visual(key,kind,schema,title_text,roles,x,y,w,h):
 d={'$schema':schema,'name':newuid(key),'position':{'x':x,'y':y,'z':90000,'tabOrder':90000,'width':w,'height':h},'visual':{'visualType':kind,'query':qs(**roles),'drillFilterOtherVisuals':True,'visualContainerObjects':{'background':props(show=lit('true'),color=color('#FFFFFF'),transparency=lit('0D'))},'objects':{}}}
 title(d,title_text);restyle(d);return d

def set_sort(d,f,descending=False):d['visual']['query']['sortDefinition']={'sort':[{'field':f,'direction':'Descending' if descending else 'Ascending'}],'isDefaultSort':True}
def tooltips(d,names):d['visual']['query']['queryState']['Tooltips']={'projections':[projection(M(n)) for n in names]}

def gradient(name,low='#EEF8F6',high='#4EB8AA'):
 ref='_Measures.'+name
 rule = {'Input': {'SelectRef': {'ExpressionName': ref}}, 'FillRule': {'linearGradient2': {
  'min': {'color': {'Literal': {'Value': "'"+low+"'"}}, 'value': {'Literal': {'Value': '0D'}}},
  'max': {'color': {'Literal': {'Value': "'"+high+"'"}}, 'value': {'Literal': {'Value': '1D'}}},
  'nullColoringStrategy': {'strategy': {'Literal': {'Value': "'noColor'"}}}
 }}}
 return {'selector': {'data': [{'dataViewWildcard': {'matchingOption': 1}}], 'metadata': ref},
         'properties': {'backColor': {'solid': {'color': {'expr': {'FillRule': rule}}}}}}

def rank_filter(d,name):
 f={'name':newuid('rank-filter-'+name),'field':M(name),'type':'Advanced','howCreated':'User','filter':{'Version':2,'From':[{'Name':'m','Entity':'_Measures','Type':0}],'Where':[{'Condition':{'Comparison':{'ComparisonKind':4,'Left':{'Measure':{'Expression':{'SourceRef':{'Source':'m'}},'Property':name}},'Right':{'Literal':{'Value':'8L'}}}}}]}}
 filters=d.setdefault('filterConfig',{}).setdefault('filters',[])
 filters[:]=[x for x in filters if x.get('name')!=f['name']];filters.append(f)

def upgrade_definitions(source):
 """Transforms report JSON bytes in memory; only known visuals are changed."""
 out=dict(source);pages=[]
 for n in range(1,7):
  prefix=REPORT+uid('page-'+str(n))+'/'
  pg=json.loads(out[prefix+'page.json']);pg['width']=1440;pg['height']=900
  visuals={}
  for path,b in out.items():
   if path.startswith(prefix+'visuals/') and path.endswith('/visual.json'):
    d=json.loads(b);visuals[d['name']]=d
  def get(key):
   ident=uid(key)
   if ident not in visuals:raise ValueError('Required repaired visual missing: '+key)
   return visuals[ident]
  def add(d):visuals[d['name']]=d
  schema=get(str(n)+'-card-0')['$schema']
  for d in visuals.values():restyle(d)
  header=get(f'{n}-header');pos(header,0,0,1440,62)
  for p in header['visual']['objects']['general'][0]['properties']['paragraphs']:
   for run in p['textRuns']:run['textStyle']['fontSize']='25pt'
  sub=get(f'{n}-subtitle');pos(sub,24,68,1392,26)
  footer=get(f'{n}-foot');pos(footer,24,866,1392,24)
  note=get(f'{n}-note');pos(note,24,824,1392,36)
  for d,size in [(sub,'11pt'),(footer,'10pt'),(note,'11pt')]:
   for p in d['visual']['objects']['general'][0]['properties']['paragraphs']:
    for run in p['textRuns']:run['textStyle']['fontSize']=size
  for i in range(4):pos(get(f'{n}-card-{i}'),24+i*352,164,336,88)
  if n<6:
   keys=[f'{n}-month-slicer' if n==1 else f'{n}-month',f'{n}-class-slicer' if n==1 else f'{n}-class',f'{n}-type']
   for i,key in enumerate(keys):pos(get(key),24+i*472,98,448,54)
  else:pos(get('6-check-note'),24,102,1392,46)
  if n==1:
   pos(get('1-demand'),24,268,880,278);title(get('1-demand'),'How does passenger demand change? | passengers per simulated run')
   pos(get('1-class'),920,268,496,278);title(get('1-class'),'Which classes use more capacity? | occupancy %')
   pos(get('1-month'),24,562,880,250)
   status=base_visual('status-summary','clusteredBarChart',schema,'Where do passengers finish? | final status',{'Category':[C('Dim_PassengerStatus','Status')],'Y':[M('Total Passengers')]},920,562,496,250)
   set_sort(status,M('Total Passengers'),True);add(status)
   tooltips(get('1-class'),['Seat Supply','Booked Seats','Total Passengers'])
  elif n==2:
   pos(get('2-demand'),24,268,688,278)
   capacity=get('2-occupancy');pos(capacity,728,268,688,278)
   capacity['visual']['visualType']='clusteredColumnChart';capacity['visual']['query']=qs(Category=[C('Dim_Class','ClassKey')],Y=[M('Seat Supply'),M('Total Passengers')])
   capacity['visual']['objects']={};restyle(capacity);title(capacity,'Capacity vs requested demand | seats and passengers')
   capacity['visual']['objects']['dataPoint'][1]['properties']['fill']=color(AMBER)
   pos(get('2-classes'),24,562,688,250)
   heat=base_visual('occupancy-heatmap','pivotTable',schema,'Occupancy heatmap | season × class, darker = higher',{'Rows':[C('Dim_Date','Season')],'Columns':[C('Dim_Class','ClassKey')],'Values':[M('Seat Occupancy')]},728,562,688,250)
   o=heat['visual']['objects'];setp(o,'rowHeaders',fontSize=lit('11D'));o['values'].append(gradient('Seat Occupancy'))
   setp(heat['visual']['visualContainerObjects'],'stylePreset',name=string('None'));add(heat)
  elif n==3:
   pos(get('3-values'),24,268,880,278);title(get('3-values'),'Gross booking value vs net after refunds | INR million')
   refunds=get('3-refunds');pos(refunds,920,268,496,278)
   refunds['visual']['visualType']='columnChart';refunds['visual']['query']=qs(Category=[C('Dim_Class','ClassKey')],Y=[M('Passenger Refunds (INR million)'),M('System Refunds (INR million)')]);refunds['visual']['objects']={}
   restyle(refunds);title(refunds,'What drives refunds? | INR million')
   setp(refunds['visual']['objects'],'valueAxis',labelDisplayUnits=lit('1D'),labelPrecision=lit('1D'))
   pos(get('3-monthly'),24,562,1392,250)
  elif n==4:
   route=get('4-route');train=get('4-train');pos(route,24,268,688,278);pos(train,728,268,688,278)
   title(route,'Leading routes | passengers/run, ranks 1–8 incl. ties');rank_filter(route,'Route Demand Rank')
   title(train,'Leading trains | occupancy %, ranks 1–8 incl. ties');rank_filter(train,'Train Occupancy Rank')
   for d in [route,train]:
    setp(d['visual']['objects'],'categoryAxis',maxMarginFactor=lit('45D'))
    tooltips(d,['Simulated Runs','Total Passengers','Passengers per Run','Seat Occupancy','Passenger Cancellation Rate','On-Time Performance'])
   pos(get('4-performance'),24,562,880,250)
   scatter=base_visual('train-scatter','scatterChart',schema,'Occupancy vs cancellations | bubble = passengers',{'Category':[C('Dim_Train','TrainName')],'X':[M('Seat Occupancy')],'Y':[M('Passenger Cancellation Rate')],'Size':[M('Total Passengers')]},920,562,496,250)
   tooltips(scatter,['Simulated Runs','On-Time Performance'])
   setp(scatter['visual']['objects'],'categoryAxis',showAxisTitle=lit('true'),titleText=string('Occupancy %'),start=lit('0D'))
   setp(scatter['visual']['objects'],'valueAxis',showAxisTitle=lit('true'),titleText=string('Cancellation %'))
   setp(scatter['visual']['objects'],'legend',show=lit('false'));setp(scatter['visual']['objects'],'categoryLabels',show=lit('false'));add(scatter)
  elif n==5:
   pos(get('5-clearance'),24,268,688,278)
   pos(get('5-cancellations'),920,562,496,250)
   pos(get('5-funnel'),24,562,880,250)
   mix=base_visual('status-mix','hundredPercentStackedBarChart',schema,'Passenger outcomes by class | share of final statuses',{'Category':[C('Dim_Class','ClassKey')],'Y':[M('Confirmed Passengers'),M('RAC Passengers'),M('Uncleared Waitlist Passengers'),M('Cancelled Passengers')]},728,268,688,278)
   tooltips(mix,['Total Passengers']);add(mix)
  else:
   pos(get('6-kpi'),24,268,804,544);pos(get('6-rows'),844,268,572,544)
   title(get('6-kpi'),'31 KPI checks | reference, calculated value, difference, status')
   title(get('6-rows'),'11 model tables | expected vs actual rows')
  # Color key table cells by their actual ratio, never by summed percentages.
  for d in visuals.values():
   if d['visual']['visualType']=='tableEx' and 'Seat Occupancy' in measures(d['visual']):
    values=d['visual'].setdefault('objects',{}).setdefault('values',[])
    values[:]=[x for x in values if x.get('selector',{}).get('metadata')!='_Measures.Seat Occupancy']
    values.append(gradient('Seat Occupancy'))
  for i,(ident,d) in enumerate(visuals.items()):
   d['position']['z']=i*1000;d['position']['tabOrder']=i*1000
   out[prefix+'visuals/'+ident+'/visual.json']=(json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
  out[prefix+'page.json']=(json.dumps(pg,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
 return out

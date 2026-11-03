"""Targeted IRCTC portfolio corrections. No CSV edits or base DAX changes."""
import copy
import json
import re
import uuid

NAVY, BLUE, TEAL, BG = '#14263D', '#2563EB', '#00877A', '#F3F6FA'
FINANCIAL = {
    'Gross Booking Value': 'Gross Booking Value (INR million)',
    'Refunds': 'Refunds (INR million)',
    'Refunds - Passenger Cancellations': 'Passenger Refunds (INR million)',
    'Refunds - System Auto-Refunds': 'System Refunds (INR million)',
    'Net Booking Value': 'Net Booking Value (INR million)',
}

def lit(value):
    return {'expr': {'Literal': {'Value': value}}}

def string(value):
    return lit("'" + value.replace("'", "''") + "'")

def color(value):
    return {'solid': {'color': string(value)}}

def set_props(objects, object_name, **kwargs):
    # Preserve any existing selector-specific overrides.
    entries = objects.setdefault(object_name, [])
    for entry in entries:
        if not entry.get('selector'):
            entry.setdefault('properties', {}).update(kwargs)
            return
    entries.insert(0, {'properties': kwargs})

def projections(v):
    for role in v.get('query', {}).get('queryState', {}).values():
        yield from role.get('projections', [])

def replace_money(node):
    if isinstance(node, dict):
        measure = node.get('Measure')
        if isinstance(measure, dict) and measure.get('Expression', {}).get('SourceRef', {}).get('Entity') == '_Measures':
            name = measure.get('Property')
            if name in FINANCIAL:
                measure['Property'] = FINANCIAL[name]
        for key, value in list(node.items()):
            if isinstance(value, str):
                if key in ('queryRef', 'metadata') and value.startswith('_Measures.') and value[10:] in FINANCIAL:
                    node[key] = '_Measures.' + FINANCIAL[value[10:]]
                elif key == 'nativeQueryRef' and value in FINANCIAL:
                    node[key] = FINANCIAL[value]
            else:
                replace_money(value)
    elif isinstance(node, list):
        for item in node:
            replace_money(item)

def repair_visual(source):
    d = copy.deepcopy(source)
    v = d.get('visual', {})
    kind = v.get('visualType')
    if kind == 'textbox':
        return d
    original_measures = [p.get('field', {}).get('Measure', {}).get('Property') for p in projections(v)]
    financial = any(name in FINANCIAL or name in FINANCIAL.values() for name in original_measures)
    # Only rewrite financial display bindings. Validation measures still use raw INR.
    if financial:
        replace_money(d)
    objects = v.setdefault('objects', {})
    vco = v.setdefault('visualContainerObjects', {})
    if 'title' in vco:
        set_props(vco, 'title', fontSize=lit('12D'))
    if kind == 'tableEx':
        # active is a category-drill property, not a table column visibility flag.
        for p in projections(v):
            p.pop('active', None)
        set_props(objects, 'grid', textSize=lit('11D'), rowPadding=lit('4D'))
        set_props(objects, 'columnHeaders', autoSizeColumnWidth=lit('true'),
                  columnAdjustment=string('growToFit'), fontSize=lit('11D'),
                  fontColor=color(NAVY), backColor=color('#E7EEF7'), wordWrap=lit('true'))
        set_props(objects, 'values', fontSize=lit('11D'),
                  fontColorPrimary=color(NAVY), fontColorSecondary=color(NAVY),
                  backColorPrimary=color('#FFFFFF'), backColorSecondary=color(BG))
        set_props(vco, 'stylePreset', name=string('None'))
        # A grand total of unrelated KPI rows or row-count reference rows is meaningless.
        fields = list(projections(v))
        if any(p.get('field', {}).get('Column', {}).get('Expression', {}).get('SourceRef', {}).get('Entity') in {'Ref_KPI', 'Ref_RowCounts'} for p in fields):
            set_props(objects, 'total', totals=lit('false'))
    elif kind == 'card' and financial:
        set_props(objects, 'labels', labelDisplayUnits=lit('1D'), labelPrecision=lit('2D'))
    elif kind in {'lineChart', 'clusteredBarChart', 'clusteredColumnChart'}:
        set_props(objects, 'categoryAxis', fontSize=lit('10D'))
        set_props(objects, 'valueAxis', fontSize=lit('10D'))
        if financial:
            set_props(objects, 'valueAxis', labelDisplayUnits=lit('1D'), labelPrecision=lit('1D'))
            if 'labels' in objects:
                set_props(objects, 'labels', labelDisplayUnits=lit('1D'))
        # Consistent chart colors; occupancy/net use teal, volume/gross use blue.
        series = v.get('query', {}).get('queryState', {}).get('Y', {}).get('projections', [])
        for p in series:
            name = p.get('field', {}).get('Measure', {}).get('Property', '')
            shade = TEAL if name in {'Seat Occupancy', 'Waitlist Clearance Rate', FINANCIAL['Net Booking Value']} else BLUE
            entries = objects.setdefault('dataPoint', [])
            selector = {'metadata': p['queryRef']}
            match = next((x for x in entries if x.get('selector') == selector), None)
            if match is None:
                match = {'selector': selector, 'properties': {}}
                entries.append(match)
            match['properties']['fill'] = color(shade)
    return d

def repair_model(text):
    # Keep every original measure expression, relationship and import unchanged.
    text = text.replace('formatString: #,0.00,,', 'formatString: #,0.00')
    text = text.replace('Gross booking value in INR (displayed in millions):', 'Gross booking value in raw INR:')
    text = text.replace('Refund amount in INR (millions):', 'Refund amount in raw INR:')
    text = text.replace('Gross booking value minus refunds, INR millions.', 'Gross booking value minus refunds, raw INR.')
    blocks = []
    for raw, display in FINANCIAL.items():
        if "measure '" + display + "' =" in text:
            continue
        tag = str(uuid.uuid5(uuid.NAMESPACE_URL, 'irctc-portfolio-display-v1/' + display))
        blocks.append(f"\t/// Presentation only: raw INR divided once by 1,000,000. Base KPI reconciliation uses raw INR.\n\tmeasure '{display}' = DIVIDE([{raw}], 1000000)\n\t\tformatString: #,0.00\n\t\tdisplayFolder: 11 Portfolio display (INR million)\n\t\tlineageTag: {tag}\n\n")
    if blocks:
        marker = '\tcolumn Placeholder'
        if text.count(marker) != 1:
            raise ValueError('Expected one _Measures placeholder; stopped without changes.')
        text = text.replace(marker, ''.join(blocks) + marker)
    return text

import json
from pathlib import Path
from openpyxl import load_workbook
root=Path(__file__).resolve().parents[1]
d=json.loads((root/'data/snapshot.json').read_text())
for k,p in d['periods'].items():
    assert len(p['records'])==5 and p['start']<=p['end']
    values=[r['gross_rub'] for r in p['records']]
    assert values==sorted(values,reverse=True) and all(v>0 for v in values)
    for r in p['records']:assert any(f['title']==r['title'] for f in d['ratings']['records'])
for f in d['ratings']['records']:
    for s in f['scores'].values():
        if s['value'] is not None:assert s['checked_date'] and 0<=s['value']<=s['scale']
w=load_workbook(root/'site/kinopulse.xlsx',read_only=True,data_only=True)
assert len(w.sheetnames)==4
assert w['Сборы'].max_row==11
assert w['Сборы']['F2'].value==d['periods']['weekend']['records'][0]['gross_rub']
assert isinstance(w['Сборы']['F2'].value,int)
assert (root/'site/data.js').read_text().startswith('window.CINEMA_DATA=')
print('Validated 2 periods, 10 box-office rows, rating provenance and numeric Excel cells')

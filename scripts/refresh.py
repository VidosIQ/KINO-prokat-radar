"""Collect published Fond Kino periods. Never advance a period after failed validation."""
import argparse, copy, hashlib, html, io, json, math, re, signal
from datetime import datetime, date
from pathlib import Path
from urllib.parse import urlencode, urljoin, quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from ratings import refresh_ratings, Tree, clean
import pdfplumber
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

ROOT = Path(__file__).resolve().parents[1]
INDEX = 'https://www.fond-kino.ru/pages/otraslevaa-analitika/'
EAIS = 'https://ekinobilet.fond-kino.ru/ekb/top-films/'
NOW = datetime.now(ZoneInfo('Europe/Moscow')).isoformat(timespec='seconds')
TODAY = NOW[:10]
AUDIT = []

def fetch(url, form=None):
    print('Fetching '+url,flush=True)
    req=Request(url, data=urlencode(form).encode() if form else None,
        headers={'User-Agent':'Kinopulse/1.0 (public cinema statistics)', 'X-Requested-With':'XMLHttpRequest'})
    def deadline(signum,frame):raise TimeoutError('Source request exceeded 75 seconds: '+url)
    signal.signal(signal.SIGALRM,deadline);signal.alarm(75)
    try:
        with urlopen(req, timeout=30) as r: body=r.read()
    finally:signal.alarm(0)
    print('Received '+str(len(body))+' bytes',flush=True)
    digest=hashlib.sha256(body).hexdigest()
    AUDIT.append(dict(url=url,form=form,checked_at=NOW,sha256=digest,bytes=len(body)))
    p=ROOT/'data/evidence'/digest
    p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(body)
    return body

def reports_from_html(body):
    out={}
    for href,text in re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',body):
        text=html.unescape(re.sub('<[^>]+>',' ',text))
        m=re.search(r'(уикенд|неделя)\s+(\d+)\s*\((\d{2})\.(\d{2})\s*[-–]\s*(\d{2})\.(\d{2})\.(\d{4})\)',text,re.I)
        if not m or '/documents/download/' not in href: continue
        kind='weekend' if m[1].lower()=='уикенд' else 'week'
        end=date(int(m[7]),int(m[6]),int(m[5]));year=end.year-(int(m[4])>end.month)
        start=date(year,int(m[4]),int(m[3]))
        if end.isoformat()>=TODAY: continue
        if start>end: raise ValueError('Reversed report dates')
        item=dict(kind=kind,issue=int(m[2]),start=start.isoformat(),end=end.isoformat(),source_url=urljoin(INDEX,href))
        if kind not in out or out[kind]['end']<item['end']: out[kind]=item
    if set(out)!={'week','weekend'}: raise ValueError('Both published periods required')
    return out

def eais_records(report):
    raw=json.loads(fetch(EAIS,dict(periodStart=report['start'].replace('-','.'),periodEnd=report['end'].replace('-','.'))))
    if not isinstance(raw,list) or len(raw)<20: raise ValueError('Unexpected EAIS response')
    sums=[r['sum'] for r in raw]
    if any(not isinstance(v,(int,float)) or v<0 for v in sums) or sums!=sorted(sums,reverse=True):
        raise ValueError('EAIS must return descending gross ranking')
    records=[dict(rank=i+1,title=r['title'],certificate=str(r['id']),gross_rub=math.floor(r['sum']),viewers=int(r['quantity'])) for i,r in enumerate(raw)]
    if len({r['certificate'] for r in records})!=len(records): raise ValueError('Duplicate certificates')
    return records

def pdf_records(body, report, online):
    by_cert={r['certificate']:r['title'] for r in online}
    with pdfplumber.open(io.BytesIO(body)) as pdf:
        header=pdf.pages[0].extract_text()
        expected_start=datetime.strptime(report['start'],'%Y-%m-%d').strftime('%d.%m')
        expected_end=datetime.strptime(report['end'],'%Y-%m-%d').strftime('%d.%m.%Y')
        if not re.search(re.escape(expected_start)+r'\s*[–-]\s*'+re.escape(expected_end),header):raise ValueError('PDF dates do not match published link')
        page=pdf.pages[1];table=page.find_tables()[0]; values=table.extract()
        first=next(i for i,r in enumerate(values) if r[0]=='1')
        cells=[c for c in table.rows[first].cells if c is not None]
        if len(cells)!=17: raise ValueError('PDF layout changed')
        words=page.extract_words()
        ranks=[w for w in words if w['x1']<cells[0][2]+.2 and w['text'].isdigit() and table.bbox[1]<w['top']<table.bbox[3]]
        if [int(w['text']) for w in ranks]!=list(range(1,13)): raise ValueError('PDF rank layout changed')
        rows=[]
        for i,w in enumerate(ranks):
            center=(w['top']+w['bottom'])/2
            def value(col):
                x0,_,x1,_=cells[col]
                return ' '.join(v['text'] for v in sorted(words,key=lambda v:v['x0']) if x0<=(v['x0']+v['x1'])/2<x1 and abs((v['top']+v['bottom'])/2-center)<1)
            def number(col): return int(re.sub(r'\s+','',value(col)))
            # Certificate field may occupy several lines. Bound it by neighbouring rank centres.
            low=(center+(ranks[i-1]['top']+ranks[i-1]['bottom'])/2)/2 if i else center-12
            high=(center+(ranks[i+1]['top']+ranks[i+1]['bottom'])/2)/2 if i+1<len(ranks) else center+12
            x0,_,x1,_=cells[2]
            certs=[v['text'] for v in words if x0<=(v['x0']+v['x1'])/2<x1 and low<=(v['top']+v['bottom'])/2<high and re.fullmatch(r'\d{9}',v['text'])]
            title=next((by_cert[c] for c in certs if c in by_cert),None)
            if not title: title=value(1) or 'Название не сопоставлено'
            rows.append(dict(title=title,certificates=certs,gross_rub=number(10),viewers=number(8),total_gross_rub=number(15),total_viewers=number(14),source_url=report['source_url'],source_rank=i+1))
        summary=next(x for x in page.extract_text().splitlines() if 'ИТОГО ТОП-12:' in x)
        parts=re.split(r'[+-]?[\d,]+%',summary.split('ИТОГО ТОП-12:')[1])
        expected=int(re.sub(r'\s+','',parts[1]));difference=sum(r['gross_rub'] for r in rows)-expected
        if abs(difference)>12: raise ValueError('PDF numeric checksum failed')
        return dict(**report,records=rows,detail_minus_published_total_rub=difference)

def export_excel(data):
    wb=Workbook();wb.remove(wb.active)
    intro=wb.create_sheet('Описание')
    for row in [
        ['Кинопульс — Кинопрокат России',''],
        ['Сайт','https://vidosiq.github.io/KINO-prokat-radar/'],
        ['Сборы','Топ-5 строк ЕАИС по кассе за уикенд и неделю; сборы в рублях и число зрителей.'],
        ['Рейтинги','Оценки зрителей, критиков и редакции хранятся отдельно, со шкалой, датой и ссылкой.'],
        ['Фонд кино PDF','Показатели выборки отчёта и общая касса фильма на конец периода.'],
        ['Сравнение источников','Одинаковые фильмы и даты: разница = Kinometro − ЕАИС; процент — от ЕАИС.'],
        ['Периоды','Берём даты опубликованных отчётов Фонда кино; уикенд и неделя могут обновляться независимо.'],
        ['Ограничения','Разные ПУ не объединяем. Отсутствие оценки не считаем нулём. Кинопоиск и IMDb пока — датированные снимки.'],
        ['Свежесть','Даты проверки указаны на листах. Историческое сравнение может быть старше текущего уикенда.'],
        ['Последние сборы',data['checked_date']],
        ['Уикенд',data['periods']['weekend']['start']+' — '+data['periods']['weekend']['end']],
        ['Неделя',data['periods']['week']['start']+' — '+data['periods']['week']['end']],
        ['Основной источник',INDEX],
    ]:intro.append(row)
    intro.column_dimensions['A'].width=28;intro.column_dimensions['B'].width=100
    intro.freeze_panes='B2';intro.sheet_view.showGridLines=False
    for row in intro:
        for c in row:c.alignment=Alignment(wrap_text=True,vertical='center')
        intro.row_dimensions[row[0].row].height=42
        row[0].font=Font(bold=True,color='5630BF')
    for c in intro[1]:c.font=Font(bold=True,color='FFFFFF',size=13);c.fill=PatternFill('solid',fgColor='6236B6')
    for address in ('B2','B13'):intro[address].hyperlink=intro[address].value;intro[address].style='Hyperlink'

    tables={
      'Сборы':(['Период','Начало','Конец','Место','Фильм','Сборы, руб.','Зрители','Проверено','Источник'],[
        [k,p['start'],p['end'],r['rank'],r['title'],r['gross_rub'],r['viewers'],p.get('checked_date',data['checked_date']),EAIS] for k,p in data['periods'].items() for r in p['records']]),
      'Рейтинги':(['Фильм','Источник','Оценка','Шкала','Голоса','Статус','Дата значения','Ссылка'],[
        [r['title'],data['ratings']['sources'][k]['label'],s['value'],s['scale'],s.get('count_label') or s.get('count'),s['status'],s.get('checked_date'),s['url']] for r in data['ratings']['records'] for k,s in r['scores'].items()]),
      'Фонд кино PDF':(['Период','Конец','Фильм','Сборы, руб.','Зрители','Всего, руб.','Источник'],[
        [p['kind'],p.get('end',p.get('period')),r['title'],r['gross_rub'],r['viewers'],r['total_gross_rub'],r['source_url']] for p in data['pdf_reports'] for r in p['records']]),
      'Сравнение источников':(['Начало','Конец','Фильм','ЕАИС, руб.','Kinometro, руб.','Разница, руб.','Разница, %','ЕАИС','Kinometro'],[
        [data['comparison_eais']['start'],data['comparison_eais']['end'],r['title'],r['gross_rub'],k['gross_rub'],k['gross_rub']-r['gross_rub'],(k['gross_rub']/r['gross_rub']-1)*100,EAIS,k['source_url']]
        for r in data['comparison_eais']['records'] for k in data['kinometro']['records'] if k['title'].casefold().replace('ё','е').startswith(r['title'].casefold().replace('ё','е'))])}
    for name,(headers,rows) in tables.items():
        ws=wb.create_sheet(name);ws.append(headers)
        for row in rows: ws.append(row)
        ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
        for c in ws[1]:c.font=Font(color='FFFFFF',bold=True);c.fill=PatternFill('solid',fgColor='6236B6')
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width=min(75,max(16,max(len(str(c.value or '')) for c in col)+2))
        for row in ws.iter_rows(min_row=2):
            for c in row:
                if c.row%2==0:c.fill=PatternFill('solid',fgColor='F3EEFA')
                if isinstance(c.value,(int,float)):c.number_format='#,##0.0' if isinstance(c.value,float) else '#,##0'
        title_col=headers.index('Фильм')+1 if 'Фильм' in headers else None
        if title_col:
            for row in ws.iter_rows(min_row=2):row[title_col-1].font=Font(bold=True)
        if name=='Сравнение источников':
            for row in ws.iter_rows(min_row=2):row[6].number_format='0.0000'
    wb.save(ROOT/'site/kinopulse.xlsx')

def refresh_kinometro(data):
    url='https://www.kinometro.ru/box/show/region/ruonly/'
    try:
        body=fetch(url).decode();tree=Tree(body).root
        header=next(n for n in tree.walk() if n.has('boxofise-topdate-red')).text()
        m=re.search(r'(\d{2}\.\d{2}\.\d{2})\s*-\s*(\d{2}\.\d{2}\.\d{2})',header)
        if not m:raise ValueError('Kinometro period not found')
        start=datetime.strptime(m[1],'%d.%m.%y').date().isoformat();end=datetime.strptime(m[2],'%d.%m.%y').date().isoformat()
        records=[]
        for n in tree.walk():
            if n.tag!='tr':continue
            cells=[clean(c.text()) for c in n.children if hasattr(c,'tag') and c.tag in ('td','th')]
            if len(cells)==15 and cells[0].isdigit() and 1<=int(cells[0])<=20:
                records.append(dict(rank=int(cells[0]),title=cells[2],gross_rub=int(re.sub(r'\s+','',cells[6].split('$')[0])),viewers=int(re.sub(r'\s+','',cells[10])),source_url=url))
        if len(records)!=20:raise ValueError('Kinometro table layout changed')
        # Preserve the matched historical pair unless this period matches EAIS.
        if start==data['periods']['weekend']['start'] and end==data['periods']['weekend']['end']:
            data['comparison_eais']=copy.deepcopy(data['periods']['weekend'])
            data['kinometro']=dict(start=start,end=end,period=start+' — '+end,records=records,checked_date=TODAY,territory='Russia')
        data['kinometro']['latest_available_period']=start+' — '+end
        data['kinometro']['last_attempt']=TODAY
    except Exception as error:data['kinometro']['refresh_error']=str(error)[:180]

def run(force=False):
    current=json.loads((ROOT/'data/snapshot.json').read_text());candidate=copy.deepcopy(current)
    reports=reports_from_html(fetch(INDEX).decode())
    changed=False
    for kind,report in reports.items():
        prior=current['periods'][kind]
        if not force and prior.get('report_url')==report['source_url']:continue
        records=eais_records(report);pdf=pdf_records(fetch(report['source_url']),report,records)
        candidate['periods'][kind]=dict(**report,report_url=report['source_url'],checked_date=TODAY,records=records[:5],coverage_count=len(records),requests=copy.deepcopy(AUDIT[-2:]))
        candidate['pdf_reports']=[p for p in candidate['pdf_reports'] if p['kind']!=kind]+[pdf]
        changed=True
    if changed:
        candidate['checked_date']=TODAY
        # A new film gets explicit missing ratings and a Kinopoisk search link until its identity is confirmed.
        known={r['title'] for r in candidate['ratings']['records']}
        for p in candidate['periods'].values():
            for r in p['records']:
                if r['title'] in known:continue
                link='https://www.kinopoisk.ru/index.php?kp_query='+quote(r['title'])
                candidate['ratings']['records'].append(dict(title=r['title'],kinopoisk_url=link,scores={k:dict(value=None,scale=s['scale'],url=link if k=='kinopoisk' else {'imdb':'https://www.imdb.com/','kritikanstvo':'https://kritikanstvo.ru/','megacritic':'https://megacritic.ru/'}.get(k,'https://www.film.ru/'),status='not_confirmed',count=None,checked_date=None) for k,s in candidate['ratings']['sources'].items()}));known.add(r['title'])
        (ROOT/'data/snapshot.json').write_text(json.dumps(candidate,ensure_ascii=False,indent=2)+'\n')
    refresh_ratings(candidate,fetch,TODAY)
    refresh_kinometro(candidate)
    (ROOT/'data/snapshot.json').write_text(json.dumps(candidate,ensure_ascii=False,indent=2)+'\n')
    export_excel(candidate)
    (ROOT/'site/data.js').write_text('window.CINEMA_DATA='+json.dumps(candidate,ensure_ascii=False).replace('<','\\u003c')+';\n')
    (ROOT/'data/last-check.json').write_text(json.dumps(dict(checked_at=NOW,new_report=changed,reports=reports,requests=AUDIT),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(changed=changed,periods={k:p['end'] for k,p in candidate['periods'].items()})))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--force',action='store_true');args=ap.parse_args();run(args.force)

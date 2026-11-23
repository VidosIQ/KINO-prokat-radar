(()=>{'use strict';
const data=window.CINEMA_DATA;
let period='weekend', metric='gross', precise=false, ratingGroup='audience';
const $=id=>document.getElementById(id);
const fmt=(n,d=0)=>new Intl.NumberFormat('ru-RU',{minimumFractionDigits:d,maximumFractionDigits:d}).format(n);
const million=n=>n==null?'нет данных':fmt(n/1e6,2);
const dates=p=>new Date(p.start+'T12:00:00').toLocaleDateString('ru-RU',{day:'numeric',month:'short'})+' — '+new Date(p.end+'T12:00:00').toLocaleDateString('ru-RU',{day:'numeric',month:'short',year:'numeric'});
const checked=p=>p.checked_date||data.checked_date;
const ratingFilm=title=>data.ratings.records.find(r=>r.title===title);
const kp=title=>ratingFilm(title)?.kinopoisk_url||'https://www.kinopoisk.ru/index.php?kp_query='+encodeURIComponent(title);
const eais='https://ekinobilet.fond-kino.ru/statistics/';
const kino='https://www.kinometro.ru/box/show/region/ruonly/';
const norm=s=>s.toLocaleLowerCase('ru').replaceAll('ё','е');
const pdfReport=()=>data.pdf_reports.find(r=>r.kind===(period==='weekend'?'weekend':'week'));
const pdfRow=title=>pdfReport()?.records.find(r=>r.title===title);
const kinoRow=title=>data.kinometro.records.find(r=>norm(r.title).startsWith(norm(title)));
function el(tag,cls,text){const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=text;return node}
function anchor(title,url,cls){const a=el('a',cls,title);a.href=url;a.target='_blank';a.rel='noopener';return a}
function signed(n,d=0){return (n>0?'+':'')+fmt(n,d)}
function noun(n,forms){return forms[new Intl.PluralRules('ru').select(n)]||forms.many}
function render(){
 const records=data.periods[period].records;
 const totalGross=records.reduce((s,r)=>s+r.gross_rub,0), totalViewers=records.reduce((s,r)=>s+r.viewers,0);
 const total=metric==='gross'?totalGross:totalViewers, lead=records[0],leadMeasure=metric==='gross'?lead.gross_rub:lead.viewers;
 $('heading-date').textContent=dates(data.periods[period]);document.querySelector('.edition span').textContent='ОТЧЁТ №'+data.periods[period].issue; document.querySelector('.sidebar-bottom p').textContent='Сборы · '+checked(data.periods[period]);document.querySelector('.method-section .date-tag').textContent='Сборы · '+checked(data.periods[period]);
 $('period-note').textContent=dates(data.periods[period]);
 $('leader-title').textContent=lead.title;$('leader-title').href=kp(lead.title);
 $('leader-gross').textContent=million(lead.gross_rub);
 const pdf=pdfRow(lead.title);$('leader-total').textContent=million(pdf?.total_gross_rub);$('leader-total-source').href=pdf?.source_url||data.periods[period].report_url;
 $('top-gross').textContent=million(totalGross);$('top-viewers').textContent=fmt(totalViewers/1000,1);
 $('rank-subtitle').textContent=(metric==='gross'?'По сборам':'Зрители фильмов из топ-5 по кассе')+(period==='weekend'?' за уикенд':' за неделю');
 $('chart-unit').textContent=(metric==='gross'?'млн ₽':'тыс. зрителей')+' · шкала от нуля';
 const measure=r=>metric==='gross'?r.gross_rub:r.viewers;
 const ceiling=Math.ceil(Math.max(...records.map(measure))/(metric==='gross'?50e6:100e3))*(metric==='gross'?50e6:100e3);
 const chart=$('rank-chart');chart.replaceChildren();
 records.forEach(r=>{
  const row=el('div','rank-row'),num=el('span','rank-num',String(r.rank).padStart(2,'0')),body=el('div','rank-data'),caption=el('div','rank-caption');
  const value=metric==='gross'?million(r.gross_rub):fmt(r.viewers/1000,1);
  caption.append(anchor(r.title,kp(r.title)),el('strong','',value));
  const track=el('div','rank-track'),fill=el('div','rank-fill');fill.style.width=(measure(r)/ceiling*100)+'%';track.append(fill);track.setAttribute('role','img');track.setAttribute('aria-label',r.title+': '+(metric==='gross'?fmt(r.gross_rub)+' рублей':fmt(r.viewers)+' зрителей')+'. Место по кассе '+r.rank);
  body.append(caption,track);row.append(num,body);chart.append(row);
 });
 const share=leadMeasure/total*100;
 $('donut-fill').style.strokeDasharray=share+' '+(100-share);$('share-value').textContent=fmt(share,1)+'%';
 $('share-film').textContent=lead.title;$('share-label').textContent=metric==='gross'?'кассы топ-5':'зрителей топ-5';$('share-leader').textContent=fmt(share,1)+'%';$('share-rest').textContent=fmt(100-share,1)+'%';
 $('donut').setAttribute('aria-label',lead.title+': '+fmt(share,1)+'% '+(metric==='gross'?'кассы':'зрителей')+' внутри топ-5 ЕАИС');
 $('week-notice').hidden=false;$('week-notice').textContent='Сравнение источников: '+dates(data.comparison_eais)+'. Сравниваются только совпадающие периоды. Недельная таблица Kinometro не подтверждена.';
 const tbody=$('film-table');tbody.replaceChildren();
 records.forEach(r=>{
  const tr=el('tr'),name=el('td');name.append(el('span','table-rank',String(r.rank).padStart(2,'0')),anchor(r.title,kp(r.title)));
  const p=pdfRow(r.title), gross=el('td','',precise?fmt(r.gross_rub)+' ₽':million(r.gross_rub)+' млн ₽'),viewers=el('td','',precise?fmt(r.viewers):fmt(r.viewers/1000,1)+' тыс.'),lifetime=el('td');
  if(p) lifetime.append(anchor(precise?fmt(p.total_gross_rub)+' ₽':million(p.total_gross_rub)+' млн ₽',p.source_url));else lifetime.textContent='нет данных';
  const detail=el('td'),button=el('button','detail-button','Детали');button.type='button';button.setAttribute('aria-label','Детали: '+r.title);button.addEventListener('click',()=>showFilm(r));detail.append(button);tr.append(name,gross,viewers,lifetime,detail);tbody.append(tr);
 });
 document.querySelectorAll('[data-period]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.period===period)));
 document.querySelectorAll('[data-metric]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.metric===metric)));
 renderRatings();
}
function countLabel(s,key){
 if(key==='filmru_editor')return s.value===null?'оценки нет':'редакционная оценка';
 if(s.count_label)return s.count_label.replace('.',',')+' голосов';
 if(s.count!==null && s.count!==undefined)return fmt(s.count)+' '+(key==='kritikanstvo'?noun(s.count,{one:'рецензия',few:'рецензии',many:'рецензий'}):noun(s.count,{one:'голос',few:'голоса',many:'голосов'}));
 return '';
}
function missingLabel(s){
 return {insufficient_votes:'Мало оценок',no_reviews:'Нет рецензий',not_confirmed:'Не подтверждено',not_available:'Нет оценки'}[s.status]||'Нет данных';
}
function renderRatings(){
 const sources=data.ratings.sources,keys=Object.keys(sources).filter(k=>sources[k].group===ratingGroup);
 const head=$('ratings-head'),body=$('ratings-body');head.replaceChildren();body.replaceChildren();
 const header=el('tr');let name=el('th','','Фильм');name.scope='col';header.append(name);
 for(const key of keys){const th=el('th');th.scope='col';th.append(el('span','',sources[key].label),el('small','',sources[key].scale?'шкала 0–'+sources[key].scale:'нет подтверждённой оценки'));header.append(th)}
 head.append(header);
 for(const film of data.periods[period].records){
  const item=ratingFilm(film.title),row=el('tr'),title=el('th');title.scope='row';title.append(anchor(film.title,item.kinopoisk_url));row.append(title);
  for(const [i,key] of keys.entries()){
   const score=item.scores[key],cell=el('td');
   if(score.value!==null){
    const a=anchor(fmt(score.value,score.scale===100?0:1),score.url,'rating-value');a.append(el('span','rating-scale',' / '+score.scale));a.title=sources[key].description+' · дата значения '+(score.checked_date||'не подтверждено');
    const track=el('div','rating-track'),fill=el('div','rating-fill series-'+i);fill.style.width=(score.value/score.scale*100)+'%';track.append(fill);track.setAttribute('aria-hidden','true');
    cell.append(a,track,el('small','rating-count',countLabel(score,key)+(score.checked_date?' · '+score.checked_date:'')+(['saved_snapshot','unavailable'].includes(score.refresh_status)?' · сохранено':'')));
   }else{
    cell.append(anchor(missingLabel(score),score.url,'rating-missing'));
    if(score.count!==null && score.count!==undefined)cell.append(el('small','rating-count',countLabel(score,key)+(score.checked_date?' · '+score.checked_date:'')+(['saved_snapshot','unavailable'].includes(score.refresh_status)?' · сохранено':'')));
   }
   row.append(cell);
  }
  body.append(row);
 }
 document.querySelectorAll('[data-rating-group]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.ratingGroup===ratingGroup)));
 $('rating-scope').textContent=ratingGroup==='audience'?'Три зрительские аудитории · шкала 0–10':'Агрегат критиков и оценка редакции · разные методы';
 const difference=$('ratings-difference');difference.replaceChildren();
 if(ratingGroup==='audience'){
  const pairs=data.ratings.records.filter(r=>data.periods[period].records.some(f=>f.title===r.title)).filter(r=>r.scores.kinopoisk.value!==null&&r.scores.imdb.value!==null).map(r=>({r,delta:r.scores.kinopoisk.value-r.scores.imdb.value})).sort((a,b)=>Math.abs(b.delta)-Math.abs(a.delta));
  if(!pairs.length){difference.append(el('p','','Сопоставимых оценок нет'));return;}
  const largest=pairs[0],r=largest.r;
  difference.append(el('div','eyebrow orange-text','РАЗНИЦА АУДИТОРИЙ'),el('h3','',r.title),el('strong','rating-gap-number',fmt(Math.abs(largest.delta),1)+' балла'));
  const pair=el('div','rating-gap-pair');pair.append(anchor('Кинопоиск '+fmt(r.scores.kinopoisk.value,1),r.scores.kinopoisk.url),anchor('IMDb '+fmt(r.scores.imdb.value,1),r.scores.imdb.url));difference.append(pair);
  difference.append(el('p','',fmt(r.scores.kinopoisk.count)+' против '+fmt(r.scores.imdb.count)+' голосов. Разные аудитории, не ошибка данных.'));
  const list=el('div','rating-gap-list');list.append(el('div','rating-gap-list-heading','Кинопоиск − IMDb · баллы'));
  for(const p of pairs){const line=el('div');line.append(el('span','',p.r.title),el('b','',signed(p.delta,1)));list.append(line)}difference.append(list);
 }else{
  difference.append(el('div','eyebrow orange-text','РАЗНЫЕ МЕТОДЫ'),el('h3','','Средняя критиков ≠ оценка редакции'));
  const definitions=el('div','critic-definitions');definitions.append(el('strong','','0–100'),el('p','','Критиканство · средняя оценка русских изданий'),el('strong','','0–10'),el('p','','Film.ru · редакционная оценка'));difference.append(definitions);
  difference.append(el('p','','Общий рейтинг не считаем. Шкала и число рецензий остаются рядом с каждым значением.'));
 }
}
function renderComparison(){
 const chart=$('compare-chart');chart.replaceChildren();
 const records=data.comparison_eais.records,ceiling=Math.max(...records.map(r=>Math.max(r.gross_rub,kinoRow(r.title)?.gross_rub||0)))*1.08;document.querySelector('.comparison-section .date-tag').textContent=dates(data.comparison_eais);
 records.forEach(r=>{
  const k=kinoRow(r.title);if(!k)return;const d=k.gross_rub-r.gross_rub,percent=d/r.gross_rub*100;
  const row=el('div','compare-row'),name=el('div','compare-name');name.append(anchor(r.title,kp(r.title)),el('small','',signed(percent,Math.abs(percent)<.01?3:2)+'% · '+signed(d)+' ₽'));
  const pair=el('div','pair-bars');
  for(const [cls,value,label] of [['eais',r.gross_rub,'ЕАИС'],['kino',k.gross_rub,'Kinometro']]){
   const line=el('div','pair-line '+cls),track=el('div','pair-track'),fill=el('div','pair-fill '+(cls==='eais'?'purple':'blue'));
   fill.style.width=value/ceiling*100+'%';track.append(fill);line.append(track,el('b','',million(value)));line.setAttribute('role','img');line.setAttribute('aria-label',r.title+', '+label+': '+fmt(value)+' рублей');pair.append(line);
  }
  row.append(name,pair);chart.append(row);
 });
}
function showFilm(r){
 $('dialog-title').textContent=r.title;const content=$('dialog-content');content.replaceChildren();
 const p=pdfRow(r.title);
 function block(label,value,source,url){const box=el('div','dialog-metric');box.append(el('span','',label),el('strong','',value),anchor(source,url));content.append(box)}
 block('ЕАИС · '+dates(data.periods[period]),fmt(r.gross_rub)+' ₽ · '+fmt(r.viewers)+' зрителей','ЕАИС · '+checked(data.periods[period]),eais);
 if(p)block('Фонд кино PDF · общая касса',fmt(p.total_gross_rub)+' ₽','Отчёт на конец выбранного периода',p.source_url);
 else content.append(el('p','','Общая касса не найдена в выборке PDF.'));
 const ratings=ratingFilm(r.title);content.append(el('h3','','Оценки и даты значений'));
 const grid=el('div','dialog-ratings-grid');
 for(const [key,source] of Object.entries(data.ratings.sources)){
  const score=ratings.scores[key],box=el('div','dialog-rating');
  box.append(el('span','',source.label),anchor(score.value===null?missingLabel(score):fmt(score.value,score.scale===100?0:1)+' / '+score.scale,score.url));
  box.append(el('small','',(score.checked_date||'Не подтверждено')+' · '+(countLabel(score,key)||source.description)));grid.append(box);
 }content.append(grid);content.append(el('p','dialog-note','Рейтинги имеют собственную дату проверки. Для новых фильмов ссылка может вести на поиск Кинопоиска.'));
 $('film-dialog').showModal();
}
document.querySelectorAll('[data-period]').forEach(b=>b.addEventListener('click',()=>{period=b.dataset.period;render()}));
document.querySelectorAll('[data-metric]').forEach(b=>b.addEventListener('click',()=>{metric=b.dataset.metric;render()}));
document.querySelectorAll('[data-rating-group]').forEach(b=>b.addEventListener('click',()=>{ratingGroup=b.dataset.ratingGroup;renderRatings()}));
$('precision').addEventListener('click',()=>{precise=!precise;$('precision').textContent=precise?'Сократить числа':'Показать точные числа';$('precision').setAttribute('aria-pressed',String(precise));render()});
$('dialog-close').addEventListener('click',()=>$('film-dialog').close());
$('film-dialog').addEventListener('click',e=>{if(e.target===$('film-dialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close()}});
$('download').addEventListener('click',()=>{const a=document.createElement('a');a.href='kinopulse.xlsx';a.download='kinopulse.xlsx';a.click()});
document.querySelectorAll('.nav-link').forEach(a=>a.addEventListener('click',()=>{document.querySelectorAll('.nav-link').forEach(n=>n.classList.toggle('active',n===a))}));
document.querySelector('.rating-checked').textContent='Дата рядом с каждой оценкой';document.querySelector('.ratings-table caption').textContent='Оценки разных источников с датами проверки';const ps=$('pdf-sources');ps.querySelectorAll('a').forEach(a=>a.remove());for(const p of data.pdf_reports)ps.append(anchor((p.kind==='weekend'?'Уикенд · ':'Неделя · ')+dates(data.periods[p.kind]),p.source_url));render();renderComparison();
})();

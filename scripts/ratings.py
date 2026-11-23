"""Refresh confirmed film identities only; retain dated evidence on source failure."""
import json,re
from html import unescape
from html.parser import HTMLParser

class Node:
    def __init__(self,tag='',attrs=None):self.tag,self.attrs,self.children=tag,dict(attrs or []),[]
    def walk(self):
        yield self
        for c in self.children:
            if isinstance(c,Node):yield from c.walk()
    def text(self):return ' '.join(c.text() if isinstance(c,Node) else c for c in self.children)
    def has(self,cls):return cls in self.attrs.get('class','').split()
class Tree(HTMLParser):
    voids={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
    def __init__(self,text):
        super().__init__();self.root=Node();self.stack=[self.root];self.feed(text)
    def handle_starttag(self,tag,attrs):
        n=Node(tag,attrs);self.stack[-1].children.append(n)
        if tag not in self.voids:self.stack.append(n)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:self.stack=self.stack[:i];break
    def handle_data(self,text):self.stack[-1].children.append(text)
def clean(text):return re.sub(r'\s+',' ',unescape(text)).strip()
def number(text):
    m=re.match(r'([\d.]+)\s',clean(text));return float(m[1]) if m else None

def refresh_ratings(data,fetch,today):
    for film in data['ratings']['records']:
        if not film.get('key'):continue # New identities must be confirmed before linking ratings.
        scores=film['scores']
        for key in scores:scores[key]['last_attempt']=today
        for group in ('filmru','kritikanstvo'):
            keys=['filmru_users','filmru_editor'] if group=='filmru' else ['kritikanstvo']
            try:
                url=scores[keys[0]]['url'];tree=Tree(fetch(url).decode()).root
                if group=='filmru':
                    nodes=[n for n in tree.walk() if n.has('wrapper_movies_scores_score')]
                    if len(nodes)<3:raise ValueError('Film.ru score layout not found')
                    movies=[]
                    for n in tree.walk():
                        if n.tag=='script' and n.attrs.get('type')=='application/ld+json':
                            j=json.loads(''.join(c for c in n.children if isinstance(c,str)))
                            if j.get('@type')=='Movie':movies.append(j)
                    if not movies or str(movies[0].get('dateCreated'))!=str(film['year']):raise ValueError('Film year mismatch')
                    count=movies[0].get('aggregateRating',{}).get('ratingCount')
                    for key,idx in [('filmru_users',2),('filmru_editor',0)]:
                        value=number(nodes[idx].text())
                        scores[key].update(value=value,count=int(count) if key=='filmru_users' and count else None,checked_date=today,status='confirmed' if value is not None else ('insufficient_votes' if key=='filmru_users' else 'not_available'),refresh_status='ok')
                else:
                    node=next(n for n in tree.walk() if n.has('page_item_site_rating'))
                    text=clean(node.text());m=re.match(r'(\d+) ',text);count=re.search(r'изданий (\d+) реценз',text)
                    value=int(m[1]) if m else None
                    scores['kritikanstvo'].update(value=value,count=int(count[1]) if count else 0,checked_date=today,status='confirmed' if value is not None else 'no_reviews',refresh_status='ok')
            except Exception as error:
                for key in keys:scores[key]['refresh_status']='unavailable';scores[key]['refresh_error']=str(error)[:180]
        # KP and IMDb require a supported API or a working public HTML rating.
        # Do not treat a successful challenge/empty HTTP response as refreshed evidence.
        for key in ('kinopoisk','imdb'):scores[key]['refresh_status']='saved_snapshot'

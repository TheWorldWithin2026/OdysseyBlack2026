# Real-browser test of the weekly digest on Today.
import json, datetime
from playwright.sync_api import sync_playwright
fails=0
def t(n,c):
    global fails
    print(('PASS: ' if c else 'FAIL: ')+n)
    if not c: fails+=1
D=datetime.date.today()
iso=lambda n:(D+datetime.timedelta(days=n)).isoformat()
now_ms=int(datetime.datetime.now().timestamp()*1000)
PIPE=[{"id":now_ms-86400000,"name":"A","company":"X","stage":"contacted","lastContact":iso(-1),"followUp":iso(-2)},
      {"id":now_ms-30*86400000,"name":"B","company":"Y","stage":"contacted","lastContact":iso(-20)},
      {"id":now_ms-2*86400000,"name":"C","company":"Z","stage":"trial-sched"},
      {"id":5,"name":"D","company":"W","stage":"active","monthlyValue":3000}]
PART=[{"id":"pt-111111","name":"Hotel P","type":"hotel","status":"active","lastContact":iso(-2),"nextFollow":iso(-1),"sent":4,"won":1}]
with sync_playwright() as p:
    b=p.chromium.launch()
    for w,h in [(390,844),(1440,900)]:
        pg=b.new_page(viewport={'width':w,'height':h}); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.goto('http://localhost:8765/index.html')
        td=pg.inner_text('#today-body')
        t(f'[{w}] digest card present on a fresh install','Weekly digest' in td.replace('WEEKLY DIGEST','Weekly digest') or 'WEEKLY DIGEST' in td)
        txt=pg.evaluate('digestText()')
        t(f'[{w}] empty data: honest, tells you to add prospects','no scan yet' in txt and 'Add prospects in Prospect Builder' in txt and '0 prospects added' in txt)
        pg.evaluate("localStorage.setItem('ob-pipeline',JSON.stringify(%s));localStorage.setItem('ob-partners',JSON.stringify(%s))"%(json.dumps(PIPE),json.dumps(PART))); pg.reload()
        txt=pg.evaluate('digestText()')
        t(f'[{w}] pipeline: 2 added this week (not the 30-day-old one or the tiny id)','2 prospects added' in txt)
        t(f'[{w}] pipeline: 1 contacted in last 7 days','1 contacted in the last 7 days' in txt)
        t(f'[{w}] pipeline: 1 overdue follow-up','1 follow-up overdue' in txt)
        t(f'[{w}] pipeline: 1 in trial stages, 1 client at $3,000','1 in trial stages' in txt and '1 client ($3,000 per month' in txt)
        t(f'[{w}] partners: 1 tracked, 1 contacted this week, 1 due, 4 sent 1 became client','1 tracked; 1 contacted in the last 7 days; 1 follow-up due; 4 referrals sent, 1 became a client' in txt)
        t(f'[{w}] focus list tells you to clear overdue and follow up partners','Clear the 1 overdue pipeline follow-up first' in txt and 'Follow up with 1 partner that is due' in txt)
        t(f'[{w}] sprint not started line','30-day sprint: not started' in txt)
        pg.evaluate("localStorage.setItem('ob-radar',JSON.stringify({seen:['a'],watch:{'x':'contacted','y':'meeting'},sprintStart:null,sprintDone:{},hotels:{},custom:[],lastScanAt:new Date().toISOString(),scanCache:[{id:'a',title:'t',url:'https://e.com',source:'s'},{id:'b',title:'t2',url:'https://e.com/2',source:'s'}]}))"); pg.reload()
        txt=pg.evaluate('digestText()')
        t(f'[{w}] radar: 1 unreviewed headline, 1 contacted, 1 meeting','1 headline you have not reviewed' in txt and '1 watchlist company contacted, 1 with a meeting set' in txt)
        pg.evaluate("window.__copied=null;Object.defineProperty(navigator,'clipboard',{value:{writeText:function(t){window.__copied=t;return Promise.resolve();}},configurable:true})")
        pg.click('#today-body button:has-text("Copy digest")'); pg.wait_for_timeout(200)
        t(f'[{w}] copy button copies the digest text',pg.evaluate('window.__copied')is not None and 'Odyssey Black weekly digest' in pg.evaluate('window.__copied'))
        pg.evaluate("localStorage.setItem('ob-pipeline',JSON.stringify([{id:1,name:'<img src=x onerror=window.__xd=1>',company:'<b>x</b>',stage:'contacted',lastContact:'%s'}]))"%iso(-1)); pg.reload()
        t(f'[{w}] hostile data cannot execute in digest',pg.evaluate('window.__xd')is None)
        t(f'[{w}] no horizontal page scroll',not pg.evaluate('document.documentElement.scrollWidth>window.innerWidth+1'))
        t(f'[{w}] no page errors',not errs)
        pg.close()
    b.close()
print('FAILS',fails)

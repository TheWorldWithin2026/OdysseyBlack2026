# Real-browser test of Results by Channel. Seeds known data and checks the exact numbers.
import json, sys
from playwright.sync_api import sync_playwright
fails=0
def t(n,c):
    global fails
    print(('PASS: ' if c else 'FAIL: ')+n)
    if not c: fails+=1
SMALL=[
 {"id":1,"travel":"heavy","name":"A","company":"X","source":"linkedin","stage":"contacted","responseStatus":"positive","lastContact":"2026-10-01","ea":{"active":True,"name":"Ann"}},
 {"id":2,"travel":"heavy","name":"B","company":"X","source":"linkedin","stage":"contacted","responseStatus":"negative","lastContact":"2026-10-01"},
 {"id":3,"travel":"moderate","name":"C","company":"X","source":"linkedin","stage":"identified","responseStatus":"none"},
 {"id":4,"travel":"heavy","name":"D","company":"X","source":"referral","stage":"active","monthlyValue":3000,"responseStatus":"positive","lastContact":"2026-10-02"},
 {"id":5,"travel":"light","name":"E","company":"X","source":"hotel","stage":"trial-done","responseStatus":"pending"},
 {"id":6,"name":"F","company":"X","source":"hotel","stage":"identified","responseStatus":"none"},
 {"id":7,"travel":"xyz","name":"G","company":"X","source":"xyz","stage":"contacted","responseStatus":"none","lastContact":"2026-10-03"}]
def mk(n,src,replied,start):
    return [{"id":start+i,"name":src+str(i),"company":"Y","source":src,"stage":"contacted","lastContact":"2026-10-01","responseStatus":"positive" if i<replied else "none"} for i in range(n)]
BIG=mk(10,"cold",5,100)+mk(10,"linkedin",2,200)
with sync_playwright() as p:
    b=p.chromium.launch()
    for w,h in [(390,844),(1440,900)]:
        pg=b.new_page(viewport={'width':w,'height':h}); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.goto('http://localhost:8765/index.html')
        pg.click('.tab[onclick*="results"]')
        t(f'[{w}] empty state is friendly','No prospects yet' in pg.inner_text('#results-body'))
        pg.evaluate("localStorage.setItem('ob-pipeline',JSON.stringify(%s))"%json.dumps(SMALL)); pg.reload(); pg.click('.tab[onclick*="results"]')
        def row(label): return [c.strip() for c in pg.locator('#results-body tr',has_text=label).first.locator('td').all_inner_texts()]
        li=row('LinkedIn'); t(f'[{w}] LinkedIn: 3 added, 2 contacted, 2 replied, 100%',li[1:5]==['3','2','2','100%'])
        rf=row('Referral'); t(f'[{w}] Referral: 1 client and $3,000 MRR',rf[1]=='1' and rf[6]=='1' and rf[7]=='$3,000')
        ho=row('Hotel concierge'); t(f'[{w}] Hotel: trial counted, 1 contacted (stage beyond identified)',ho[1]=='2' and ho[2]=='1' and ho[5]=='1')
        t(f'[{w}] unknown source grouped as Not recorded',row('Not recorded')[1]=='1')
        al=row('All prospects'); t(f'[{w}] total prospects counted (7)',al[1]=='7')
        t(f'[{w}] small samples flagged, no winner declared','too few to judge' in pg.inner_text('#results-body') and 'Not enough data' in pg.inner_text('#results-body'))
        hv=row('Heavy'); t(f'[{w}] travel: Heavy 3 added, 3 contacted, 3 replied, 100%',hv[1:5]==['3','3','3','100%'])
        t(f'[{w}] travel: Moderate 1 added, 0 contacted',row('Moderate')[1:3]==['1','0'])
        t(f'[{w}] travel: Light 1 added',row('Light (occasional)')[1]=='1')
        t(f'[{w}] travel: invalid/missing grouped as Not recorded (2)',pg.locator('#results-body tr',has_text='Not recorded').nth(1).locator('td').nth(1).text_content().strip()=='2')
        ea=row('Through an assistant'); dr=row('Direct to executive'); t(f'[{w}] assistant vs direct split',ea[1]=='1' and dr[1]=='6')
        t(f'[{w}] no horizontal PAGE scroll (table scrolls inside card)',not pg.evaluate('document.documentElement.scrollWidth>window.innerWidth+1'))
        pg.evaluate("localStorage.setItem('ob-pipeline',JSON.stringify(%s))"%json.dumps(BIG)); pg.reload(); pg.click('.tab[onclick*="results"]')
        v=pg.inner_text('#results-body')
        t(f'[{w}] winner named once two channels have 10+ contacted','Best reply rate so far' in v and 'Cold outreach' in v.split('Best reply rate so far')[1][:60] and '50%' in v)
        # new sources selectable in Prospect Builder
        pg.click('.tab[onclick*="prospect"]')
        opts=pg.eval_on_selector_all('#p-source option','els=>els.map(e=>e.value)')
        t(f'[{w}] Prospect Builder offers Perimeter Radar + Hotel sources','perimeter' in opts and 'hotel' in opts)
        t(f'[{w}] no page errors',not errs)
        if w==390:
            pg.click('.tab[onclick*="results"]'); pg.screenshot(path='/tmp/results-390.png')
        pg.close()
    b.close()
print('FAILS',fails); sys.exit(1 if fails else 0)

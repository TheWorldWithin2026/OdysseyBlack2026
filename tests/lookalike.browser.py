# Real-browser test of the Lookalike Finder.
import json, urllib.parse
from playwright.sync_api import sync_playwright
fails=0
def t(n,c):
    global fails
    print(('PASS: ' if c else 'FAIL: ')+n)
    if not c: fails+=1
with sync_playwright() as p:
    b=p.chromium.launch()
    for w,h in [(390,844),(1440,900)]:
        pg=b.new_page(viewport={'width':w,'height':h}); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.goto('http://localhost:8765/index.html')
        pg.click('.tab[onclick*="lookalike"]')
        t(f'[{w}] empty state is friendly','No clients yet' in pg.inner_text('#lk-clients'))
        pg.click('#panel-lookalike button:has-text("Add client")')
        t(f'[{w}] empty name refused',pg.evaluate('lkState.clients.length')==0)
        pg.fill('#lk-name','Acme Brokers'); pg.fill('#lk-ind','Insurance brokerage'); pg.select_option('#lk-size','mid'); pg.select_option('#lk-area','alpharetta'); pg.select_option('#lk-books','assistant')
        pg.click('#panel-lookalike button:has-text("Add client")')
        pg.fill('#lk-name','<img src=x onerror=window.__xl=1>Evil Co'); pg.fill('#lk-ind','Insurance brokerage'); pg.select_option('#lk-area','perimeter')
        pg.click('#panel-lookalike button:has-text("Add client")')
        t(f'[{w}] two clients added, names escaped',pg.evaluate('lkState.clients.length')==2 and pg.evaluate('window.__xl')is None and '<img' in pg.inner_text('#lk-clients'))
        pat=pg.inner_text('#lk-pattern')
        t(f'[{w}] pattern: most common industry 2 of 2','Insurance brokerage (2 of 2)' in pat)
        t(f'[{w}] pattern: size and who books (selects keep their value between adds)','200-1,000' in pat and 'Executive assistant (2 of 2)' in pat)
        hrefs=pg.eval_on_selector_all('#lk-body a','els=>els.map(e=>e.href)')
        t(f'[{w}] search links built (2 areas + news + 2 LinkedIn = 5)',len(hrefs)==5)
        t(f'[{w}] links only go to google.com and linkedin.com',all(urllib.parse.urlparse(h).hostname in ('www.google.com','www.linkedin.com') for h in hrefs))
        t(f'[{w}] links open safely',pg.eval_on_selector_all('#lk-body a','els=>els.every(e=>e.target==="_blank"&&e.rel.indexOf("noopener")!==-1)'))
        txt=pg.inner_text('#lk-body')
        t(f'[{w}] Apollo filters use client size and book titles','201-1000' in txt and 'executive assistant' in txt)
        t(f'[{w}] names no companies on its own','Marsh' not in txt and 'Gallagher' not in txt)
        pg.fill('#lk-co-0','Candidate Corp'); pg.select_option('#lk-ar-0','cobb'); pg.click('#lk-body button:has-text("Add to Radar watchlist")')
        t(f'[{w}] candidate goes to Radar watchlist with its source note',pg.evaluate("radarState.custom.filter(function(c){return c.name==='Candidate Corp'&&c.area==='cobb'&&c.note.indexOf('Similar to Acme Brokers')===0}).length")==1)
        pg.click('#panel-lookalike button:has-text("Remove") >> nth=0')
        t(f'[{w}] remove needs a second click',pg.evaluate('lkState.clients.length')==2)
        pg.click('#panel-lookalike button:has-text("Click again")'); 
        t(f'[{w}] second click removes',pg.evaluate('lkState.clients.length')==1)
        # pipeline clients appear automatically
        pg.evaluate("localStorage.setItem('ob-pipeline',JSON.stringify([{id:1,name:'Sam',company:'Auto Client Inc',stage:'active',industry:'Technology'},{id:2,name:'Lee',company:'Not Yet Inc',stage:'contacted',industry:'Technology'}]))"); pg.reload(); pg.click('.tab[onclick*="lookalike"]')
        t(f'[{w}] active pipeline company appears, prospects do not','Auto Client Inc' in pg.inner_text('#lk-clients') and 'Not Yet Inc' not in pg.inner_text('#lk-clients'))
        hostile={"clients":[{"id":"x'+alert(1)+'","name":"Evil","industry":"i"*500,"size":"zzz","area":"zzz","books":"zzz","note":"n"*900},"junk",{"name":""}]}
        pg.evaluate("localStorage.setItem('ob-lookalike',JSON.stringify(%s))"%json.dumps(hostile)); pg.reload(); pg.click('.tab[onclick*="lookalike"]')
        ok=pg.evaluate("lkState.clients.length===1&&/^lk-\\d{6,}$/.test(lkState.clients[0].id)&&lkState.clients[0].size===''&&lkState.clients[0].area===''&&lkState.clients[0].books===''&&lkState.clients[0].industry.length<=60&&lkState.clients[0].note.length<=200")
        t(f'[{w}] tampered backup is sanitised',ok)
        t(f'[{w}] ob-lookalike in backup/sync allowlist',pg.evaluate("APPROVED_BACKUP_KEYS.indexOf('ob-lookalike')!==-1"))
        t(f'[{w}] no horizontal page scroll',not pg.evaluate('document.documentElement.scrollWidth>window.innerWidth+1'))
        t(f'[{w}] no page errors',not errs)
        pg.close()
    b.close()
print('FAILS',fails)

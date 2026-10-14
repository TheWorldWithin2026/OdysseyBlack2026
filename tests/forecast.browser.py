# Real-browser test of the revenue forecast with known numbers.
import json
from playwright.sync_api import sync_playwright
fails=0
def t(n,c):
    global fails
    print(('PASS: ' if c else 'FAIL: ')+n)
    if not c: fails+=1
def P(i,stage,val=None,**k):
    d={"id":i,"name":"P%d"%i,"company":"C%d"%i,"stage":stage}
    if val is not None: d["monthlyValue"]=val
    d.update(k); return d
PIPE=[P(1,'active',3000),P(2,'recurring',1000),
      P(3,'identified',600),P(4,'identified',1400),
      P(5,'contacted',3200),P(6,'contacted'),
      P(7,'trial-sched',1000),P(8,'trial-done',2000)]
with sync_playwright() as p:
    b=p.chromium.launch()
    for w,h in [(390,844),(1440,900)]:
        pg=b.new_page(viewport={'width':w,'height':h}); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.goto('http://localhost:8765/index.html')
        pg.click('.tab[onclick*="forecast"]')
        t(f'[{w}] empty data renders zeros, no errors','$0' in pg.inner_text('#fc-body') and not errs)
        pg.evaluate("localStorage.setItem('ob-pipeline',JSON.stringify(%s))"%json.dumps(PIPE)); pg.reload(); pg.click('.tab[onclick*="forecast"]')
        tx=pg.inner_text('#fc-body')
        t(f'[{w}] current monthly revenue $4,000 from 2 clients','$4,000' in tx and '2 clients' in tx)
        t(f'[{w}] expected from pipeline $1,766 (60+256+350+1,100)','$1,766' in tx)
        t(f'[{w}] expected total $5,766 and $69,192 per year','$5,766' in tx and '$69,192' in tx)
        t(f'[{w}] upper bound $12,200 labelled not a forecast','$12,200' in tx and 'not a forecast' in tx)
        t(f'[{w}] prospect without a value is flagged and left out','1 with no value' in tx)
        t(f'[{w}] placeholder disclaimer and estimate provenance shown','placeholder guesses' in tx and "app's estimate" in tx)
        pg.fill('#fc-target','10000'); pg.press('#fc-target','Tab')
        tx=pg.inner_text('#fc-body')
        t(f'[{w}] goal: gap $6,000 and 3 more clients at $2,000 average','$6,000' in tx and '3</strong> more' in pg.inner_html('#fc-body') )
        t(f'[{w}] goal: contacts needed says not enough data below 10 contacted','not enough data yet' in tx)
        more=[P(100+i,'contacted',None,lastContact='2026-10-01') for i in range(10)]
        pg.evaluate("localStorage.setItem('ob-pipeline',JSON.stringify(%s))"%json.dumps(PIPE+more)); pg.reload(); pg.click('.tab[onclick*="forecast"]')
        rs=pg.evaluate("resultStats(pipeline)")
        need=-(-3//1) and __import__('math').ceil(3/(rs['clients']/rs['contacted']))
        t(f'[{w}] goal: contacts needed matches measured rate ({rs["clients"]}/{rs["contacted"]})',f'<strong>{need}</strong> prospects to contact' in pg.inner_html('#fc-body'))
        pg.locator('#fc-body input[aria-label*="Identified"]').fill('50'); pg.press('#fc-body input[aria-label*="Identified"]','Tab')
        t(f'[{w}] editing win chance to 50% updates expected ($1,000 + 256 + 350 + 1,100 = $2,706)','$2,706' in pg.inner_text('#fc-body'))
        pg.reload(); pg.click('.tab[onclick*="forecast"]')
        t(f'[{w}] win chance and goal persist across reload',pg.locator('#fc-body input[aria-label*="Identified"]').input_value()=='50' and pg.input_value('#fc-target')=='10000')
        pg.click('#fc-body button:has-text("Reset win chances")')
        t(f'[{w}] reset restores the default 3%',pg.locator('#fc-body input[aria-label*="Identified"]').input_value()=='3')
        pg.locator('#fc-body input[aria-label*="Contacted"]').fill('250'); pg.press('#fc-body input[aria-label*="Contacted"]','Tab')
        t(f'[{w}] win chance is capped at 100%',pg.locator('#fc-body input[aria-label*="Contacted"]').input_value()=='100')
        pg.locator('#fc-body input[aria-label*="Contacted"]').fill('abc'); pg.press('#fc-body input[aria-label*="Contacted"]','Tab')
        t(f'[{w}] junk win chance falls back to the default 8%',pg.locator('#fc-body input[aria-label*="Contacted"]').input_value()=='8')
        pg.evaluate("localStorage.setItem('ob-forecast',JSON.stringify({probs:{identified:'-5',contacted:'999',assistant:'x','trial-sched':null,evil:5},target:'-1'}))"); pg.reload(); pg.click('.tab[onclick*="forecast"]')
        ok=pg.evaluate("fcState.probs.identified===0&&fcState.probs.contacted===100&&fcState.probs.assistant===15&&fcState.probs['trial-sched']===35&&!('evil' in fcState.probs)&&fcState.target===0")
        t(f'[{w}] tampered backup is sanitised',ok)
        t(f'[{w}] ob-forecast in backup/sync allowlist',pg.evaluate("APPROVED_BACKUP_KEYS.indexOf('ob-forecast')!==-1"))
        t(f'[{w}] no horizontal page scroll',not pg.evaluate('document.documentElement.scrollWidth>window.innerWidth+1'))
        t(f'[{w}] no page errors',not errs)
        pg.close()
    b.close()
print('FAILS',fails)

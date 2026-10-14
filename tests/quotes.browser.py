# Real-browser test of the Quote Builder with known numbers from the booking-system matrices.
import json, re
from playwright.sync_api import sync_playwright
fails=0
def t(n,c):
    global fails
    print(('PASS: ' if c else 'FAIL: ')+n)
    if not c: fails+=1
def total(pg,veh): return pg.locator('[data-qt-total="%s"]'%veh).text_content().strip()
def setv(pg,sel,val):
    pg.fill(sel,val)
def open_tab(pg):
    pg.click('.tab[onclick*="quotes"]')
with sync_playwright() as p:
    b=p.chromium.launch()
    for w,h in [(390,844),(1440,900)]:
        ctx=b.new_context(viewport={'width':w,'height':h}); pg=ctx.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.on('dialog',lambda d:d.accept())
        pg.goto('http://localhost:8765/index.html'); open_tab(pg)
        t(f'[{w}] tab opens, empty state asks for miles',('Enter both addresses' in pg.text_content('#qt-result')) and not errs)
        # base pricing
        for miles,sed,suv,label in [('0.5','$94.25','$108.75','under 1 mile charges the first tier'),('5','$94.25','$108.75','5 miles'),('10','$94.25','$108.75','exactly 10 miles'),('18.4','$132.62','$154.92','18.4 miles (65 + 8.4 x 3.15, +45% service rate)')]:
            setv(pg,'#qt-miles',miles)
            t(f'[{w}] {label}: Sedan {sed}, SUV {suv}',total(pg,'sedan')==sed and total(pg,'suv')==suv)
        txt=pg.text_content('#qt-result')
        t(f'[{w}] no time given shows peak figures $152.84 and $185.98 and asks for the time','$152.84' in txt and '$185.98' in txt and 'Add the pickup date and time' in txt)
        # peak windows (2026-10-20 is a Tuesday)
        def at(date,time,mode='auto'):
            pg.fill('#qt-date',date); pg.fill('#qt-time',time); pg.select_option('#qt-peak',mode)
            return total(pg,'sedan'),total(pg,'suv')
        t(f'[{w}] Tuesday 15:00 is peak for both: $152.84 / $185.98',at('2026-10-20','15:00')==('$152.84','$185.98'))
        t(f'[{w}] Tuesday 13:59 is off-peak',at('2026-10-20','13:59')==('$132.62','$154.92'))
        t(f'[{w}] Tuesday 19:59 still peak, 20:00 off-peak',at('2026-10-20','19:59')[0]=='$152.84' and at('2026-10-20','20:00')[0]=='$132.62')
        t(f'[{w}] Monday ends 18:59 (peak) and 19:00 is off-peak',at('2026-10-19','18:59')[0]=='$152.84' and at('2026-10-19','19:00')[0]=='$132.62')
        t(f'[{w}] Friday 23:59 is peak',at('2026-10-16','23:59')[0]=='$152.84')
        t(f'[{w}] Saturday 03:00 is peak for both',at('2026-10-17','03:00')==('$152.84','$185.98'))
        t(f'[{w}] Sunday 03:00: SUV peak, Sedan not (Sunday unchecked for Sedan)',at('2026-10-18','03:00')==('$132.62','$185.98'))
        t(f'[{w}] Sunday 10:00 off-peak for both',at('2026-10-18','10:00')==('$132.62','$154.92'))
        t(f'[{w}] override: treat as off-peak on a peak time',at('2026-10-20','15:00','no')==('$132.62','$154.92'))
        t(f'[{w}] override: treat as peak on an off-peak time',at('2026-10-20','09:00','yes')==('$152.84','$185.98'))
        at('2026-10-20','15:00','auto')
        t(f'[{w}] peak line shown in the breakdown','Peak pricing +15.25%' in pg.text_content('#qt-result') and 'Peak pricing +20.05%' in pg.text_content('#qt-result'))
        t(f'[{w}] breakdown shows the 45% Executive & Service Rate line','Executive & Service Rate 45%' in pg.text_content('#qt-result'))
        # copy text
        qt=pg.evaluate('qtText()')
        t(f'[{w}] quote text has both prices, peak note, estimate wording and signature','Executive Sedan: $152.84 (includes peak pricing)' in qt and 'Executive SUV: $185.98' in qt and 'estimate' in qt and 'Kerry A. Pope' in qt and 'Odyssey Black, LLC' in qt)
        t(f'[{w}] quote text never mentions insurance or any outside company','nsurance' not in qt and 'Theo' not in qt and 'Ethio' not in qt)
        # booking-site check
        pg.fill('#qt-chk-sedan','152.84'); pg.fill('#qt-chk-suv','125.00')
        c=pg.text_content('#qt-check-out')
        t(f'[{w}] check: matching price says matches, differing price shows +$60.98','matches' in c and '+$60.98' in c)
        pg.fill('#qt-chk-sedan',''); pg.fill('#qt-chk-suv','')
        # maps link and pipeline pick
        pg.fill('#qt-from','6 Concourse Pkwy, Sandy Springs, GA'); pg.fill('#qt-to','Hartsfield-Jackson Atlanta International Airport')
        href=pg.get_attribute('#qt-maps','href')
        t(f'[{w}] Google Maps link appears with both addresses encoded','origin=6%20Concourse' in href and 'destination=Hartsfield' in href and pg.is_visible('#qt-maps'))
        # distance lookup: success then failure
        pg.route('**/.netlify/functions/distance*',lambda r:r.fulfill(status=200,content_type='application/json',body=json.dumps({'status':'OK','miles':22.7,'minutes':31})))
        pg.click('#qt-lookup')
        pg.wait_for_function("document.getElementById('qt-miles').value==='22.7'")
        t(f'[{w}] Get distance fills miles and message',('22.7' in pg.text_content('#qt-msg')) and pg.input_value('#qt-miles')=='22.7')
        pg.unroute('**/.netlify/functions/distance*')
        pg.route('**/.netlify/functions/distance*',lambda r:r.fulfill(status=502,content_type='application/json',body=json.dumps({'error':'routes_not_enabled'})))
        pg.click('#qt-lookup'); pg.wait_for_function("document.getElementById('qt-msg').textContent.indexOf('Routes API')!==-1")
        t(f'[{w}] distance failure keeps typed miles and explains the Routes API fix',pg.input_value('#qt-miles')=='22.7' and 'Routes API' in pg.text_content('#qt-msg'))
        pg.unroute('**/.netlify/functions/distance*')
        pg.route('**/.netlify/functions/distance*',lambda r:r.abort())
        pg.click('#qt-lookup'); pg.wait_for_function("document.getElementById('qt-msg').textContent.indexOf('did not work')!==-1")
        t(f'[{w}] network failure is handled without errors',not errs)
        pg.unroute('**/.netlify/functions/distance*')
        # hourly from vendor packet
        t(f'[{w}] hourly alternative shown from Vendor Packet rates','$125.00/hr, 3-hour minimum ($375.00)' in pg.text_content('#qt-result') and 'Sprinter $190.00/hr' in pg.text_content('#qt-result'))
        # save + log
        pg.fill('#qt-client','Newell Brands'); setv(pg,'#qt-miles','18.4')
        pg.click('#qt-result button:has-text("Save to quote log")')
        lg=pg.text_content('#qt-log')
        st=pg.evaluate("qtState.log")
        t(f'[{w}] saved quote appears with prices and a +3 day follow-up',len(st)==1 and 'Newell Brands' in lg and st[0]['follow']==pg.evaluate("todayAddDays(3)") and st[0]['sedan']==152.84 and st[0]['suv']==185.98)
        # Today follow-up
        pg.evaluate("qtSet(qtState.log[0].id,'follow','2026-10-01')")
        pg.click('.tab[onclick*="today"]')
        tt=pg.text_content('#today-body')
        t(f'[{w}] overdue quote shows on Today with Won/Lost',('Quote follow-up overdue' in tt) and pg.locator('#today-body button:has-text("Won")').count()==1)
        pg.locator('#today-body button:has-text("Won")').click()
        t(f'[{w}] marking won clears it from Today and counts in the log',('Quote follow-up overdue' not in pg.text_content('#today-body')) and pg.evaluate("qtState.log[0].status")=='won')
        open_tab(pg)
        t(f'[{w}] log summary: 1 won, 100% of decided','<strong>1</strong> won' in pg.inner_html('#qt-log') and '100%' in pg.text_content('#qt-log'))
        # persistence
        pg.reload(); open_tab(pg)
        t(f'[{w}] saved quote persists across reload',pg.evaluate("qtState.log.length")==1)
        # two-step delete
        pg.click('#qt-log button:has-text("Delete")'); t(f'[{w}] delete needs a second click',pg.evaluate("qtState.log.length")==1)
        pg.click('#qt-log button:has-text("Click again")'); t(f'[{w}] second click deletes',pg.evaluate("qtState.log.length")==0)
        # rate editing
        pg.fill('#qt-date',''); pg.fill('#qt-time',''); setv(pg,'#qt-miles','18.4')
        pg.click('#qt-rates details:nth-of-type(1) summary')
        inp=pg.locator('#qt-rates input[aria-label="Executive Sedan Remaining $ per mile"]'); inp.fill('4'); inp.press('Tab')
        t(f'[{w}] editing the Sedan per-mile rate to $4.00 reprices: (65 + 8.4 x 4) x 1.45 = $142.97',total(pg,'sedan')=='$142.97')
        pg.reload(); open_tab(pg); setv(pg,'#qt-miles','18.4')
        t(f'[{w}] edited rate persists',total(pg,'sedan')=='$142.97')
        pg.evaluate("qtSetDay('sedan',2,'on',false)")
        pg.fill('#qt-date','2026-10-20'); pg.fill('#qt-time','15:00')
        t(f'[{w}] turning off Tuesday peak for Sedan makes Tuesday 15:00 off-peak for Sedan only',total(pg,'sedan')=='$142.97' and total(pg,'suv')=='$185.98')
        pg.click('button:has-text("Reset rates")')
        t(f'[{w}] reset restores matrix and windows',pg.evaluate("qtState.rates.sedan.rem")==3.15 and total(pg,'sedan')=='$152.84')
        sv=pg.locator('#qt-svc'); sv.fill('40'); sv.press('Tab')
        t(f'[{w}] changing the service rate to 40% reprices Sedan peak: 105.41 x 1.40 = $147.57',total(pg,'sedan')=='$147.57')
        pg.reload(); open_tab(pg); pg.fill('#qt-miles','18.4'); pg.fill('#qt-date','2026-10-20'); pg.fill('#qt-time','15:00')
        t(f'[{w}] service rate persists',total(pg,'sedan')=='$147.57')
        pg.fill('#qt-svc','0'); pg.press('#qt-svc','Tab')
        t(f'[{w}] 0% removes the line and the copy sentence',total(pg,'sedan')=='$105.41' and 'Executive & Service Rate' not in pg.text_content('#qt-result') and 'Service Rate' not in pg.evaluate('qtText()'))
        pg.click('button:has-text("Reset rates")')
        t(f'[{w}] reset restores 45%',pg.evaluate("qtState.svc")==45 and total(pg,'sedan')=='$152.84')
        t(f'[{w}] copy text states the service rate is included','Prices include the 45% Executive & Service Rate' in pg.evaluate('qtText()'))
        # layout
        pg.fill('#qt-from','1'*5+' '+'Very Long Street Name '*8)
        t(f'[{w}] no horizontal scroll on the quotes tab',pg.evaluate("document.documentElement.scrollWidth<=window.innerWidth+1"))
        t(f'[{w}] page never says Theo',('Theo' not in pg.content()))
        t(f'[{w}] no page errors',not errs)
        ctx.close()
    # hostile stored data
    ctx=b.new_context(viewport={'width':1200,'height':900}); pg=ctx.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto('http://localhost:8765/index.html')
    bad={'svc':'abc','rates':{'sedan':{'first':{'miles':'abc','rate':-5},'next':{'miles':1e9,'rate':'x'},'rem':'NaN','peak':99999,'days':[1,2,3]},'suv':'nope'},
         'log':[{'id':'qt-1','client':'<img src=x onerror=window.__pwn=1>','from':'a'*500,'to':None,'miles':'abc','sedan':'zzz','suv':-3,'status':'hacked','follow':'not-a-date','at':'2026-10-01','time':'25:99'},None,5,{'id':'qt-1234567','client':'ok','miles':99999,'sedan':5,'suv':6,'status':'won'},{'id':'qt-1234567','client':'dup','miles':1}]}
    pg.evaluate("localStorage.setItem('ob-quotes',%s)"%json.dumps(json.dumps(bad))); pg.reload(); open_tab(pg)
    s=pg.evaluate("qtState")
    t('hostile rates fall back to defaults/clamps',s['rates']['sedan']['first']['miles']==1 and s['rates']['sedan']['first']['rate']==65 and s['rates']['sedan']['rem']==3.15 and s['rates']['sedan']['peak']==15.25 and len(s['rates']['sedan']['days'])==7 and s['rates']['suv']['rem']==3.79)
    t('hostile service rate falls back to 45',s['svc']==45)
    t('hostile log: junk rows dropped, ids regenerated/unique, status and numbers sanitized',len(s['log'])==3 and len(set(q['id'] for q in s['log']))==3 and all(q['status'] in('sent','won','lost') for q in s['log']) and s['log'][0]['sedan'] is None and s['log'][0]['suv'] is None and s['log'][0]['miles']==0 and s['log'][0]['follow']=='' and len(s['log'][0]['from'])==200 and s['log'][1]['miles']==2000)
    t('hostile client name is escaped, not executed',pg.evaluate("window.__pwn")is None and '<img' not in pg.inner_html('#qt-log').replace('&lt;img','') )
    t('hostile data raises no page errors',not errs)
    # backup/cloud keys
    t('ob-quotes is an approved backup/sync key with a label',pg.evaluate("APPROVED_BACKUP_KEYS.indexOf('ob-quotes')!==-1 && cloudKeyLabel('ob-quotes')==='Quotes'"))
    pg.evaluate("localStorage.setItem('ob-quotes',JSON.stringify({rates:{},log:[]}))")
    t('full backup includes ob-quotes',pg.evaluate("(function(){var k=APPROVED_BACKUP_KEYS;return k.indexOf('ob-quotes')>-1;})()"))
    ctx.close()
    # pipeline pick
    ctx=b.new_context(viewport={'width':1200,'height':900}); pg=ctx.new_page()
    pg.goto('http://localhost:8765/index.html')
    pg.evaluate("localStorage.setItem('ob-pipeline',JSON.stringify([{id:1,name:'Pat Lee',company:'Acme Corp',stage:'contacted'}]))"); pg.reload(); open_tab(pg)
    pg.select_option('#qt-pick',index=1)
    t('picking a prospect fills the client name',pg.input_value('#qt-client')=='Acme Corp')
    ctx.close()
    b.close()
print('ALL PASSED' if not fails else '%d FAILED'%fails)
raise SystemExit(1 if fails else 0)

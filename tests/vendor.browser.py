# Real-browser test of Vendor Packet & Proposal.
import json
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
        dialogs=[]; pg.on('dialog',lambda d:(dialogs.append(d.message),d.dismiss()))
        pg.goto('http://localhost:8765/index.html')
        pg.evaluate("localStorage.setItem('ob-pipeline',JSON.stringify([{id:5,name:'Pat',title:'EA',company:'Acme',stage:'identified'}]))"); pg.reload()
        pg.click('.tab[onclick*="vendor"]')
        t(f'[{w}] vendor panel active',pg.locator('#panel-vendor.active').count()==1)
        pv=pg.inner_text('#vp-preview')
        t(f'[{w}] short version has the five agreed rates only where selected','$125 / hour' in pv and '$150 / hour' in pv and '$190 / hour' in pv and '$225' not in pv)
        t(f'[{w}] sprinter overtime note shown','$220/hour' in pv)
        t(f'[{w}] insurance is NOT prefilled (blank highlighted)',pg.locator('#vp-preview .vp-blank').count()>=3 and 'still blank' in pg.inner_text('#vp-status'))
        t(f'[{w}] driving record line prefilled without license/DOB/address','0 points' in pv and '025141272' not in pg.content() and '1968' not in pg.content())
        t(f'[{w}] contact details from the website are prefilled','678-481-1421' in pv and 'concierge@odysseyblack.com' in pv and 'Up to 13 passengers' in pg.inner_text('#vp-preview'))
        pg.click('#vp-btn-full')
        pf=pg.inner_text('#vp-preview')
        t(f'[{w}] full version adds terms and acceptance','Acceptance' in pf and 'Cancellation policy' in pf and 'Insurance details' in pf)
        pg.check('#vp-rates input[type=checkbox] >> nth=4')
        t(f'[{w}] motorcoach shown as managed, not owned','Coordinated and dispatched' in pg.inner_text('#vp-preview') and '$250' in pg.inner_text('#vp-preview'))
        pg.select_option('#vp-pick',index=1)
        t(f'[{w}] prospect pick fills company',pg.input_value('#vp-for')=='Acme' and 'Pat, EA' in pg.input_value('#vp-attn'))
        pg.fill('#vp-for','<img src=x onerror=window.__xv=1>Evil')
        t(f'[{w}] hostile company name is escaped',pg.evaluate('window.__xv')is None and '<img' in pg.inner_text('#vp-preview'))
        pg.locator('#vp-ins input').first.fill('Carrier X'); 
        t(f'[{w}] typed insurance appears and blanks drop','Carrier X' in pg.inner_text('#vp-preview'))
        pg.locator('#vp-rates input[type=text] >> nth=0').fill('abc')
        t(f'[{w}] non-numeric rate rejected to blank',pg.evaluate("vendorState.rates[0].rate")=='')
        pg.locator('#vp-rates input[type=text] >> nth=0').fill('130')
        pg.reload(); pg.click('.tab[onclick*="vendor"]')
        t(f'[{w}] edits persist across reload','Carrier X' in pg.input_value('#vp-ins input >> nth=0') and pg.evaluate("vendorState.rates[0].rate")=='130')
        pg.evaluate("vpPrint()")
        t(f'[{w}] print root built with content, warns about blanks',pg.evaluate("document.getElementById('vp-print-root').innerText.includes('Odyssey Black VIP LLC')") and any('blank' in d for d in dialogs))
        t(f'[{w}] no horizontal page scroll',not pg.evaluate('document.documentElement.scrollWidth>window.innerWidth+1'))
        data=pg.evaluate("(function(){return APPROVED_BACKUP_KEYS.indexOf('ob-vendor')!==-1})()")
        t(f'[{w}] ob-vendor in backup/sync allowlist',data)
        pg.evaluate("localStorage.setItem('ob-vendor',JSON.stringify({co:{legal:123,phone:'x'.repeat(9000)},rates:[{id:'evil',rate:'<b>',on:true},{id:'sedan',rate:'1e9',min:'3',on:'yes',note:'n'}],__proto__:{x:1},ins:'bad'}))"); pg.reload(); pg.click('.tab[onclick*="vendor"]')
        t(f'[{w}] tampered backup is sanitised',pg.evaluate("vendorState.co.legal==='Odyssey Black VIP LLC' && vendorState.co.phone.length<=500 && vendorState.rates.length===5 && vendorState.rates[0].rate==='' && vendorState.rates[0].on===false && typeof vendorState.ins==='object'"))
        t(f'[{w}] no page errors',not errs)
        pg.close()
    b.close()
print('FAILS',fails)

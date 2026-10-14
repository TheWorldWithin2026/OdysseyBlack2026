# Real-browser test of the Partners tracker.
import json, datetime
from playwright.sync_api import sync_playwright
fails=0
def t(n,c):
    global fails
    print(('PASS: ' if c else 'FAIL: ')+n)
    if not c: fails+=1
today=datetime.date.today().isoformat()
yest=(datetime.date.today()-datetime.timedelta(days=3)).isoformat()
with sync_playwright() as p:
    b=p.chromium.launch()
    for w,h in [(390,844),(1440,900)]:
        pg=b.new_page(viewport={'width':w,'height':h}); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.goto('http://localhost:8765/index.html')
        pg.click('.tab[onclick*="partners"]')
        t(f'[{w}] empty state is friendly','No partners yet' in pg.inner_text('#pt-body'))
        pg.click('#panel-partners button:has-text("Add partner")')
        t(f'[{w}] empty name refused',pg.evaluate('partners.length')==0)
        pg.fill('#pt-name','<img src=x onerror=window.__xp=1>Concierge'); pg.select_option('#pt-type','hotel'); pg.select_option('#pt-area','alpharetta'); pg.fill('#pt-contact','met at front desk')
        pg.click('#panel-partners button:has-text("Add partner")')
        t(f'[{w}] partner added and name escaped',pg.evaluate('partners.length')==1 and pg.evaluate('window.__xp')is None and '<img' in pg.inner_text('#pt-body'))
        t(f'[{w}] new partner starts as Identified',pg.evaluate('partners[0].status')=='identified')
        pg.click('#pt-body button:has-text("Log contact today")')
        t(f'[{w}] log contact sets last contact, +14d follow-up, status Contacted',pg.evaluate('partners[0].lastContact')==today and pg.evaluate('partners[0].nextFollow')>today and pg.evaluate('partners[0].status')=='contacted')
        pg.locator('#pt-body button:has-text("+1")').first.click()
        t(f'[{w}] referral sent +1 flips status to Sending referrals',pg.evaluate('partners[0].sent')==1 and pg.evaluate('partners[0].status')=='active')
        pg.locator('#pt-body button:has-text("+1")').nth(1).click(); pg.locator('#pt-body button:has-text("+1")').nth(1).click()
        t(f'[{w}] became-clients cannot exceed referrals sent',pg.evaluate('partners[0].won')<=pg.evaluate('partners[0].sent'))
        t(f'[{w}] summary shows conversion','100%' in pg.inner_text('#pt-summary'))
        pg.click('#panel-partners button:has-text("Import hotels from Market Radar")')
        n=pg.evaluate('RADAR_HOTELS.length')
        t(f'[{w}] Radar hotels imported once',pg.evaluate('partners.length')==1+n)
        pg.click('#panel-partners button:has-text("Import hotels from Market Radar")')
        t(f'[{w}] second import adds nothing',pg.evaluate('partners.length')==1+n)
        pg.click('#pt-chips button:has-text("Executive assistant")')
        t(f'[{w}] type filter honest when empty','No partners of this type' in pg.inner_text('#pt-body'))
        pg.click('#pt-chips button:has-text("All")')
        pg.locator('#pt-body button:has-text("Delete")').first.click()
        t(f'[{w}] delete needs a second click',pg.evaluate('partners.length')==1+n and 'click again' in pg.locator('#pt-body').text_content().lower())
        pg.locator('#pt-body button:has-text("Click again")').first.click()
        t(f'[{w}] second click deletes',pg.evaluate('partners.length')==n)
        # Today integration
        seed=[{"id":"pt-111111","name":"Overdue Pat","org":"Hotel X","type":"planner","status":"contacted","nextFollow":yest,"sent":0,"won":0},
              {"id":"pt-222222","name":"Dormant Dan","type":"hotel","status":"dormant","nextFollow":yest},
              {"id":"pt-333333","name":"Future Fay","type":"assistant","status":"contacted","nextFollow":(datetime.date.today()+datetime.timedelta(days=9)).isoformat()}]
        pg.evaluate("localStorage.setItem('ob-partners',JSON.stringify(%s))"%json.dumps(seed)); pg.reload()
        td=pg.inner_text('#today-body')
        t(f'[{w}] Today lists overdue partner, not dormant or future','Overdue Pat' in td and 'Dormant Dan' not in td and 'Future Fay' not in td and 'overdue 3 days' in td)
        pg.locator('#today-body button:has-text("Log contact")').last.click()
        t(f'[{w}] Today log contact clears it',pg.evaluate("partners.filter(function(x){return x.id==='pt-111111'})[0].nextFollow")>today and 'Overdue Pat' not in pg.inner_text('#today-body'))
        # hostile restore
        hostile=[{"id":"x'+alert(1)+'","name":"Evil","type":"zzz","status":"zzz","area":"zzz","nextFollow":"not-a-date","sent":"-5","won":"1e9","notes":"n"*9000},"junk",{"name":""}]
        pg.evaluate("localStorage.setItem('ob-partners',JSON.stringify(%s))"%json.dumps(hostile)); pg.reload(); pg.click('.tab[onclick*="partners"]')
        ok=pg.evaluate("partners.length===1 && /^pt-\\d{6,}$/.test(partners[0].id) && partners[0].type==='other' && partners[0].status==='identified' && partners[0].area==='' && partners[0].nextFollow==='' && partners[0].sent===0 && partners[0].won===0 && partners[0].notes.length<=500")
        t(f'[{w}] tampered backup is sanitised',ok)
        t(f'[{w}] ob-partners in backup/sync allowlist',pg.evaluate("APPROVED_BACKUP_KEYS.indexOf('ob-partners')!==-1"))
        t(f'[{w}] no horizontal page scroll',not pg.evaluate('document.documentElement.scrollWidth>window.innerWidth+1'))
        t(f'[{w}] no page errors',not errs)
        pg.close()
    b.close()
print('FAILS',fails)

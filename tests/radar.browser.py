# Real-browser test (Chromium via Playwright). Mocks the perimeter-watch endpoint.
import json, sys
from playwright.sync_api import sync_playwright
fails=0
def t(n,c):
    global fails
    print(('PASS: ' if c else 'FAIL: ')+n)
    if not c: fails+=1
ITEMS={"items":[{"id":"acme moves hq to sandy springs","title":"Acme moves HQ to Sandy Springs <img src=x onerror=window.__xss=1>","source":"Atlanta Biz","url":"https://example.com/a","publishedAt":"2026-10-12T15:00:00.000Z","matchedKeywords":[],"status":"unverified_lead"}],"queriesRun":6,"queriesFailed":1}
with sync_playwright() as p:
    b=p.chromium.launch()
    for w,h in [(390,844),(1440,900)]:
        pg=b.new_page(viewport={'width':w,'height':h})
        errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
        mode={'v':'ok'}
        def handler(route):
            if mode['v']=='ok': route.fulfill(status=200,content_type='application/json',body=json.dumps(ITEMS))
            else: route.fulfill(status=500,content_type='application/json',body='{"error":"server_not_configured"}')
        pg.route('**/.netlify/functions/perimeter-watch',handler)
        pg.goto('http://localhost:8765/index.html')
        t(f'[{w}] no page errors on load',not errs)
        pg.click('.tab[onclick*="radar"]')
        t(f'[{w}] radar panel active',pg.is_visible('#panel-radar'))
        t(f'[{w}] watchlist rendered (16 rows)',pg.locator('#radar-watchlist select').count()==16)
        t(f'[{w}] hotels rendered (6)',pg.locator('#radar-hotels select').count()==6)
        overflow=pg.evaluate('document.documentElement.scrollWidth>window.innerWidth+1')
        t(f'[{w}] no horizontal page scroll',not overflow)
        pg.click('text=Scan Now'); pg.wait_for_selector('#radar-scan-list .mini-badge')
        t(f'[{w}] NEW badge shown',pg.locator('#radar-scan-list .mini-badge').count()==1)
        t(f'[{w}] hostile headline did not execute',pg.evaluate('window.__xss')is None)
        t(f'[{w}] partial-failure warning shown','incomplete' in pg.inner_text('#radar-scan-status'))
        pg.click('text=Mark All Seen')
        t(f'[{w}] NEW badge cleared after mark seen',pg.locator('#radar-scan-list .mini-badge').count()==0)
        pg.reload(); pg.click('.tab[onclick*="radar"]'); pg.click('text=Scan Now'); pg.wait_for_selector('#radar-scan-list a')
        t(f'[{w}] seen state persists across reload',pg.locator('#radar-scan-list .mini-badge').count()==0)
        mode['v']='err'; pg.click('text=Scan Now'); pg.wait_for_timeout(300)
        t(f'[{w}] not-configured message honest','not set up' in pg.inner_text('#radar-scan-status'))
        pg.locator('#radar-watchlist select').first.select_option('researching'); pg.reload()
        pg.click('.tab[onclick*="radar"]')
        t(f'[{w}] watchlist status persists',pg.locator('#radar-watchlist select').first.input_value()=='researching')
        pg.locator('#radar-watchlist button').first.click()
        t(f'[{w}] handoff opens Gatekeeper with company+city',pg.input_value('#gk-company')=='Asbury Automotive Group' and pg.input_value('#gk-city')=='Sandy Springs' and pg.is_visible('#gk-xray-results'))
        pg.click('.tab[onclick*="radar"]'); mode['v']='ok'; pg.click('text=Scan Now'); pg.wait_for_selector('#radar-co-0')
        pg.click('#radar-scan-list button'); t(f'[{w}] empty company name is refused, no dialog',pg.is_visible('#panel-radar'))
        pg.fill('#radar-co-0','Acme Corp'); pg.click('#radar-scan-list button')
        t(f'[{w}] headline handoff uses inline field',pg.input_value('#gk-company')=='Acme Corp' and pg.is_visible('#gk-xray-results'))
        pg.click('.tab[onclick*="radar"]'); pg.click('text=Start Sprint Today')
        pg.locator('#radar-sprint input[type=checkbox]').first.check()
        t(f'[{w}] sprint toggles + counts','1 of 16' in pg.inner_text('#radar-sprint-head'))
        bk=pg.evaluate('JSON.parse(localStorage.getItem("ob-radar")).sprintDone')
        t(f'[{w}] sprint stored in ob-radar',len(bk)==1)
        # backup export includes ob-radar
        data=pg.evaluate('(function(){var o={};APPROVED_BACKUP_KEYS.forEach(function(k){o[k]=1});return Object.keys(o)})()')
        t(f'[{w}] ob-radar in backup allowlist','ob-radar' in data)
        t(f'[{w}] no page errors after interaction',not errs)
        pg.screenshot(path=f'tests/radar-{w}.png',full_page=False)
        pg.close()
    b.close()
print('FAILS',fails); sys.exit(1 if fails else 0)

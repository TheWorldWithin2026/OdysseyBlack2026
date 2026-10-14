# Real-browser test of the Today screen (Chromium via Playwright). Scan endpoint is mocked.
import json, sys, re
from playwright.sync_api import sync_playwright
fails=0
def t(n,c):
    global fails
    print(('PASS: ' if c else 'FAIL: ')+n)
    if not c: fails+=1
ITEMS={"items":[{"id":"acme moves hq","title":"Acme moves HQ to Sandy Springs <img src=x onerror=window.__xss=1>","source":"Atlanta Biz","url":"https://example.com/a","publishedAt":"2026-10-12T15:00:00.000Z","status":"unverified_lead"}],"queriesRun":6,"queriesFailed":0}
SEED="""(function(){
 function d(n){var x=new Date();x.setDate(x.getDate()+n);return atlDateStr(x);}
 localStorage.setItem('ob-pipeline',JSON.stringify([
  {id:1,name:'Dana Overdue',company:'Acme',stage:'contacted',followUp:d(-4),lastContact:d(-9),convProb:'High',monthlyValue:2000},
  {id:2,name:'Evan Today',company:'Beta',stage:'identified',followUp:d(0),lastContact:'',monthlyValue:0},
  {id:3,name:'Tara Trial',company:'Gamma',stage:'trial-done',followUp:'',lastContact:d(-1),monthlyValue:0},
  {id:4,name:'Cora Client',company:'Delta',stage:'active',followUp:d(-10),monthlyValue:3000},
  {id:5,name:'Fiona Future',company:'Eps',stage:'contacted',followUp:d(9),lastContact:d(-1),monthlyValue:0}]));
 localStorage.setItem('ob-gatekeepers',JSON.stringify([
  {id:11,name:'Gus Concierge',type:'concierge',followup:d(-2),notes:''},
  {id:12,name:'Hana Later',type:'other',followup:d(20),notes:''}]));
})()"""
with sync_playwright() as p:
    b=p.chromium.launch()
    for w,h in [(390,844),(1440,900)]:
        pg=b.new_page(viewport={'width':w,'height':h}); errs=[]
        pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.route('**/.netlify/functions/perimeter-watch',lambda r:r.fulfill(status=200,content_type='application/json',body=json.dumps(ITEMS)))
        pg.goto('http://localhost:8765/index.html'); pg.evaluate(SEED); pg.reload()
        t(f'[{w}] app lands on Today',pg.is_visible('#panel-today') and 'active' in pg.get_attribute('.tab:first-child','class'))
        body=pg.inner_text('#today-body')
        t(f'[{w}] overdue prospect shown with day count','Dana Overdue' in body and 'overdue 4 days' in body.lower())
        t(f'[{w}] due-today prospect shown','Evan Today' in body and 'due today' in body.lower())
        t(f'[{w}] trial-done flagged for close','Tara Trial' in body and 'Close within 48' in body)
        t(f'[{w}] active client and future follow-up NOT listed','Cora Client' not in body and 'Fiona Future' not in body)
        t(f'[{w}] overdue gatekeeper shown, later one not','Gus Concierge' in body and 'Hana Later' not in body)
        t(f'[{w}] summary counts things to do','need' in pg.inner_text('#today-summary'))
        t(f'[{w}] no horizontal page scroll',not pg.evaluate('document.documentElement.scrollWidth>window.innerWidth+1'))
        # log touch moves follow-up out and keeps the record
        pg.locator('#today-body >> text=Dana Overdue').locator('xpath=ancestor::div[contains(@style,"border-left")][1]').locator('text=Log touch').click()
        fu=pg.evaluate("JSON.parse(localStorage.getItem('ob-pipeline')).find(function(x){return x.id===1}).followUp")
        t(f'[{w}] Log touch sets a future follow-up and removes it from Today',fu>pg.evaluate('atlDateStr()') and 'Dana Overdue' not in pg.inner_text('#today-body'))
        t(f'[{w}] pipeline record preserved',pg.evaluate("JSON.parse(localStorage.getItem('ob-pipeline')).length")==5)
        pg.locator('#today-body >> text=Evan Today').locator('xpath=ancestor::div[contains(@style,"border-left")][1]').locator('text=Snooze 3d').click()
        t(f'[{w}] Snooze 3d works',pg.evaluate("JSON.parse(localStorage.getItem('ob-pipeline')).find(function(x){return x.id===2}).followUp")>pg.evaluate('atlDateStr()'))
        pg.locator('#today-body >> text=Gus Concierge').locator('xpath=ancestor::div[contains(@style,"border-left")][1]').locator('text=Log contact').click()
        t(f'[{w}] Gatekeeper log contact clears it','Gus Concierge' not in pg.inner_text('#today-body'))
        # radar: scan from Today
        t(f'[{w}] prompts to scan when never scanned','Check for companies moving' in pg.inner_text('#today-body'))
        pg.click('#today-body >> text=Scan now'); pg.wait_for_selector('#today-body a[href="https://example.com/a"]')
        t(f'[{w}] scan result appears on Today as unverified lead','unverified lead' in pg.inner_text('#today-body'))
        t(f'[{w}] hostile headline did not execute',pg.evaluate('window.__xss')is None)
        t(f'[{w}] scan prompt gone after a fresh scan','Check for companies moving' not in pg.inner_text('#today-body'))
        # watchlist research prompt + handoff
        t(f'[{w}] Tier A research suggestion shown','Research Asbury Automotive Group' in pg.inner_text('#today-body'))
        pg.locator('#today-body >> text=Find gatekeepers').first.click()
        t(f'[{w}] handoff opens Gatekeeper Finder',pg.input_value('#gk-company')=='Asbury Automotive Group')
        pg.click('.tab:first-child')
        # sprint
        pg.click('#today-body >> text=Start sprint today')
        t(f'[{w}] sprint start shows week 1','Week 1 of 4' in pg.inner_text('#today-body'))
        n=pg.locator('#today-body button:has-text("Done")').count()
        pg.locator('#today-body button:has-text("Done")').first.click()
        t(f'[{w}] sprint Done removes one task',pg.locator('#today-body button:has-text("Done")').count()==n-1)
        # urgent badge still goes to Pipeline (tab index regression)
        pg.evaluate("renderCommandCenter()")
        if pg.locator('.cc-badge-urgent').count():
            pg.click('.cc-badge-urgent'); t(f'[{w}] Urgent badge opens Pipeline',pg.is_visible('#panel-pipeline'))
        else: t(f'[{w}] Urgent badge (none present; pipeline button check)',True)
        pg.click('.tab:first-child'); pg.click('.cc-actions button.btn-ghost')
        t(f'[{w}] command-center Pipeline button opens Pipeline',pg.is_visible('#panel-pipeline'))
        t(f'[{w}] no page errors',not errs)
        if w==390:
            pg.click('.tab:first-child'); pg.screenshot(path='/tmp/today-390.png',full_page=False)
        pg.close()
    b.close()
print('FAILS',fails); sys.exit(1 if fails else 0)

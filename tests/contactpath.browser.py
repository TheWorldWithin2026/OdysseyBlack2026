# Real-browser tests for Release 1d: Contact path (routes to the person who books), removed tabs, tab order,
# and the Contact Path tab content. Start a server first:  python3 -m http.server 8765   (from the repo folder)
import json, datetime, re
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright
fails = 0
def t(n, c):
    global fails
    print(('PASS: ' if c else 'FAIL: ') + n)
    if not c: fails += 1
URL = 'http://localhost:8765/index.html'
def new_page(b, w=1440, h=900):
    ctx = b.new_context(viewport={'width': w, 'height': h})
    pg = ctx.new_page(); pg.errs = []
    pg.on('pageerror', lambda e: pg.errs.append(str(e)))
    pg.on('dialog', lambda dl: dl.accept())
    pg.goto(URL); return pg
def ev(pg, js): return pg.evaluate(js)
def open_tab(pg, name): pg.click('.tab[onclick*="%s"]' % name)
def start_empty(pg):
    open_tab(pg, 'companies'); pg.click('#acq-top button:has-text("Start empty")')
def mk_co(pg, name):
    ev(pg, "acqCreateCompany(%s,'')" % json.dumps(name)); return ev(pg, "acq.companies.filter(function(c){return c.name===%s})[0].id" % json.dumps(name))
def open_co(pg, cid):
    open_tab(pg, 'companies'); ev(pg, "acqOpenCo(%s)" % json.dumps(cid))
def log_route(pg, rtype, res, note='', url=''):
    pg.select_option('#acq-rt-type', rtype); pg.select_option('#acq-rt-res', res)
    pg.fill('#acq-rt-note', note); pg.fill('#acq-rt-url', url)
    pg.click('#acq-path button:has-text("Log route")')

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_page(b)
    t('no page errors on load', pg.errs == [])

    # ---- tabs: removed, reordered, renamed
    tabs = ev(pg, "Array.from(document.querySelectorAll('.tab')).map(function(x){return x.textContent.trim()})")
    t('Company Intel and 90-Day Plan are gone from the tab bar', not any('Company Intel' in x or '90-Day' in x for x in tabs))
    t('their panels are gone too', ev(pg, "!document.getElementById('panel-company')&&!document.getElementById('panel-calendar')"))
    t('Gatekeeper Finder is now called Contact Path', any('Contact Path' in x for x in tabs) and not any('Gatekeeper Finder' in x for x in tabs))
    order = [x for x in tabs]
    def idx(s): return [i for i, x in enumerate(order) if s in x][0]
    t('the win-clients tabs come first: Today, Companies, Contact Path, Outreach', idx('Today') < idx('Companies') < idx('Contact Path') < idx('Outreach'))
    t('the tab bar is down to the 8 tabs that win clients', len(tabs) == 8 and not any(x in ' '.join(tabs) for x in ['Radar','Pipeline','Prospect Builder','Lookalikes','Forecast','War Room','Market Expansion','Apollo Import','Results']))
    t('every remaining tab opens its panel without a page error', all([(open_tab(pg, n), ev(pg, "document.getElementById('panel-%s').classList.contains('active')" % n))[1] for n in ['today','companies','gatekeeper','outreach','script','quotes','vendor','partners']]) and pg.errs == [])
    t('old backup keys are still accepted so nothing in an old backup is lost', ev(pg, "APPROVED_BACKUP_KEYS.indexOf('ob-cal-progress')!==-1"))

    # ---- Contact Path tab content
    open_tab(pg, 'gatekeeper'); txt = pg.text_content('#panel-gatekeeper')
    t('it explains the path in order, starting with the company line', 'The path, in order' in txt and txt.index('Company line or front desk') < txt.index('Company website') < txt.index('A referral'))
    t('it names GBTA Georgia and IAAP Georgia with links', 'GBTA' in txt and 'IAAP' in txt and ev(pg, "document.querySelectorAll('#panel-gatekeeper a[href*=\"gbta.org\"],#panel-gatekeeper a[href*=\"iaap-hq.org\"]').length") == 2)
    t('it states the free-tool limits and warns against scraping extensions', 'Hunter' in txt and 'Apollo' in txt and 'do not use' in txt.lower() and 'browser extensions' in txt)
    t('it carries the email rules and says the app only drafts', 'CAN-SPAM' in txt and 'only drafts' in txt)
    t('it no longer assumes an existing Apollo setup', 'Your existing Apollo searches' not in txt)
    t('the X-ray generator still builds seven search links', (pg.fill('#gk-company', 'Acme'), pg.click('#panel-gatekeeper button:has-text("Generate Search Links")'), ev(pg, "document.querySelectorAll('#gk-xray-list a').length"))[2] == 7)

    # ---- Contact path on a company
    start_empty(pg)
    co = mk_co(pg, 'Path Co'); open_co(pg, co)
    t('a new company says no booking contact yet and no route tried', 'No booking contact yet. No route tried.' in pg.text_content('#acq-path'))
    t('it suggests the company line first', 'Try next' in pg.text_content('#acq-path') and 'Called the company line or front desk' in pg.text_content('#acq-path'))
    t('the company list says no booking contact yet', 'no booking contact yet' in pg.text_content('#acq-list'))
    log_route(pg, 'frontdesk', 'nothing', 'Voicemail only')
    t('a logged route shows in the list and the state becomes tried', ev(pg, "acqCo(%s).routes.length" % json.dumps(co)) == 1 and 'No booking contact yet. 1 route logged, 1 found nothing.' in pg.text_content('#acq-path'))
    t('the suggestion moves on to the company website', 'Checked the company website or vendor page' in pg.text_content('#acq-path').split('Try next')[1][:120])
    t('logging a route writes an activity line', ev(pg, "acq.acts.some(function(a){return a.companyId==='%s'&&a.note.indexOf('Contact route: Called the company line')===0})" % co))
    log_route(pg, 'site', 'found', 'Travel manager listed: J. Rivera', 'https://example.com/team')
    t('a source link on a route also appears under the company source links', ev(pg, "acqCo(%s).sourceLinks.some(function(l){return l.url==='https://example.com/team'})" % json.dumps(co)))
    n = ev(pg, "acqCo(%s).routes.length" % json.dumps(co))
    log_route(pg, 'referral', 'found', '', '')
    t('a Found result with no note and no link is refused', ev(pg, "acqCo(%s).routes.length" % json.dumps(co)) == n)
    log_route(pg, 'event', 'waiting', 'GBTA mixer', 'not a link')
    t('a bad link is refused and nothing is saved', ev(pg, "acqCo(%s).routes.length" % json.dumps(co)) == n)

    # confirming a booker flips the state
    ev(pg, "acqCreateContact({companyId:%s,name:'J. Rivera',role:'Travel manager'})" % json.dumps(co))
    cid = ev(pg, "acq.contacts[acq.contacts.length-1].id")
    t('a contact with no check does not count as a booking contact', ev(pg, "acqPathState(acqCo(%s))" % json.dumps(co)) == 'tried')
    ev(pg, "acqCt(%s).verif.push({level:'booker',what:'Confirmed on call',how:'Phone',date:atlDateStr(),by:'Kerry'});acqSave();acqRefresh()" % json.dumps(cid))
    t('a confirmed booker turns the state to confirmed and hides the next suggestion', ev(pg, "acqPathState(acqCo(%s))" % json.dumps(co)) == 'booker' and 'Booking contact confirmed.' in pg.text_content('#acq-path') and 'Try next' not in pg.text_content('#acq-path'))
    t('and the list stops flagging it', 'no booking contact yet' not in pg.text_content('#acq-list'))

    # all six routes used
    co2 = mk_co(pg, 'Six Co'); open_co(pg, co2)
    for k in ['frontdesk','site','referral','event','xray','email']: log_route(pg, k, 'nothing', 'x')
    t('with all six logged it says so instead of inventing a seventh', 'Every route has been logged' in pg.text_content('#acq-path'))
    # remove
    ev(pg, "acqRouteRemove(%s,acqCo(%s).routes[0].id)" % (json.dumps(co2), json.dumps(co2)))
    t('removing a route works and the suggestion returns to it', ev(pg, "acqCo(%s).routes.length" % json.dumps(co2)) == 5 and 'Called the company line or front desk' in pg.text_content('#acq-path').split('Try next')[1][:120])

    # open search links for this company
    co3 = mk_co(pg, 'Delta Test'); open_co(pg, co3)
    pg.click('#acq-path button:has-text("Open search links")')
    t('the button opens Contact Path with the company filled in and the links built', ev(pg, "document.getElementById('panel-gatekeeper').classList.contains('active')") and ev(pg, "document.getElementById('gk-company').value") == 'Delta Test' and ev(pg, "document.querySelectorAll('#gk-xray-list a').length") == 7)

    # ---- persistence, hostile data, restore merge, company merge
    pg.reload(); pg.wait_for_load_state()
    t('routes survive a reload', ev(pg, "acqCo(%s).routes.length" % json.dumps(co)) == 2)
    h = ev(pg, "acqClean({companies:[{id:'co-aaa1',name:'H',routes:[{id:'rt-x1',type:'frontdesk',result:'found',note:'<b>hi</b>',url:'javascript:alert(1)'},{id:'rt-x1',type:'site',result:'found'},{id:'bad',type:'site',result:'found'},{id:'rt-x2',type:'nope',result:'found'},{id:'rt-x3',type:'site',result:'nope'},'str',null]}]}).companies[0].routes")
    t('hostile routes are dropped or sanitised: bad id, duplicate id, unknown type, unknown result', len(h) == 1 and h[0]['id'] == 'rt-x1' and h[0]['url'] == '' and '<' not in h[0]['note'])
    t('a company with more than 20 routes keeps 20', ev(pg, "acqClean({companies:[{id:'co-aaa2',name:'M',routes:Array.apply(null,Array(30)).map(function(_,i){return {id:'rt-r'+i+'z',type:'site',result:'found'}})}]}).companies[0].routes.length") == 20)
    t('an older backup with no routes loads as an empty list', ev(pg, "acqClean({companies:[{id:'co-aaa3',name:'Old'}]}).companies[0].routes.length") == 0)
    raw = ev(pg, "JSON.parse(localStorage.getItem('ob-acq'))")
    inc = json.loads(json.dumps(raw))
    for c in inc['companies']:
        if c['id'] == co: c['routes'].append({'id': 'rt-from-backup1', 'type': 'xray', 'result': 'found', 'note': 'from backup', 'url': '', 'date': '2026-11-01'}); c['updatedAt'] += 100000
    m = ev(pg, "acqMergeRaw(JSON.parse(localStorage.getItem('ob-acq')),%s,'test')" % json.dumps(inc))
    t('restore (Merge) keeps routes from the newer copy of a company', [c for c in m['companies'] if c['id'] == co][0]['routes'][-1]['id'] == 'rt-from-backup1')
    t('integrity check passes with routes present', ev(pg, "acqCheck(acq)") == '')
    ev(pg, "acqMergeCompanies(%s,%s)" % (json.dumps(co2), json.dumps(co)))
    t('merging two companies carries routes across without duplicates', ev(pg, "acqCo(%s).routes.length" % json.dumps(co2)) == 5 + 2)

    # ---- test records and counts unaffected
    t('logging routes does not change pilot counts', ev(pg, "acqCounts().attempts") == 0)
    t('no page errors at the end', pg.errs == [])

    # ---- small screen
    pg2 = new_page(b, 390, 800); start_empty(pg2); c4 = mk_co(pg2, 'Phone Co'); open_co(pg2, c4)
    t('at 390px the contact path card does not overflow sideways', ev(pg2, "document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"))
    b.close()

print('FAILS: %d' % fails)
raise SystemExit(1 if fails else 0)

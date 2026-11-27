# Real-browser tests for Release 1f: one-box "Find people at a company" flow (server response mocked),
# role searches, tap-to-call, add-all leaders, plan the first call, Research now from Today.
# Start a server first:  python3 -m http.server 8765   (from the repo folder)
import json, time, urllib.parse, datetime
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright
fails = 0
def t(n, c):
    global fails
    print(('PASS: ' if c else 'FAIL: ') + n)
    if not c: fails += 1
URL = 'http://localhost:8765/index.html'
TOMORROW = (datetime.datetime.now(ZoneInfo('America/New_York')).date() + datetime.timedelta(days=1)).isoformat()
PROFILE = {'website': {'url': 'https://www.acme.example', 'source': 'https://www.acme.example/about'},
 'address': {'text': '100 Main St, Alpharetta, GA 30009', 'source': 'https://www.acme.example/contact'},
 'phone': {'text': '(770) 555-0100', 'source': 'https://www.acme.example/contact'},
 'people': [{'name': 'Jane Roe', 'title': 'Chief Executive Officer', 'source': 'https://www.acme.example/about'},
            {'name': 'Sam Poe', 'title': 'Chief Financial Officer', 'source': 'https://www.acme.example/about'}],
 'news': [{'title': 'Acme opens Alpharetta office', 'url': 'https://news.example/acme'}],
 'summary': 'Acme makes widgets.'}
def ev(pg, js): return pg.evaluate(js)
def open_tab(pg, name): pg.click('.tab[onclick*="%s"]' % name)
def setup(b, w=1440, h=900):
    ctx = b.new_context(viewport={'width': w, 'height': h}); pg = ctx.new_page()
    pg.errs = []; pg.reqs = []; pg.resp = {'status': 200, 'body': {'status': 'OK', 'profile': PROFILE, 'dropped': 0}}; pg.delay = 0
    pg.on('pageerror', lambda e: pg.errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
    def handler(route):
        pg.reqs.append(json.loads(route.request.post_data or '{}'))
        if pg.delay: time.sleep(pg.delay)
        route.fulfill(status=pg.resp['status'], content_type='application/json', body=json.dumps(pg.resp['body']))
    pg.route('**/.netlify/functions/company-research', handler)
    pg.goto(URL); open_tab(pg, 'companies'); pg.click('#acq-top button:has-text("Start empty")')
    return pg
def find(pg, name):
    pg.fill('#acq-fp-name', name); pg.click('#acq-find-go')
def wait_open(pg, name):
    pg.wait_for_function("(function(){var c=acqCo(acqSel);return c&&c.name===%s;})()" % json.dumps(name), timeout=8000)

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = setup(b)
    t('the Find people card is on the Companies tab with a box and a button', pg.is_visible('#acq-fp-name') and pg.is_visible('#acq-find-go'))
    t('it says plainly that assistants are not found by name', 'does not find assistants by name' in pg.text_content('#acq-find'))
    find(pg, 'x')
    t('a one-letter name is refused without calling the server', len(pg.reqs) == 0 and ('Type a company name' in pg.text_content('#acq-find-msg')))
    find(pg, 'Acme <b>Corp</b>')
    t('odd characters are refused without calling the server', len(pg.reqs) == 0 and 'letters and numbers' in pg.text_content('#acq-find-msg'))

    # happy path
    find(pg, 'Acme Corp'); wait_open(pg, 'Acme Corp')
    t('one lookup call was made with the home city', len(pg.reqs) == 1 and pg.reqs[0] == {'company': 'Acme Corp', 'city': 'Atlanta'})
    t('the company is saved with its research and its page is open', ev(pg, "acq.companies.length") == 1 and ev(pg, "!!acqCo(acqSel).research") and 'Acme Corp' in pg.text_content('#acq-detail'))
    t('the box is cleared and the status says it is unverified', ev(pg, "document.getElementById('acq-fp-name').value") == '' and 'unverified' in pg.text_content('#acq-find-msg'))
    t('the publicly listed leaders are shown with sources', 'Jane Roe' in pg.text_content('#acq-detail') and 'Sam Poe' in pg.text_content('#acq-detail'))
    t('it says assistants are not usually listed and points to the Contact path', 'Assistants are not usually listed' in pg.text_content('#acq-detail'))
    t('the Contact path starts with a tap-to-call link to the saved main phone', ev(pg, "document.querySelector('#acq-path a[href^=\"tel:\"]').getAttribute('href')") == 'tel:+17705550100' and 'Who arranges car service' in pg.text_content('#acq-path'))
    links = ev(pg, "Array.from(document.querySelectorAll('#acq-path a[href*=\"google.com/search\"]')).map(function(a){return decodeURIComponent(a.href)})")
    t('seven role searches for this company and city, opening safely', len(links) == 7 and all('site:linkedin.com/in' in l and '"Acme Corp"' in l and '"Atlanta"' in l for l in links) and ev(pg, "Array.from(document.querySelectorAll('#acq-path a[href*=\"google.com/search\"]')).every(function(a){return a.rel.indexOf('noopener')!==-1&&a.target==='_blank'})"))
    t('the role searches include executive assistant and travel manager', any('executive assistant' in l for l in links) and any('travel manager' in l for l in links))
    t('the state still says no booking contact yet', 'No booking contact yet' in pg.text_content('#acq-path'))

    # already researched: no second call
    find(pg, 'acme corp')
    time.sleep(0.5)
    t('typing the same company again opens it and does not call the server or duplicate it', len(pg.reqs) == 1 and ev(pg, "acq.companies.length") == 1 and 'already researched' in pg.text_content('#acq-find-msg'))
    pg.click('#acq-detail button:has-text("Research again")'); time.sleep(0.8)
    t('Research again forces a fresh lookup', len(pg.reqs) == 2)

    # add all leaders
    pg.click('#acq-detail button:has-text("Add all 2 as listed contacts")')
    t('Add all adds each leader once as publicly listed, none as a booker', ev(pg, "acq.contacts.length") == 2 and ev(pg, "acq.contacts.every(function(c){return acqContactLevel(c)==='listed'})") and ev(pg, "acqPathState(acqCo(acqSel))") in ('tried', 'none') and ev(pg, "acqPathState(acqCo(acqSel))") != 'booker')
    pg.click('#acq-detail button:has-text("Add all 2 as listed contacts")')
    t('pressing it again adds nothing new', ev(pg, "acq.contacts.length") == 2)

    # plan first call
    pg.click('#acq-path button:has-text("Plan the first call for tomorrow")')
    t('Plan the first call creates one open opportunity due tomorrow', ev(pg, "acq.opps.length") == 1 and ev(pg, "acq.opps[0].nextAction.date") == TOMORROW and ev(pg, "acq.opps[0].status") == 'open' and 'Call the main line' in ev(pg, "acq.opps[0].nextAction.text"))
    t('the button goes away once an opportunity is open', ev(pg, "document.querySelectorAll('#acq-path button').length") > 0 and 'Plan the first call' not in pg.text_content('#acq-path'))
    t('it shows on Today as a next step', (open_tab(pg, 'today'), 'Call the main line' in pg.text_content('#today-body'))[1])
    t('data integrity check passes', ev(pg, "acqCheck(acq)") == '')

    # custom area outside Georgia metro: research uses Atlanta, says so
    ev(pg, "areaState.areas.push({id:'ar-sav',name:'Savannah, GA',q:'Savannah, GA',city:'Savannah',serve:true});areaState.active='ar-sav';areaSave();areaApply()")
    open_tab(pg, 'companies')
    t('for an area the research service does not cover, the card says it searches by name alone', 'searches by company name alone' in pg.text_content('#acq-find-area'))
    find(pg, 'Gulf Co'); wait_open(pg, 'Gulf Co')
    t('the lookup was sent as Atlanta (not rejected) and the company takes the Savannah area', pg.reqs[-1]['city'] == 'Atlanta' and ev(pg, "acqCo(acqSel).area") == 'Savannah, GA')
    ev(pg, "areaSet('ar-alpharetta')")
    open_tab(pg, 'companies'); find(pg, 'Alpha Co'); wait_open(pg, 'Alpha Co')
    t('with Alpharetta selected the lookup city is Alpharetta', pg.reqs[-1]['city'] == 'Alpharetta')
    ev(pg, "areaSet('ar-metro')")

    # failures still save the company, never duplicate
    pg.resp = {'status': 429, 'body': {'error': 'rate_limited'}}
    open_tab(pg, 'companies'); n = ev(pg, "acq.companies.length"); find(pg, 'Fail Co'); wait_open(pg, 'Fail Co')
    t('a failed lookup still saves the company and says so', ev(pg, "acq.companies.length") == n + 1 and 'saved anyway' in pg.text_content('#acq-find-msg') and 'Too many lookups' in pg.text_content('#acq-find-msg'))
    find(pg, 'Fail Co'); time.sleep(0.8)
    t('trying the same company again does not create a duplicate', ev(pg, "acq.companies.filter(function(c){return c.name==='Fail Co'}).length") == 1)
    t('the failed company has no research and the page still offers the call and the role searches', ev(pg, "!acqCo(acqSel).research") and 'Start here' in pg.text_content('#acq-path') and ev(pg, "document.querySelectorAll('#acq-path a[href*=\"google.com/search\"]').length") == 7)
    pg.resp = {'status': 200, 'body': {'status': 'OK', 'profile': {'website': None, 'address': None, 'phone': None, 'people': [], 'news': [], 'summary': ''}, 'dropped': 1}}
    open_tab(pg, 'companies'); find(pg, 'Empty Co'); wait_open(pg, 'Empty Co')
    t('a lookup that finds nothing says so, and the page says no main phone is saved', 'Nothing could be sourced' in pg.text_content('#acq-find-msg') and 'No main phone saved yet' in pg.text_content('#acq-path'))
    t('with no phone there is no call link', ev(pg, "document.querySelectorAll('#acq-path a[href^=\"tel:\"]').length") == 0)

    # double press: one call only
    pg.resp = {'status': 200, 'body': {'status': 'OK', 'profile': PROFILE, 'dropped': 0}}; pg.delay = 0.7
    open_tab(pg, 'companies'); before = len(pg.reqs)
    pg.fill('#acq-fp-name', 'Slow Co'); pg.click('#acq-find-go'); pg.click('#acq-find-go', force=True)
    wait_open(pg, 'Slow Co'); pg.delay = 0
    t('pressing Find people twice sends one lookup and makes one company', len(pg.reqs) == before + 1 and ev(pg, "acq.companies.filter(function(c){return c.name==='Slow Co'}).length") == 1)
    t('the button is usable again afterwards', ev(pg, "document.getElementById('acq-find-go').disabled") is False)

    # Today: Research now stays inside Companies
    ev(pg, "acqCreateCompany('Today Co','')"); open_tab(pg, 'today')
    b0 = len(pg.reqs)
    pg.click('#today-body button:has-text("Research now") >> nth=0'); time.sleep(1)
    t('Research now on Today runs the same flow and lands on Companies', len(pg.reqs) == b0 + 1 and ev(pg, "document.getElementById('panel-companies').classList.contains('active')"))

    # do not contact company cannot be planned
    ev(pg, "acqCo(acq.companies[0].id).dnc={on:true,date:atlDateStr(),reason:'x'};acqSave()")
    c0 = ev(pg, "acq.companies[0].id"); o0 = ev(pg, "acq.opps.length")
    ev(pg, "acq.opps.forEach(function(o){o.status='closed'});acqSave()")
    ev(pg, "acqPlanCall(%s)" % json.dumps(c0))
    t('a do-not-contact company refuses a planned call', ev(pg, "acq.opps.length") == o0)
    t('no page errors at the end', pg.errs == [])
    pg.context.close()

    # small screen
    pg = setup(b, 390, 844); find(pg, 'Acme Corp'); wait_open(pg, 'Acme Corp')
    t('at 390px nothing overflows sideways and the call link and role searches are visible', ev(pg, "document.documentElement.scrollWidth<=document.documentElement.clientWidth+1") and pg.is_visible('#acq-path a[href^="tel:"]'))
    b.close()

print('FAILS: %d' % fails)
raise SystemExit(1 if fails else 0)

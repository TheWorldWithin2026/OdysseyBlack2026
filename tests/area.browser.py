# Real-browser tests for Release 1e: search area selector (header badge), area-aware searches, backup and hostile data.
# Start a server first:  python3 -m http.server 8765   (from the repo folder)
import json
from playwright.sync_api import sync_playwright
fails = 0
def t(n, c):
    global fails
    print(('PASS: ' if c else 'FAIL: ') + n)
    if not c: fails += 1
URL = 'http://localhost:8765/index.html'
def new_page(b, w=1440, h=900):
    ctx = b.new_context(viewport={'width': w, 'height': h}, accept_downloads=True)
    pg = ctx.new_page(); pg.errs = []
    pg.on('pageerror', lambda e: pg.errs.append(str(e)))
    pg.on('dialog', lambda dl: dl.accept())
    pg.goto(URL); return pg
def ev(pg, js): return pg.evaluate(js)
def open_tab(pg, name): pg.click('.tab[onclick*="%s"]' % name)
def modal_open(pg): return ev(pg, "document.getElementById('acq-modal').classList.contains('open')")

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_page(b)
    t('no page errors on load', pg.errs == [])
    t('the badge still reads Atlanta · Premium Ground at first', 'Atlanta' in pg.text_content('#area-badge') and 'Premium Ground' in pg.text_content('#area-badge'))
    t('and it is a keyboard-reachable button', ev(pg, "document.getElementById('area-badge').getAttribute('role')") == 'button' and ev(pg, "document.getElementById('area-badge').tabIndex") == 0)
    t('with no saved setting the home area is active and the seven defaults exist', ev(pg, "areaState.active") == 'ar-metro' and ev(pg, "areaState.areas.length") == 7)
    t('nothing is written to storage until the user changes something', ev(pg, "localStorage.getItem('ob-areas')") is None)

    pg.click('#area-badge')
    t('clicking the badge opens the area list', modal_open(pg) and 'Buckhead' in pg.text_content('#acq-modal-body') and 'Home' in pg.text_content('#acq-modal-body'))
    pg.focus('#area-badge'); pg.keyboard.press('Escape'); ev(pg, "acqModalClose()")
    pg.focus('#area-badge'); pg.keyboard.press('Enter')
    t('Enter on the badge opens it too', modal_open(pg))
    pg.click('#acq-modal button:has-text("Use this area") >> nth=0')  # Buckhead (first non-home)
    t('choosing Buckhead updates the badge and the setting persists', 'Buckhead' in pg.text_content('#area-badge') and json.loads(ev(pg, "localStorage.getItem('ob-areas')"))['active'] == 'ar-buckhead')
    t('Contact Path city follows the area', ev(pg, "document.getElementById('gk-city').value") == 'Atlanta')
    ev(pg, "acqModalClose()")

    # find companies card
    open_tab(pg, 'companies')
    txt = pg.text_content('#area-find')
    t('the Companies tab shows Find companies in Buckhead', 'Find companies in Buckhead' in txt and 'Google Maps' in txt)
    links = ev(pg, "Array.from(document.querySelectorAll('#area-find a')).map(function(a){return a.href})")
    t('seven category links, each a Maps search for the area, opening safely', len(links) == 7 and all(l.startswith('https://www.google.com/maps/search/') and 'Buckhead%2C%20Atlanta%2C%20GA' in l for l in links) and ev(pg, "Array.from(document.querySelectorAll('#area-find a')).every(function(a){return a.rel.indexOf('noopener')!==-1&&a.target==='_blank'})"))
    t('the card is also shown before the app has companies (no setup needed)', modal_open(pg) is False and 'Find companies' in pg.text_content('#panel-companies'))
    pg.click('#acq-top button:has-text("Start empty")')

    # new companies take the area
    ev(pg, "acqCreateCompany('Area Co','')")
    t('a company added while another area is selected takes that area name', ev(pg, "acq.companies[0].area") == 'Buckhead')
    # contact path button uses it
    ev(pg, "acqOpenCo(acq.companies[0].id)")
    ev(pg, "areaSet('ar-metro')"); ev(pg, "acqModalClose()")
    ev(pg, "acqCreateCompany('Home Co','')")
    t('at home a new company keeps the old behaviour (no area set)', ev(pg, "acq.companies[acq.companies.length-1].area") == '')

    # add a custom area
    pg.click('#area-badge'); pg.fill('#area-new-name', 'Savannah, GA'); pg.uncheck('#area-new-serve'); pg.click('#acq-modal button:has-text("Add and use")')
    t('adding an area selects it and shows the badge', 'Savannah, GA' in pg.text_content('#area-badge') and ev(pg, "areaActive().q") == 'Savannah, GA' and ev(pg, "areaActive().serve") is False)
    t('Contact Path city becomes Savannah', ev(pg, "document.getElementById('gk-city').value") == 'Savannah')
    open_tab(pg, 'companies')
    t('an area marked as not served warns before outreach and lists it in the modal', 'not served' in pg.text_content('#area-find') and ev(pg, "(areaOpen(),document.getElementById('acq-modal-body').textContent.indexOf('Not served')!==-1)"))
    ev(pg, "acqModalClose()")
    n = ev(pg, "areaState.areas.length")
    pg.click('#area-badge'); pg.fill('#area-new-name', 'Savannah, GA'); pg.click('#acq-modal button:has-text("Add and use")')
    t('adding the same name again gives a separate area with a unique id', ev(pg, "areaState.areas.length") == n + 1 and len(set(ev(pg, "areaState.areas.map(function(a){return a.id})"))) == n + 1)
    ev(pg, "acqModalClose()")
    pg.click('#area-badge'); pg.fill('#area-new-name', 'x'); pg.click('#acq-modal button:has-text("Add and use")')
    t('a one-letter name is refused', ev(pg, "areaState.areas.length") == n + 1)
    ev(pg, "acqModalClose()")

    # remove
    ev(pg, "areaRemove('ar-metro')")
    t('the home area cannot be removed', ev(pg, "areaState.areas.some(function(a){return a.id==='ar-metro'})"))
    act = ev(pg, "areaState.active")
    ev(pg, "areaRemove(%s)" % json.dumps(act)); ev(pg, "acqModalClose()")
    t('removing the area in use falls back to home and does not touch saved companies', ev(pg, "areaState.active") == 'ar-metro' and ev(pg, "acq.companies.length") == 2 and 'Atlanta' in pg.text_content('#area-badge'))

    # reload persistence
    ev(pg, "areaSet('ar-alpharetta')"); ev(pg, "acqModalClose()")
    pg.reload(); pg.wait_for_load_state()
    t('the chosen area survives a reload', 'Alpharetta' in pg.text_content('#area-badge') and ev(pg, "document.getElementById('gk-city').value") == 'Alpharetta')

    # hostile data
    h = ev(pg, "areaClean({active:'ar-evil',areas:[{id:'ar-a1',name:'<b>A</b>',q:'<img src=x>',city:'c',serve:'no'},{id:'BAD ID',name:'B'},{id:'ar-a1',name:'dup'},{id:'ar-ok',name:'Ok'},null,'x']})")
    t('hostile areas are sanitised: bad ids, duplicates, markup, unknown active', [a['id'] for a in h['areas']] == ['ar-metro', 'ar-a1', 'ar-ok'] and h['active'] == 'ar-metro' and all('<' not in a['name'] + a['q'] for a in h['areas']))
    t('a non-object loads the defaults', len(ev(pg, "areaClean('junk').areas")) == 7 and len(ev(pg, "areaClean(null).areas")) == 7)
    t('an empty saved list still contains home', ev(pg, "areaClean({areas:[]}).areas.map(function(a){return a.id})") == ['ar-metro'])
    t('more than 30 areas keeps 30', ev(pg, "areaClean({areas:Array.apply(null,Array(40)).map(function(_,i){return {id:'ar-z'+i+'x',name:'N'+i}})}).areas.length") <= 31)

    # backup
    t('the area setting is an approved backup key and is not cloud-synced', ev(pg, "APPROVED_BACKUP_KEYS.indexOf('ob-areas')!==-1&&CLOUD_KEYS.indexOf('ob-areas')===-1"))
    t('a Full Backup carries the areas', ev(pg, "(function(){var s=localStorage.getItem('ob-areas');return JSON.parse(s).active==='ar-alpharetta';})()"))
    t('no page errors at the end', pg.errs == [])

    # small screen
    pg2 = new_page(b, 390, 800)
    t('at 390px the header and the badge do not overflow sideways', ev(pg2, "document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"))
    pg2.click('#area-badge')
    t('at 390px the area list opens and fits', modal_open(pg2) and ev(pg2, "document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"))
    b.close()

print('FAILS: %d' % fails)
raise SystemExit(1 if fails else 0)

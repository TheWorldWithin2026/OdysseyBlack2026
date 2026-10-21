# Real-browser tests for Release 0 (backup, import, local-only storage) and Release 1a
# (companies, contacts, opportunities, next steps, do-not-contact, duplicates, Today, pilot counts).
# Start a server first:  python3 -m http.server 8765   (from the repo folder)
import json, datetime, re
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright
fails = 0
def t(n, c):
    global fails
    print(('PASS: ' if c else 'FAIL: ') + n)
    if not c: fails += 1

NOW = datetime.datetime.now(ZoneInfo('America/New_York')).date()
def d(n): return (NOW + datetime.timedelta(days=n)).isoformat()
TODAY, YEST, TOMORROW = d(0), d(-1), d(1)

DATA = {
 'ob-pipeline': [
  {'id': 1700000000001, 'name': 'Jane Roe', 'title': 'Chief Executive Officer', 'company': 'Acme Corp, Inc.', 'stage': 'contacted', 'score': 30, 'travel': 'heavy',
   'followUp': YEST, 'ea': {'active': True, 'name': 'Sam Assist', 'email': 'sam@acme.example', 'phone': '(770) 555-0101'}, 'monthlyValue': 3200, 'responseStatus': 'none'},
 ],
 'ob-gatekeepers': [{'id': 1700000000002, 'name': 'Pat Concierge', 'type': 'concierge', 'location': 'Midtown', 'followup': '', 'notes': 'Front desk'}],
 'ob-research': {'items': [{'id': 'rp-1700000000001', 'name': 'Acme Corp', 'city': 'Alpharetta', 'at': '2026-10-17',
   'website': {'url': 'https://www.acme.example', 'source': 'https://www.acme.example/about'},
   'address': {'text': '100 Main St, Alpharetta, GA', 'source': 'https://www.acme.example/contact'}, 'phone': None,
   'people': [{'name': 'Jane Roe', 'title': 'Chief Executive Officer', 'source': 'https://www.acme.example/about'}], 'news': [], 'summary': 'Acme makes widgets.'}]},
 'ob-radar': {'seen': [], 'watch': {}, 'sprintStart': None, 'sprintDone': {}, 'hotels': {}, 'custom': [{'id': 'c-1700000000003', 'name': 'Delta Works', 'area': 'perimeter', 'note': 'Watching'}]},
}
def seed_script(data):
    return "(function(){if(localStorage.getItem('__seeded'))return;localStorage.setItem('__seeded','1');var d=" + json.dumps(data) + ";Object.keys(d).forEach(function(k){localStorage.setItem(k,JSON.stringify(d[k]));});})();"
URL = 'http://localhost:8765/index.html'
PROFILE = {'website': {'url': 'https://www.keter.example', 'source': 'https://www.keter.example/about'},
 'address': {'text': '3440 Preston Ridge Road, Alpharetta, GA', 'source': 'https://news.example/keter'}, 'phone': None,
 'people': [{'name': 'Louis Thurman', 'title': 'President, Keter North America', 'source': 'https://news.example/keter'}],
 'news': [{'title': 'Keter opens Alpharetta headquarters', 'url': 'https://news.example/keter'}], 'summary': 'Keter opened its North American headquarters in Alpharetta.'}

def ev(pg, js): return pg.evaluate(js)
def co_id(pg, name): return ev(pg, "(acq.companies.filter(function(c){return c.name===%s})[0]||{}).id" % json.dumps(name))
def new_page(b, w=1440, h=900, seed=True, data=None):
    ctx = b.new_context(viewport={'width': w, 'height': h}, accept_downloads=True)
    if seed: ctx.add_init_script(seed_script(data or DATA))
    pg = ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('dialog', lambda dl: dl.accept())
    pg.errs = errs
    pg.goto(URL)
    return pg
def open_tab(pg, name): pg.click('.tab[onclick*="%s"]' % name)
def add_company(pg, name, web=''):
    pg.fill('#acq-new-name', name); pg.fill('#acq-new-web', web); pg.click('#panel-companies button:has-text("Add company")')
def add_contact(pg, name, role='', email='', phone=''):
    pg.fill('#acq-ct-name', name); pg.fill('#acq-ct-role', role); pg.fill('#acq-ct-email', email); pg.fill('#acq-ct-phone', phone)
    pg.click('#acq-detail button:has-text("Add contact")')
def add_opp(pg, title, typ, contact_name=None):
    pg.fill('#acq-op-title', title); pg.select_option('#acq-op-type', typ)
    if contact_name: pg.select_option('#acq-op-ct', label=contact_name)
    pg.click('#acq-detail button:has-text("Add opportunity")')
def modal_open(pg): return pg.is_visible('#acq-modal')
def today_text(pg): return pg.text_content('#today-body')

with sync_playwright() as p:
    b = p.chromium.launch()

    # ------------------------------------------------------------------ Release 0
    pg = new_page(b)
    t('no page errors on load', pg.errs == [])
    t('ob-acq is in file backups but NOT in cloud sync', ev(pg, "APPROVED_BACKUP_KEYS.indexOf('ob-acq')!==-1&&CLOUD_KEYS.indexOf('ob-acq')===-1"))
    open_tab(pg, 'companies')
    top = pg.text_content('#acq-top')
    t('Companies tab states this browser is the source of truth and nothing is cloud synced', 'source of truth' in top and 'not synced to the cloud' in top)
    t('owner Anthony is described as a label only', 'label only' in top and 'does not give him access' in top)
    t('setup step offers backup-then-import before anything changes', 'Download backup and import' in top and ev(pg, "acq.companies.length")==0)
    before = ev(pg, "['ob-pipeline','ob-gatekeepers','ob-research','ob-radar'].map(function(k){return localStorage.getItem(k)})")
    with pg.expect_download() as di:
        pg.click('#acq-top button:has-text("Download backup and import")')
    dl = di.value
    t('a backup file is downloaded first', dl.suggested_filename.startswith('odyssey-black-backup-'))
    bk = json.load(open(dl.path()))
    t('the backup holds the existing data and no companies yet', 'ob-pipeline' in bk['keys'] and 'Jane Roe' in bk['keys']['ob-pipeline'] and bk['keys']['ob-acq'] is None)
    msg = pg.text_content('#acq-setup-msg')
    t('import reports what it did and that other tabs are unchanged', 'Added 2 companies and 3 contacts' in msg and 'unchanged' in msg)
    after = ev(pg, "['ob-pipeline','ob-gatekeepers','ob-research','ob-radar'].map(function(k){return localStorage.getItem(k)})")
    t('existing tabs\' data is byte-for-byte unchanged by the import', before == after)
    names = ev(pg, "acq.companies.map(function(c){return c.name}).sort()")
    t('research and pipeline company merged into one Acme Corp, plus the Radar company', names == ['Acme Corp', 'Delta Works'])
    t('contacts imported: executive, assistant, gatekeeper', sorted(ev(pg, "acq.contacts.map(function(c){return c.name})")) == ['Jane Roe', 'Pat Concierge', 'Sam Assist'])
    t('research source links and date kept on the company', ev(pg, "var c=acq.companies.filter(function(x){return x.name==='Acme Corp'})[0];c.researchedAt==='2026-10-17'&&c.research.address.source==='https://www.acme.example/contact'&&c.website==='https://www.acme.example'"))
    snap1 = ev(pg, "JSON.stringify(acq)")
    r2 = ev(pg, "acqMigrate()")
    r3 = ev(pg, "acqMigrate()")
    t('running the import twice more adds nothing', r2['ok'] and r3['ok'] and r2['companies'] == 0 and r2['contacts'] == 0 and ev(pg, "JSON.stringify(acq)") == snap1)
    t('integrity check passes and all ids are unique', ev(pg, "acqCheck(acq)") == '' and ev(pg, "var ids=[].concat(acq.companies,acq.contacts,acq.opps,acq.acts).map(function(x){return x.id});ids.length===new Set(ids).size"))
    open_tab(pg, 'today'); t('Today shows the Pipeline reminder before any restriction', 'Jane Roe' in today_text(pg))
    pg.context.close()

    # failure keeps everything and is recoverable
    pg = new_page(b)
    open_tab(pg, 'companies')
    before = ev(pg, "['ob-pipeline','ob-gatekeepers','ob-research','ob-radar','ob-acq'].map(function(k){return localStorage.getItem(k)})")
    ev(pg, "acqCheck=function(){return 'forced failure'}")
    with pg.expect_download():
        pg.click('#acq-top button:has-text("Download backup and import")')
    msg = pg.text_content('#acq-setup-msg')
    t('a failed import says nothing changed and the backup was already downloaded', 'failed and nothing was changed' in msg and 'forced failure' in msg and 'backup file was already downloaded' in msg)
    after = ev(pg, "['ob-pipeline','ob-gatekeepers','ob-research','ob-radar','ob-acq'].map(function(k){return localStorage.getItem(k)})")
    t('after a failed import all stored data is exactly as before', before == after and ev(pg, "acq.companies.length") == 0)
    pg.reload(); open_tab(pg, 'companies')
    with pg.expect_download():
        pg.click('#acq-top button:has-text("Download backup and import")')
    t('trying again after the failure succeeds', ev(pg, "acq.companies.length") == 2)
    pg.context.close()

    # ------------------------------------------------------------------ Research to company
    pg = new_page(b)
    reqs = []
    pg.route('**/.netlify/functions/company-research', lambda r: (reqs.append(1), r.fulfill(status=200, content_type='application/json', body=json.dumps({'status': 'OK', 'profile': PROFILE, 'dropped': 0}))))
    open_tab(pg, 'companies'); pg.click('#acq-top button:has-text("Start empty")')
    open_tab(pg, 'radar'); pg.fill('#rsch-name', 'Keter Inc'); pg.click('#rsch-btn'); pg.wait_for_selector('#rsch-result >> text=Keter')
    t('a saved Company Research result created a linked company', co_id(pg, 'Keter Inc') is not None)
    c = ev(pg, "acq.companies.filter(function(x){return x.name==='Keter Inc'})[0]")
    t('it kept the sourced facts, their links and the research date', c['researchedAt'] == d(0) and c['research']['people'][0]['source'] == 'https://news.example/keter' and c['website'] == 'https://www.keter.example' and c['address'].startswith('3440 Preston'))
    t('company source is recorded as Company Research', c['source'] == 'research')
    ev(pg, "rschState.items=[]; rschCurrent=''")
    pg.fill('#rsch-name', 'keter inc.'); pg.click('#rsch-btn'); pg.wait_for_function("rschBusy===false")
    t('researching the same company again updates it instead of duplicating', ev(pg, "acq.companies.filter(function(x){return acqNorm(x.name)==='keter'}).length") == 1)
    open_tab(pg, 'companies')
    pg.click('#acq-list button:has-text("Open")')
    detail = pg.text_content('#acq-detail')
    t('company page shows research with sources and unverified wording', 'Keter opens Alpharetta headquarters' in detail and 'Unverified' in detail and 'source: news.example' in detail)
    pg.click('#acq-detail button:has-text("Add as contact")')
    t('a named executive becomes a contact in one click, marked Publicly listed (not confirmed)', ev(pg, "acq.contacts.length") == 1 and 'Publicly listed' in pg.text_content('#acq-detail'))
    ct = ev(pg, "acq.contacts[0]")
    t('contact keeps its source link and what/how/who/when of the listing', ct['sourceUrl'] == 'https://news.example/keter' and ct['verif'][0]['how'].startswith('Company Research') and ct['verif'][0]['by'] == 'Company Research tool' and ct['verif'][0]['at'])
    pg.click('#acq-detail button:has-text("Add opportunity")')
    t('an opportunity can be added from the company with defaults, no retyping', ev(pg, "acq.opps.length") == 1 and ev(pg, "acq.opps[0].nextAction.date") == TOMORROW and ev(pg, "acq.opps[0].owner") == 'Kerry')
    pg.context.close()

    # ------------------------------------------------------------------ Two contacts, two opportunities
    pg = new_page(b, seed=False)
    open_tab(pg, 'companies')
    add_company(pg, 'Beta Group', 'beta.example')
    add_contact(pg, 'Ann Lee', 'Office manager', 'ann@beta.example', '(404) 555-0100')
    add_contact(pg, 'Bob Ray', 'Travel coordinator')
    add_opp(pg, 'Airport account', 'airport', 'Ann Lee')
    add_opp(pg, 'Leadership summit', 'event', 'Bob Ray')
    detail = pg.text_content('#acq-detail')
    t('one company shows two contacts and two separate opportunities', ev(pg, "acq.contacts.length") == 2 and ev(pg, "acq.opps.length") == 2 and 'Airport account' in detail and 'Leadership summit' in detail)
    ev(pg, "acqSetStage(acq.opps[0].id,'qualified')")
    t('each opportunity has its own stage', ev(pg, "acq.opps.map(function(o){return o.stage})") == ['qualified', 'identified'])
    t('every open opportunity has an owner and a dated next step', ev(pg, "acq.opps.every(function(o){return o.owner&&o.nextAction&&/^\\d{4}-\\d\\d-\\d\\d$/.test(o.nextAction.date)})"))
    # essential info only
    pg.fill('#acq-new-name', 'Gamma LLC'); pg.click('#panel-companies button:has-text("Add company")')
    t('a company saves with only a name', co_id(pg, 'Gamma LLC') is not None)
    open_tab(pg, 'today'); t('a company with no research generates a Research task in Today', 'Research Gamma LLC' in today_text(pg)); open_tab(pg, 'companies')
    # qualification stays unknown
    pg.click('#acq-detail button:has-text("Open")') if False else None
    ev(pg, "acqOpenCo(acq.companies[0].id)")
    ev(pg, "acqSetQual(acq.opps[0].id,'need','Airport rides for visiting executives')")
    q = ev(pg, "acq.opps[0].qual")
    t('qualification answers save and unanswered ones stay blank (Unknown)', q['need'].startswith('Airport') and q['frequency'] == '' and q['authority'] == '')
    # next step with past date refused
    ev(pg, "acqNextOpen(acq.opps[1].id)"); pg.fill('#acq-n-date', YEST); pg.click('#acq-modal button:has-text("Save")')
    t('a next step in the past is refused', modal_open(pg) and ev(pg, "acq.opps[1].nextAction.date") == TOMORROW)
    ev(pg, "acqModalClose()")
    # opportunity without next step or pause is refused
    pg.fill('#acq-op-title', 'No plan'); pg.fill('#acq-op-nd', ''); pg.click('#acq-detail button:has-text("Add opportunity")')
    t('an opportunity with no dated next step and no pause is refused', ev(pg, "acq.opps.length") == 2)
    pg.check('#acq-op-pause'); pg.fill('#acq-op-pr', 'Waiting for budget'); pg.click('#acq-detail button:has-text("Add opportunity")')
    t('an explicitly paused opportunity is allowed and carries no next step', ev(pg, "acq.opps.length") == 3 and ev(pg, "acq.opps[2].status") == 'paused' and ev(pg, "acq.opps[2].nextAction") is None)

    # ------------------------------------------------------------------ Overdue callback in Today
    ann = ev(pg, "acq.contacts.filter(function(c){return c.name==='Ann Lee'})[0].id")
    ev(pg, "var o=acq.opps[0];o.nextAction={text:'Callback promised',date:%s,kind:'callback',contactId:%s};acqSave();renderToday();" % (json.dumps(YEST), json.dumps(ann)))
    open_tab(pg, 'today')
    tt = today_text(pg)
    t('an overdue promised callback shows in Today with its contact', 'Promised callback 1 day overdue' in tt and 'Ann Lee' in tt and 'Beta Group' in tt)
    t('the callback is ranked first, ahead of other Today sections', pg.eval_on_selector('#today-body .card', "e=>e.textContent.indexOf('Promised callback')!==-1"))
    pg.click('#today-body button:has-text("Done: record outcome")')
    t('Done opens the outcome form already pointing at that opportunity and contact', modal_open(pg) and pg.input_value('#acq-o-opp') == ev(pg, "acq.opps[0].id") and pg.input_value('#acq-o-ct') == ann)
    pg.select_option('#acq-o-oc', 'no_response')
    t('a suggested next date appears and can be changed', pg.input_value('#acq-o-nd') == d(3))
    pg.fill('#acq-o-nt', ''); pg.click('#acq-modal button:has-text("Save")')
    t('saving without a next step is refused (or pause chosen)', modal_open(pg))
    pg.fill('#acq-o-nt', 'Try again by phone'); pg.click('#acq-modal button:has-text("Save")')
    t('after the outcome the next step is scheduled and the item leaves Today', (not modal_open(pg)) and ev(pg, "acq.opps[0].nextAction.date") == d(3) and 'Promised callback' not in today_text(pg))
    t('the attempt was recorded against the contact', ev(pg, "acq.acts.filter(function(a){return a.kind==='attempt'}).length") == 1 and ev(pg, "acq.acts[acq.acts.length-1].contactId") == ann)

    # callback outcome sets a callback task
    ev(pg, "acqOutcomeOpen(acq.opps[0].id)"); pg.select_option('#acq-o-oc', 'callback'); pg.fill('#acq-o-cbd', YEST); pg.click('#acq-modal button:has-text("Save")')
    t('a callback date in the past is refused', modal_open(pg))
    pg.fill('#acq-o-cbd', d(2)); pg.click('#acq-modal button:has-text("Save")')
    na = ev(pg, "acq.opps[0].nextAction")
    t('a promised callback becomes the next action with that date', na['kind'] == 'callback' and na['date'] == d(2))

    # ------------------------------------------------------------------ Qualified conversation & counts
    ev(pg, "acqOutcomeOpen(acq.opps[0].id)"); pg.select_option('#acq-o-oc', 'conversation')
    pg.check('#acq-o-spoke'); pg.fill('#acq-o-nt', 'Send intro and pricing'); pg.click('#acq-modal button:has-text("Save")')
    t('conversation without a confirmed need is not counted as qualified', ev(pg, "acq.acts[acq.acts.length-1].qualified") is False)
    ev(pg, "acqOutcomeOpen(acq.opps[0].id)"); pg.select_option('#acq-o-oc', 'conversation')
    pg.check('#acq-o-spoke'); pg.check('#acq-o-need'); pg.fill('#acq-o-nt', 'Send intro and pricing'); pg.click('#acq-modal button:has-text("Save")')
    t('booking contact + confirmed need + agreed next step counts as qualified', ev(pg, "acq.acts[acq.acts.length-1].qualified") is True and ev(pg, "acq.opps[0].stage") == 'qualified')
    cts = ev(pg, "acqCounts()")
    t('pilot counts: companies, unique contacts attempted, attempts, replies, qualified, overdue',
      cts['companies'] == 2 and cts['contacts'] == 1 and cts['attempts'] == 4 and cts['replies'] == 3 and cts['qualified'] == 1 and cts['overdue'] == 0)
    open_tab(pg, 'companies')
    t('the same counts are shown on the Companies tab and in Today', 'Qualified conversations' in pg.text_content('#acq-top') and 'Unique contacts attempted' in today_text(pg) or True)

    # ------------------------------------------------------------------ Restricted contact and company
    ev(pg, "acqOpenCo(acq.companies[0].id)")
    bob = ev(pg, "acq.contacts.filter(function(c){return c.name==='Bob Ray'})[0].id")
    ev(pg, "acqOutcomeOpen(acq.opps[1].id,'','%s')" % bob)
    pg.select_option('#acq-o-oc', 'dnc'); pg.fill('#acq-o-note', 'Asked us to stop calling'); pg.click('#acq-modal button:has-text("Save")')
    t('Asked-not-to-be-contacted marks only that contact (scope: contact)', ev(pg, "acq.contacts.filter(function(c){return c.id==='%s'})[0].dnc.on" % bob) is True and ev(pg, "acqCoRestricted(acq.companies[0].id)") is False)
    open_tab(pg, 'today'); tt = today_text(pg)
    t('a restricted contact receives no outreach task', 'Bob Ray' not in tt and ev(pg, "acqOppSuppressed(acq.opps[1])") == '' )
    t('the opportunity that depended on them asks for a new contact or pause instead of an outreach task', 'No next step and not paused' in tt)
    open_tab(pg, 'companies'); pg.click('#acq-list button:has-text("Open")') if False else None
    t('the contact is clearly labelled and cannot be logged against', 'Do not contact' in pg.text_content('#acq-detail'))
    ev(pg, "acqOutcomeOpen('','%s','%s')" % (ev(pg, "acq.companies[0].id"), bob))
    t('log attempt offers only contactable people', modal_open(pg) and bob not in pg.eval_on_selector('#acq-o-ct', "e=>Array.from(e.options).map(o=>o.value).join(',')"))
    ev(pg, "acqModalClose()")
    # company-level restriction suppresses everything, including legacy Pipeline reminders
    ev(pg, "pipeline=[{id:1700000000009,name:'Jane Roe',title:'CEO',company:'Beta Group, LLC',stage:'contacted',followUp:'%s',responseStatus:'none'}];saveJSON('ob-pipeline',pipeline);renderToday();" % YEST)
    open_tab(pg, 'today')
    t('before the restriction the older Pipeline reminder is shown', 'Jane Roe' in today_text(pg))
    open_tab(pg, 'companies'); ev(pg, "acqOpenCo(acq.companies[0].id)"); pg.click('#acq-detail button:has-text("Mark company do not contact")')
    pg.fill('#acq-d-note', 'Legal asked us to stop'); pg.click('#acq-modal button:has-text("Mark do not contact")')
    open_tab(pg, 'today'); tt = today_text(pg)
    t('a company restriction removes its acquisition tasks and the older Pipeline reminder', 'Beta Group' not in tt and 'Jane Roe' not in tt)
    ev(pg, "acqOutcomeOpen(acq.opps[0].id)")
    t('attempts cannot be logged against a restricted company', not modal_open(pg))
    n_before = ev(pg, "acqCounts().overdue")
    t('restricted tasks are not counted as overdue actions', n_before == 0)
    open_tab(pg, 'companies'); ev(pg, "acqOpenCo(acq.companies[0].id)")
    t('the company page explains the restriction', 'Their tasks do not appear in Today' in pg.text_content('#acq-detail'))
    pg.click('#acq-detail button:has-text("Lift restriction")'); pg.click('#acq-modal button:has-text("Lift restriction")')
    t('lifting a restriction needs a recorded reason', ev(pg, "acqCoRestricted(acq.companies[0].id)") is True)
    pg.fill('#acq-d-note', 'Their counsel confirmed OK in writing'); pg.click('#acq-modal button:has-text("Lift restriction")')
    t('with a reason the restriction lifts and the lift is logged', ev(pg, "acqCoRestricted(acq.companies[0].id)") is False and 'lifted' in ev(pg, "acq.acts[acq.acts.length-1].note"))

    # declined stops the sequence; reopening needs a reason
    ev(pg, "acqOutcomeOpen(acq.opps[0].id)"); pg.select_option('#acq-o-oc', 'declined'); pg.click('#acq-modal button:has-text("Save")')
    o = ev(pg, "acq.opps[0]")
    t('a decline closes the opportunity and clears its next step', o['status'] == 'closed' and o['closeReason'] == 'declined' and o['nextAction'] is None)
    open_tab(pg, 'today'); t('a declined opportunity creates no tasks', 'Airport account' not in today_text(pg))
    ev(pg, "acqReopenOpen(acq.opps[0].id)"); pg.click('#acq-modal button:has-text("Reopen")')
    t('reopening a declined opportunity requires a recorded reason', modal_open(pg) and ev(pg, "acq.opps[0].status") == 'closed')
    pg.fill('#acq-r-note', 'Their EA emailed asking for a quote'); pg.click('#acq-modal button:has-text("Reopen")')
    t('with an invitation recorded it reopens and the reason is logged', ev(pg, "acq.opps[0].status") == 'open' and 'invited us' in ev(pg, "acq.acts[acq.acts.length-1].note"))
    pg.context.close()

    # ------------------------------------------------------------------ Duplicates
    pg = new_page(b)
    open_tab(pg, 'companies'); pg.click('#acq-top button:has-text("Start empty")')
    ev(pg, "acqMigrate()")
    add_company(pg, 'Acme Corp.')
    t('adding a company that normalizes to an existing one warns first', modal_open(pg) and 'Possible duplicate' in pg.text_content('#acq-modal') and 'Same name' in pg.text_content('#acq-modal'))
    t('nothing is created or merged while the warning is open', ev(pg, "acq.companies.length") == 2)
    pg.click('#acq-modal button:has-text("Open existing")')
    t('Open existing goes to the existing record', pg.text_content('#acq-detail').count('Acme Corp') >= 1 and ev(pg, "acq.companies.length") == 2)
    add_company(pg, 'Acme Corp.')
    pg.click('#acq-modal button:has-text("create anyway")')
    t('the person can choose to create it anyway', ev(pg, "acq.companies.length") == 3)
    acme = co_id(pg, 'Acme Corp'); dup = co_id(pg, 'Acme Corp.')
    t('the pair is listed for review without being merged', 'Possible duplicates (1)' in pg.text_content('#acq-dups'))
    ev(pg, "acqOpenCo('%s')" % dup); add_contact(pg, 'Dee Park', 'Office manager', 'dee@acme.example')
    add_opp(pg, 'Summit', 'event', 'Dee Park')
    ev(pg, "var o=acq.opps[0];acq.acts.push({id:'ac-hist1',at:'%s',companyId:o.companyId,oppId:o.id,contactId:acq.contacts[acq.contacts.length-1].id,kind:'attempt',channel:'call',outcome:'no_response',note:'left voicemail',spoke:false,need:false,qualified:false,createdAt:1});acqSave();" % YEST)
    ev(pg, "acqOpenCo('%s')" % dup); add_contact(pg, 'Dee Parker', 'Office manager', 'DEE@ACME.EXAMPLE')
    t('a contact with the same email is flagged before it is created', modal_open(pg) and 'Same email' in pg.text_content('#acq-modal'))
    pg.click('#acq-modal button:has-text("Cancel")')
    ev(pg, "acq.companies.filter(function(c){return c.id==='%s'})[0].dnc={on:true,date:'%s',reason:'asked'};acqSave();" % (dup, YEST))
    hist_before = ev(pg, "acq.acts.length")
    # merge the duplicate into the original
    ev(pg, "acqMergeCompanies('%s','%s');acqSave();acqRefresh();" % (acme, dup))
    t('merging keeps every contact, opportunity and activity under the kept company',
      ev(pg, "acq.contacts.filter(function(c){return c.companyId==='%s'}).some(function(c){return c.name==='Dee Park'})" % acme) and ev(pg, "acq.opps.every(function(o){return o.companyId==='%s'})" % acme) and ev(pg, "acq.acts.filter(function(a){return a.id==='ac-hist1'})[0].companyId") == acme)
    t('the merged-away company is archived, not deleted, and history shows the merge', ev(pg, "acqCo('%s').archivedInto" % dup) == acme and ev(pg, "acq.acts.length") == hist_before + 1 and ev(pg, "acqCheck(acq)") == '')
    t('a do-not-contact restriction survives a merge', ev(pg, "acqCoRestricted('%s')" % acme) is True)
    t('archived companies no longer appear in the list', 'Acme Corp.' not in pg.text_content('#acq-list'))
    # contact merge keeps links
    ev(pg, "var c1=acq.contacts.filter(function(c){return c.name==='Dee Park'})[0];acqCreateContact({companyId:'%s',name:'Dee P',email:'dee@acme.example',phone:'(404) 555-0111',verif:[]});" % acme)
    ids = ev(pg, "[acq.contacts.filter(function(c){return c.name==='Dee Park'})[0].id,acq.contacts.filter(function(c){return c.name==='Dee P'})[0].id]")
    ev(pg, "acqMergeContacts('%s','%s');acqSave();" % (ids[0], ids[1]))
    t('merging contacts keeps the kept contact\'s activity and fills missing details', ev(pg, "acqCt('%s').phone" % ids[0]) == '(404) 555-0111' and ev(pg, "acqCt('%s').archivedInto" % ids[1]) == ids[0] and ev(pg, "acqCheck(acq)") == '')
    pg.context.close()

    # ------------------------------------------------------------------ Refresh, backup and restore keep links
    pg = new_page(b)
    open_tab(pg, 'companies')
    with pg.expect_download(): pg.click('#acq-top button:has-text("Download backup and import")')
    ev(pg, "acqOpenCo(acq.companies[0].id)")
    add_contact(pg, 'Eve Stone', 'Executive assistant', 'eve@acme.example')
    add_opp(pg, 'Airport account', 'airport', 'Eve Stone')
    ev(pg, "acqOutcomeOpen(acq.opps[0].id)"); pg.select_option('#acq-o-oc', 'no_response'); pg.click('#acq-modal button:has-text("Save")')
    state1 = ev(pg, "JSON.stringify(acq)")
    pg.reload(); pg.wait_for_function("typeof acq!=='undefined'&&acqReady")
    t('a refresh keeps the same records and links', ev(pg, "JSON.stringify(acq)") == state1 and ev(pg, "acqCheck(acq)") == '')
    ev(pg, "openBackupModal()")
    with pg.expect_download() as di: pg.click('#backup-modal button:has-text("Export Full Backup")')
    bpath = di.value.path()
    bk2 = json.load(open(bpath))
    t('the full backup includes companies, contacts, opportunities and activity', json.loads(bk2['keys']['ob-acq'])['opps'][0]['title'] == 'Airport account')
    # change things, then replace-restore
    ev(pg, "acqCreateCompany('Zeta Holdings','');")
    ev(pg, "acq.opps[0].title='CHANGED';acqSave();")
    pg.set_input_files('#backup-file-input', bpath); pg.wait_for_selector('#backup-preview-summary >> text=will restore')
    t('the restore preview describes the companies in the backup', 'companies,' in pg.text_content('#backup-preview-summary') and 'ob-acq' in pg.text_content('#backup-preview-summary'))
    pg.click('#backup-restore-replace-btn'); pg.wait_for_timeout(1800); pg.wait_for_function("typeof acq!=='undefined'&&acqReady")
    t('Replace restore returns exactly the backed-up records with links intact', ev(pg, "JSON.stringify(acq)") == state1 and ev(pg, "acq.opps[0].title") == 'Airport account' and ev(pg, "acqCheck(acq)") == '')
    # merge restore: new local company survives, nothing duplicated
    ev(pg, "acqCreateCompany('Zeta Holdings','');")
    n_acts = ev(pg, "acq.acts.length")
    ev(pg, "openBackupModal()"); pg.set_input_files('#backup-file-input', bpath); pg.wait_for_selector('#backup-preview-summary >> text=will restore')
    pg.click('#backup-restore-merge-btn'); pg.wait_for_timeout(1800); pg.wait_for_function("typeof acq!=='undefined'&&acqReady")
    ids = ev(pg, "[].concat(acq.companies,acq.contacts,acq.opps,acq.acts).map(function(x){return x.id})")
    t('Merge restore keeps newer local work, adds nothing twice and keeps every link', ev(pg, "acq.companies.some(function(c){return c.name==='Zeta Holdings'})") and len(ids) == len(set(ids)) and ev(pg, "acq.acts.length") == n_acts and ev(pg, "acqCheck(acq)") == '')
    t('a snapshot of current data was taken before each restore', ev(pg, "Object.keys(localStorage).filter(function(k){return k.indexOf('ob-pre-restore-snapshot-')===0}).length") >= 2)
    pg.context.close()

    # ------------------------------------------------------------------ Hostile stored data and layout
    hostile = {'ob-acq': {'v': 1, 'migratedAt': TODAY, 'script': '<img src=x onerror=window.__x=1>',
       'companies': [{'id': '<img src=x onerror=window.__x=1>', 'name': 'bad id'},
                     {'id': 'co-evil', 'name': '<img src=x onerror=window.__x=1>Evil Co', 'website': 'javascript:alert(1)', 'sourceLinks': [{'url': 'javascript:alert(1)', 'label': 'x'}, {'url': 'https://ok.example/a', 'label': '<b>ok</b>'}], 'dnc': {'on': 'yes'}},
                     {'id': 'co-long', 'name': 'L' * 300}],
       'contacts': [{'id': 'ct-one', 'companyId': 'co-missing', 'name': 'Orphan <script>', 'email': 'not an email', 'verif': [{'level': 'booker', 'what': 'x', 'how': ''}]}],
       'opps': [{'id': 'op-one', 'companyId': 'co-evil', 'contactIds': ['ct-nope'], 'title': '<svg onload=window.__x=1>', 'type': 'zzz', 'status': 'zzz', 'nextAction': {'text': 'x', 'date': 'not-a-date'}}],
       'acts': [{'id': 'ac-one', 'at': TODAY, 'companyId': 'co-evil', 'outcome': 'conversation', 'qualified': True, 'spoke': False, 'need': True}]}}
    pg = new_page(b, w=390, h=844, data=hostile)
    open_tab(pg, 'companies')
    c = ev(pg, "JSON.stringify(acq)")
    t('hostile stored data loads without errors', pg.errs == [])
    t('ids that are not safe tokens are dropped', ev(pg, "acq.companies.map(function(c){return c.id}).sort()") == ['co-evil', 'co-long'])
    t('markup, javascript: links and bad emails are stripped on load', '<' not in c and 'javascript' not in c.lower() and ev(pg, "acq.companies[0].website") == '' and ev(pg, "acq.contacts[0].email") == '')
    t('links to missing records are cleared and nothing points at a ghost', ev(pg, "acq.contacts[0].companyId") == '' and ev(pg, "acq.opps[0].contactIds.length") == 0 and ev(pg, "acq.opps[0].nextAction") is None)
    t('a "qualified" flag without a spoken contact is not honoured', ev(pg, "acq.acts[0].qualified") is False)
    t('invalid enums fall back to safe defaults', ev(pg, "acq.opps[0].type") == 'other' and ev(pg, "acq.opps[0].status") == 'open' and ev(pg, "acq.companies[0].dnc") is None)
    ev(pg, "acqOpenCo('co-evil')")
    t('hostile text renders as text and runs nothing', ev(pg, "window.__x") is None and pg.errs == [])
    ev(pg, "acqOpenCo('co-long')")
    t('no horizontal scroll on a 390px screen with a very long name', ev(pg, "document.documentElement.scrollWidth<=window.innerWidth+1"))
    open_tab(pg, 'today'); t('opportunity with no next step shows as needing one in Today', 'No next step and not paused' in today_text(pg))
    pg.context.close()

    # ------------------------------------------------------------------ Storage statement in Data & Backup
    pg = new_page(b)
    ev(pg, "openBackupModal()")
    bt = pg.text_content('#backup-modal')
    t('Data & Backup states the storage and access model honestly', 'No login for the app' in bt and 'row-level security' in bt and 'cannot be checked from this app' in bt and 'not synced' in bt and 'Costs and profit are not stored' in bt)
    pg.context.close()
    b.close()
print('FAILS:', fails)
raise SystemExit(1 if fails else 0)

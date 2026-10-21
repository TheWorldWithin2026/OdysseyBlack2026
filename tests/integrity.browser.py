# Real-browser tests for Release 1c integrity fixes:
# restore conflicts on accepted quote terms, recurring-booking rules, Pipeline follow-up consistency,
# quote status ownership across Quotes and Companies, test-record labelling, release check.
# Start a server first:  python3 -m http.server 8765   (from the repo folder)
import json, datetime, re, shutil, tempfile, os
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
URL = 'http://localhost:8765/index.html'

def seed_script(data):
    return "(function(){if(localStorage.getItem('__seeded'))return;localStorage.setItem('__seeded','1');var d=" + json.dumps(data) + ";Object.keys(d).forEach(function(k){localStorage.setItem(k,JSON.stringify(d[k]));});})();"
def new_page(b, w=1440, h=900, data=None):
    ctx = b.new_context(viewport={'width': w, 'height': h}, accept_downloads=True)
    if data: ctx.add_init_script(seed_script(data))
    pg = ctx.new_page(); pg.errs = []; pg.downloads = 0
    pg.on('pageerror', lambda e: pg.errs.append(str(e)))
    pg.on('dialog', lambda dl: dl.accept())
    pg.on('download', lambda x: setattr(pg, 'downloads', pg.downloads + 1))
    pg.goto(URL)
    return pg
def ev(pg, js): return pg.evaluate(js)
def open_tab(pg, name): pg.click('.tab[onclick*="%s"]' % name)
def start_empty(pg):
    open_tab(pg, 'companies'); pg.click('#acq-top button:has-text("Start empty")')
def mk_co(pg, name):
    ev(pg, "acqCreateCompany(%s,'')" % json.dumps(name)); return ev(pg, "acq.companies.filter(function(c){return c.name===%s})[0].id" % json.dumps(name))
def mk_ct(pg, co, name, email=''):
    ev(pg, "acqCreateContact({companyId:%s,name:%s,email:%s})" % (json.dumps(co), json.dumps(name), json.dumps(email)))
    return ev(pg, "acq.contacts.filter(function(c){return c.name===%s&&c.companyId===%s})[0].id" % (json.dumps(name), json.dumps(co)))
def mk_op(pg, co, title, ct=''):
    return ev(pg, """() => {var o={id:acqNewId('op'),companyId:%s,contactIds:%s,title:%s,type:'airport',stage:'identified',status:'open',owner:'Kerry',nextAction:{text:'First contact',date:todayAddDays(1),kind:'outreach',contactId:%s},pauseReason:'',closeReason:'',closedAt:'',qual:{},notes:'',createdAt:atlDateStr(),updatedAt:Date.now(),projected:null,archived:null};ACQ_QUAL.forEach(function(q){o.qual[q[0]]='';});acq.opps.push(o);acqSave();acqRefresh();return o.id;}""" % (json.dumps(co), json.dumps([ct] if ct else []), json.dumps(title), json.dumps(ct)))
def quote_add(pg, oid, amt, veh='sedan', date='', frm='', to='', src='', scope='trip'):
    ev(pg, "acqQuoteOpen(%s,%s)" % (json.dumps(oid), json.dumps(src)))
    pg.select_option('#acq-q-veh', veh); pg.fill('#acq-q-amt', str(amt)); pg.select_option('#acq-q-scope', scope)
    if date: pg.fill('#acq-q-date', date)
    if frm: pg.fill('#acq-q-from', frm)
    if to: pg.fill('#acq-q-to', to)
    pg.click('#acq-modal button:has-text("Save quote")')
    return ev(pg, "acq.quotes[acq.quotes.length-1].id")
def quote_accept(pg, qid, n, date=None):
    ev(pg, "acqQuoteAcceptOpen(%s,%d)" % (json.dumps(qid), n)); pg.fill('#acq-qa-date', date or TODAY)
    pg.click('#acq-modal button:has-text("Record acceptance")')
def quote_revise(pg, qid, amt, note='price change'):
    ev(pg, "acqQuoteReviseOpen(%s)" % json.dumps(qid)); pg.fill('#acq-q-amt', str(amt)); pg.fill('#acq-q-note', note)
    pg.click('#acq-modal button:has-text("Save revision")')
def booking_add(pg, oid, qid, date, time='', amt='', rep=0, veh=None):
    ev(pg, "acqBookingOpen(%s,%s)" % (json.dumps(oid), json.dumps(qid)))
    pg.fill('#acq-b-date', date)
    if time: pg.fill('#acq-b-time', time)
    if amt != '': pg.fill('#acq-b-amt', str(amt))
    if rep:
        pg.select_option('#acq-b-rep', 'weekly'); pg.fill('#acq-b-cnt', str(rep + 1))
    pg.click('#acq-b-go')
def today_text(pg): return pg.text_content('#today-body')
def sections(pg): return ev(pg, "Array.from(document.querySelectorAll('#today-body .card')).map(function(c){return [c.querySelector('.mini-badge').textContent,c.textContent]})")
def sec(pg, name):
    for n, tx in sections(pg):
        if n == name: return tx
    return ''
def dump(pg): return ev(pg, "(function(){var o={};for(var i=0;i<localStorage.length;i++){var k=localStorage.key(i);o[k]=localStorage.getItem(k);}return JSON.stringify(o);})()")


QT = lambda i, client, sedan, suv, follow: {'id': 'qt-17000000000%d' % i, 'client': client, 'from': 'ATL', 'to': 'Buckhead', 'miles': 20, 'date': d(10), 'time': '09:00', 'peak': 'no', 'sedan': sedan, 'suv': suv, 'status': 'sent', 'follow': follow, 'at': d(-5)}
TMP = tempfile.mkdtemp()
def write_backup(name, acq_obj, extra=None):
    keys = {'ob-acq': json.dumps(acq_obj)}
    if extra: keys.update(extra)
    path = os.path.join(TMP, name)
    open(path, 'w').write(json.dumps({'app': 'odyssey-black-executive-acquisition-suite', 'schemaVersion': 2, 'appRelease': '1c', 'exportedAt': datetime.datetime.utcnow().isoformat() + 'Z', 'keys': keys}))
    return path
def open_backup(pg): pg.evaluate("openBackupModal()")
def acq_raw(pg): return json.loads(ev(pg, "localStorage.getItem('ob-acq')"))
def row_btns(pg, name): return ev(pg, "(function(){var r=Array.from(document.querySelectorAll('#today-body .btns')).map(function(b){return b.parentElement}).filter(function(e){return e.textContent.indexOf(%s)!==-1&&e.textContent.indexOf('Quote follow-up')!==-1})[0];return r?Array.from(r.querySelectorAll('button')).map(function(b){return b.textContent}):null;})()" % json.dumps(name))
def derived_ok(pg):
    return ev(pg, "acq.quotes.every(function(q){if(!q.legacyId)return true;var l=qtFind(q.legacyId);return !l||l.status===acqDerivedStatus(q);})")

with sync_playwright() as p:
    b = p.chromium.launch()

    # =====================================================================  1. Restore conflicts on accepted terms
    pg = new_page(b)
    t('no page errors on load', pg.errs == [])
    start_empty(pg)
    co = mk_co(pg, 'Acme Conflict'); ct = mk_ct(pg, co, 'Dana Booker'); op = mk_op(pg, co, 'Airport account', ct)
    q = quote_add(pg, op, 400, 'suv', d(8), 'ATL Airport', 'Buckhead', '', 'recurring'); quote_accept(pg, q, 1, d(-1))
    booking_add(pg, op, q, d(8), '09:00')
    t('setup: one accepted quote v1 at $400 and one booking at $400', ev(pg, "acqAcceptedVer(acqQt(%s)).amount" % json.dumps(q)) == 400 and ev(pg, "acq.bookings.length") == 1 and ev(pg, "acq.bookings[0].amount") == 400)
    base = acq_raw(pg)
    t('a stored quote version records whether it covers one trip or a recurring arrangement', base['quotes'][0]['versions'][0]['scope'] == 'recurring' and base['conflicts'] == [])

    def variant(mut, newer=True):
        o = json.loads(json.dumps(base)); mut(o)
        if newer:
            for r in o['quotes']: r['updatedAt'] += 100000
            for r in o['bookings']: r['updatedAt'] += 100000
        return o
    def mut_amount(o): o['quotes'][0]['versions'][0]['amount'] = 999
    inc = variant(mut_amount)
    merged = ev(pg, "acqMergeRaw(JSON.parse(localStorage.getItem('ob-acq')),%s,'test')" % json.dumps(inc))
    mq = merged['quotes'][0]
    t('a NEWER backup with different content for the accepted version does not overwrite it', mq['versions'][0]['amount'] == 400 and mq['versions'][0]['status'] == 'accepted' and mq['versions'][0]['acceptedAt'] == d(-1))
    t('both copies are retained: the other one sits in conflicts with its own amount', len(merged['conflicts']) == 1 and merged['conflicts'][0]['kind'] == 'quote' and merged['conflicts'][0]['copy']['amount'] == 999 and merged['conflicts'][0]['n'] == 1)
    t('the existing booking keeps its original agreed terms', merged['bookings'][0]['amount'] == 400 and merged['bookings'][0]['quoteVersion'] == 1)
    again = ev(pg, "acqMergeRaw(%s,%s,'test')" % (json.dumps(merged), json.dumps(inc)))
    t('merging the same file again does not pile up duplicate conflicts', len(again['conflicts']) == 1)
    # reverse direction: the accepted copy is in the incoming file and the local copy differs
    local_diff = json.loads(json.dumps(base)); local_diff['quotes'][0]['versions'][0]['status'] = 'sent'; local_diff['quotes'][0]['versions'][0]['acceptedAt'] = ''; local_diff['quotes'][0]['versions'][0]['amount'] = 350; local_diff['quotes'][0]['updatedAt'] += 100000
    rev = ev(pg, "acqMergeRaw(%s,%s,'test')" % (json.dumps(local_diff), json.dumps(base)))
    t('an accepted copy in the backup is not lost to a newer non-accepted local copy; the other is kept for resolution', rev['quotes'][0]['versions'][0]['amount'] == 400 and rev['quotes'][0]['versions'][0]['acceptedAt'] == d(-1) and len(rev['conflicts']) == 1 and rev['conflicts'][0]['copy']['amount'] == 350)
    # acceptance dates differ
    def mut_date(o): o['quotes'][0]['versions'][0]['acceptedAt'] = d(-3)
    dd = ev(pg, "acqMergeRaw(JSON.parse(localStorage.getItem('ob-acq')),%s,'test')" % json.dumps(variant(mut_date)))
    t('different acceptance dates for the same version are also flagged, current date kept', dd['quotes'][0]['versions'][0]['acceptedAt'] == d(-1) and len(dd['conflicts']) == 1)
    # identical content and non accepted versions merge without conflict
    same = ev(pg, "acqMergeRaw(JSON.parse(localStorage.getItem('ob-acq')),%s,'test')" % json.dumps(variant(lambda o: None)))
    t('identical content merges with no conflict', same['conflicts'] == [])
    ev(pg, "(function(){var q=acqQt(%s);q.versions[0].status='superseded';q.versions.push({n:2,at:atlDateStr(),vehicle:'suv',amount:420,from:'A',to:'B',miles:0,date:'',time:'',note:'',status:'sent',acceptedAt:'',scope:'recurring'});acqTouch(q);acqSave();})()" % json.dumps(q))
    base2 = acq_raw(pg)
    inc2 = json.loads(json.dumps(base2)); inc2['quotes'][0]['versions'][1]['amount'] = 460; inc2['quotes'][0]['updatedAt'] += 100000
    nc = ev(pg, "acqMergeRaw(JSON.parse(localStorage.getItem('ob-acq')),%s,'test')" % json.dumps(inc2))
    t('a not-yet-accepted version follows the newer record: no conflict, newer content wins', nc['conflicts'] == [] and nc['quotes'][0]['versions'][1]['amount'] == 460)
    # booking with different agreed terms
    inc3 = json.loads(json.dumps(base2)); inc3['bookings'][0]['amount'] = 123; inc3['bookings'][0]['updatedAt'] += 100000
    bc = ev(pg, "acqMergeRaw(JSON.parse(localStorage.getItem('ob-acq')),%s,'test')" % json.dumps(inc3))
    t('a booking whose agreed terms differ keeps the current terms and flags the other copy', bc['bookings'][0]['amount'] == 400 and len(bc['conflicts']) == 1 and bc['conflicts'][0]['kind'] == 'booking' and bc['conflicts'][0]['copy']['amount'] == 123)
    # a null value for an existing array key never converts it to an object
    ev(pg, "(function(){localStorage.setItem('ob-gatekeepers',JSON.stringify([{id:1,name:'Pat',type:'concierge'}]));})()")
    # restore for real: Merge from a file with a newer, different accepted term
    ev(pg, "(function(){var q=acqQt(%s);q.versions.pop();q.versions[0].status='accepted';acqTouch(q);acqSave();})()" % json.dumps(q))
    base = acq_raw(pg)
    inc = variant(mut_amount)
    path = write_backup('conflict.json', inc, {'ob-gatekeepers': None, 'ob-pipeline': None})
    # build the file so that null-valued keys are really JSON null
    f = json.load(open(path)); f['keys']['ob-gatekeepers'] = None; f['keys']['ob-pipeline'] = None; json.dump(f, open(path, 'w'))
    state_before = ev(pg, "localStorage.getItem('ob-acq')"); gk_before = ev(pg, "localStorage.getItem('ob-gatekeepers')")
    open_backup(pg); pg.set_input_files('#backup-file-input', path); pg.wait_for_selector('#backup-preview-summary >> text=will restore')
    pv = pg.text_content('#backup-preview-summary')
    t('the restore preview warns that Replace overwrites accepted terms and Merge protects them', 'Replace overwrites ALL Companies data' in pv and 'Merge keeps accepted terms' in pv)
    t('the restore preview says how many conflicts Merge would flag, and changed nothing', 'Merge would flag 1 conflict ' in pv and ev(pg, "localStorage.getItem('ob-acq')") == state_before)
    pg.click('#backup-restore-merge-btn'); pg.wait_for_timeout(1800); pg.wait_for_function("typeof acq!=='undefined'&&acqReady")
    t('after the Merge restore the accepted terms are unchanged', ev(pg, "acqAcceptedVer(acqQt(%s)).amount" % json.dumps(q)) == 400 and ev(pg, "acq.bookings[0].amount") == 400)
    t('a null value in a backup does not overwrite or damage an existing list', ev(pg, "localStorage.getItem('ob-gatekeepers')") == gk_before and ev(pg, "Array.isArray(JSON.parse(localStorage.getItem('ob-gatekeepers')))"))
    t('one conflict is stored, with both amounts available', ev(pg, "acq.conflicts.length") == 1 and ev(pg, "acq.conflicts[0].copy.amount") == 999)
    open_tab(pg, 'companies')
    cf = pg.text_content('#acq-conflicts')
    t('a red notice on Companies says a decision is needed', 'Restore conflicts: 1 need your decision' in cf and 'Bookings keep their own agreed terms' in cf)
    open_tab(pg, 'today')
    t('Today shows a critical row for the conflict', 'Restore conflicts need your decision (1)' in sec(pg, 'Acquisition'))
    # blocked actions
    ev(pg, "acqOpenCo(%s)" % json.dumps(co)); open_tab(pg, 'companies')
    ev(pg, "acqBookingOpen(%s,%s)" % (json.dumps(op), json.dumps(q)))
    t('creating a booking from the conflicted quote is blocked', not pg.is_visible('#acq-modal.open') and ev(pg, "acq.bookings.length") == 1)
    ev(pg, "acqQuoteReviseOpen(%s)" % json.dumps(q))
    t('revising the conflicted quote is blocked', not pg.is_visible('#acq-modal.open'))
    t('the quote card says it has a restore conflict', 'Restore conflict on this quote' in pg.text_content('#acq-detail'))
    open_tab(pg, 'quotes')
    t('the Quotes tab shows the same notice', pg.locator('#qt-log #acq-conflicts').count() == 1)
    open_tab(pg, 'companies')
    pg.click('#acq-conflicts button:has-text("Review and decide")')
    modal = pg.text_content('#acq-modal')
    t('the decision screen shows the current terms and the restored copy side by side', '$400.00' in pg.text_content('#acq-cf-cur') and '$999.00' in pg.text_content('#acq-cf-new') and '1 booking made from this version keep their own agreed terms' in modal)
    pg.click('#acq-modal button:has-text("Decide later")')
    t('deciding later changes nothing', ev(pg, "acq.conflicts.length") == 1)
    pg.click('#acq-conflicts button:has-text("Review and decide")'); pg.click('#acq-modal button:has-text("Keep current terms")')
    t('keeping current terms clears the conflict and leaves $400 accepted', ev(pg, "acq.conflicts.length") == 0 and ev(pg, "acqAcceptedVer(acqQt(%s)).amount" % json.dumps(q)) == 400)
    t('the decision is logged on the company with the discarded copy', ev(pg, "acq.acts.filter(function(a){return /Restore conflict, quote v1: kept current terms/.test(a.note)&&/999/.test(a.note)}).length") == 1)
    # second conflict resolved with the restored copy
    ev(pg, "acqMergeRaw && (function(){var m=acqMergeRaw(JSON.parse(localStorage.getItem('ob-acq')),%s,'Restore (Merge) test');acq=acqClean(m);acqSave();acqRefresh();})()" % json.dumps(inc))
    t('the second restore flags the conflict again', ev(pg, "acq.conflicts.length") == 1)
    pg.click('#acq-conflicts button:has-text("Review and decide")'); pg.click('#acq-modal button:has-text("Use restored copy")')
    v1 = ev(pg, "acqQt(%s).versions[0]" % json.dumps(q))
    t('using the restored copy applies it to the quote only', v1['amount'] == 999 and v1['status'] == 'accepted' and ev(pg, "acq.conflicts.length") == 0)
    t('the booking made earlier still has its original $400 even after the quote was changed', ev(pg, "acq.bookings[0].amount") == 400 and ev(pg, "acq.bookings[0].quoteVersion") == 1)
    t('the dataset is consistent after both resolutions', ev(pg, "acqCheck(acq)") == '')
    # booking conflict resolution
    inc3 = acq_raw(pg); inc3['bookings'][0]['amount'] = 77; inc3['bookings'][0]['updatedAt'] += 100000
    ev(pg, "(function(){acq=acqClean(acqMergeRaw(JSON.parse(localStorage.getItem('ob-acq')),%s,'Restore (Merge) test'));acqSave();acqRefresh();})()" % json.dumps(inc3))
    t('a booking conflict shows in the notice', 'Booking' in pg.text_content('#acq-conflicts'))
    pg.click('#acq-conflicts button:has-text("Review and decide")'); pg.click('#acq-modal button:has-text("Keep current terms")')
    t('keeping current booking terms leaves the booking as it was', ev(pg, "acq.bookings[0].amount") == 400 and ev(pg, "acq.conflicts.length") == 0)
    # hostile conflicts are sanitised on load
    bad = acq_raw(pg); bad['conflicts'] = [{'id': 'cf-x1', 'kind': 'quote', 'refId': 'qq-nope', 'copy': {'n': 1, 'amount': 5}}, {'id': 'cf-x2', 'kind': 'weird', 'refId': q, 'copy': {}}, {'id': 'zz-bad', 'kind': 'quote', 'refId': q, 'copy': {'n': 1, 'amount': 5}}, {'id': 'cf-x3', 'kind': 'quote', 'refId': q, 'copy': {'n': 1, 'amount': '<img src=x onerror=alert(1)>'}}]
    cl = ev(pg, "acqClean(%s)" % json.dumps(bad))
    t('conflicts pointing at nothing, of unknown kind, with bad ids or bad amounts are dropped on load', cl['conflicts'] == [])
    t('no page errors during the conflict scenarios', pg.errs == [])
    pg.context.close()

    # =====================================================================  2. Recurring bookings
    pg = new_page(b); start_empty(pg)
    co = mk_co(pg, 'Series Co'); op = mk_op(pg, co, 'Weekly airport')
    qt1 = quote_add(pg, op, 150, 'sedan', d(14), 'Home', 'ATL', '', 'trip')
    ev(pg, "acqQuoteAcceptOpen(%s,1)" % json.dumps(qt1)); mt = pg.text_content('#acq-modal')
    t('accepting a one-trip quote says so plainly: one trip only, one booking', 'acceptance of one trip only' in mt and 'Only one booking' in mt)
    pg.fill('#acq-qa-date', TODAY); pg.click('#acq-modal button:has-text("Record acceptance")')
    ev(pg, "acqBookingOpen(%s,%s)" % (json.dumps(op), json.dumps(qt1)))
    t('a one-trip quote offers no repeat controls', pg.locator('#acq-b-rep').count() == 0 and 'one trip' in pg.text_content('#acq-modal'))
    pg.fill('#acq-b-date', d(14)); t('the preview shows the date and a count of one', '1 booking will be created' in pg.text_content('#acq-b-prev') and 'Create 1 booking' in pg.text_content('#acq-b-go'))
    pg.click('#acq-b-go')
    t('one booking exists', ev(pg, "acq.bookings.length") == 1)
    ev(pg, "acqBookingOpen(%s,%s)" % (json.dumps(op), json.dumps(qt1)))
    t('a second booking from the one-trip quote is refused', not pg.is_visible('#acq-modal.open') and ev(pg, "acq.bookings.length") == 1)
    qr = quote_add(pg, op, 120, 'sedan', d(21), 'Home', 'ATL', '', 'recurring')
    ev(pg, "acqQuoteAcceptOpen(%s,1)" % json.dumps(qr)); mt = pg.text_content('#acq-modal')
    t('accepting a recurring quote says it is acceptance of a recurring arrangement and dates are chosen later', 'acceptance of a recurring arrangement' in mt and 'choose the dates' in mt)
    pg.fill('#acq-qa-date', TODAY); pg.click('#acq-modal button:has-text("Record acceptance")')
    open_tab(pg, 'companies'); ev(pg, "acqOpenCo(%s)" % json.dumps(co))
    t('the quote card labels each version one trip or recurring', 'recurring arrangement' in pg.text_content('#acq-detail') and 'one trip' in pg.text_content('#acq-detail'))
    ev(pg, "acqBookingOpen(%s,%s)" % (json.dumps(op), json.dumps(qr)))
    pg.fill('#acq-b-date', d(21)); pg.fill('#acq-b-time', '07:30')
    pg.select_option('#acq-b-rep', 'weekly')
    t('a weekly series with no end is not allowed: the preview explains and Create is disabled', pg.is_disabled('#acq-b-go') and 'Choose how the series ends' in pg.text_content('#acq-b-prev'))
    ev(pg, "acqBookingSave()")
    t('forcing the save does nothing either', ev(pg, "acq.bookings.length") == 1)
    ev(pg, "acqBookingOpen(%s,%s)" % (json.dumps(op), json.dumps(qr)))
    pg.fill('#acq-b-date', d(21)); pg.fill('#acq-b-time', '07:30'); pg.select_option('#acq-b-rep', 'weekly'); pg.fill('#acq-b-cnt', '4')
    pr = pg.text_content('#acq-b-prev')
    t('the preview lists every date and the number of bookings before anything is created', '4 bookings will be created' in pr and all(x in pr for x in [d(21), d(28), d(35), d(42)]) and 'Create 4 bookings' in pg.text_content('#acq-b-go') and ev(pg, "acq.bookings.length") == 1)
    pg.fill('#acq-b-last', d(35))
    t('when both a count and a last date are given the series stops at whichever comes first', '3 bookings will be created' in pg.text_content('#acq-b-prev') and d(42) not in pg.text_content('#acq-b-prev'))
    pg.fill('#acq-b-cnt', ''); pg.fill('#acq-b-last', d(10))
    t('a last date before the first trip is refused', pg.is_disabled('#acq-b-go') and 'before the first trip' in pg.text_content('#acq-b-prev'))
    pg.fill('#acq-b-last', ''); pg.fill('#acq-b-cnt', '27')
    t('more than 26 trips is refused', pg.is_disabled('#acq-b-go') and 'At most 26' in pg.text_content('#acq-b-prev'))
    pg.fill('#acq-b-cnt', '4')
    pg.dblclick('#acq-b-go') if False else pg.click('#acq-b-go')
    ser = ev(pg, "acq.bookings.filter(function(b){return b.series}).map(function(b){return b.serviceDate})")
    t('exactly the previewed dates were created, in one series', ser == [d(21), d(28), d(35), d(42)] and ev(pg, "new Set(acq.bookings.filter(function(b){return b.series}).map(function(b){return b.series})).size") == 1)
    # duplicates
    ev(pg, "acqBookingOpen(%s,%s)" % (json.dumps(op), json.dumps(qr)))
    pg.fill('#acq-b-date', d(28)); pg.fill('#acq-b-time', '07:30'); pg.select_option('#acq-b-rep', 'weekly'); pg.fill('#acq-b-cnt', '5')
    pr = pg.text_content('#acq-b-prev')
    t('overlapping dates are shown as already booked and skipped, only the new ones are counted', '2 bookings will be created' in pr and pr.count('already booked, skipped') == 3 and d(49) in pr and d(56) in pr)
    pg.click('#acq-b-go')
    t('only the two new occurrences were created; no duplicates', ev(pg, "acq.bookings.filter(function(b){return b.quoteId===%s}).length" % json.dumps(qr)) == 6 and ev(pg, "new Set(acq.bookings.filter(function(b){return b.quoteId===%s&&b.status!=='cancelled'}).map(function(b){return b.serviceDate+b.time})).size" % json.dumps(qr)) == 6)
    # cancel one occurrence
    open_tab(pg, 'companies'); ev(pg, "acqOpenCo(%s)" % json.dumps(co))
    card = pg.text_content('#acq-detail')
    t('each booking in a series says which trip it is and offers Cancel this trip only', 'Trip 2 of 4' in card and pg.locator('#acq-detail button:has-text("Cancel this trip only")').count() >= 4)
    second = ev(pg, "acq.bookings.filter(function(b){return b.series&&b.serviceDate===%s})[0].id" % json.dumps(d(28)))
    ev(pg, "acqBookingCancelOpen(%s)" % json.dumps(second)); mt = pg.text_content('#acq-modal')
    t('the cancel screen says only this trip is cancelled and how many others stay', 'Only the trip on ' + d(28) in mt and 'The other' in mt and 'stay as they are' in mt)
    pg.fill('#acq-bc-note', 'client travelling'); pg.click('#acq-modal button:has-text("Cancel booking")')
    st = ev(pg, "acq.bookings.filter(function(b){return b.series}).map(function(b){return b.serviceDate+':'+b.status})")
    t('exactly one occurrence is cancelled; the others in the series are still scheduled', st == [d(21) + ':scheduled', d(28) + ':cancelled', d(35) + ':scheduled', d(42) + ':scheduled', d(49) + ':scheduled', d(56) + ':scheduled'])
    t('the cancelled occurrence is left out of completed value and counted as cancelled', ev(pg, "acqValues().cancelled") == 1 and ev(pg, "acqValues().completed") == 0)
    ev(pg, "acqBookingOpen(%s,%s)" % (json.dumps(op), json.dumps(qr)))
    pg.fill('#acq-b-date', d(28)); pg.fill('#acq-b-time', '07:30')
    t('a cancelled date can be booked again without being treated as a duplicate', '1 booking will be created' in pg.text_content('#acq-b-prev'))
    pg.click('#acq-modal button:has-text("Cancel")')
    # without a quote: series also needs an end
    ev(pg, "acqBookingOpen(%s,'')" % json.dumps(op)); pg.fill('#acq-b-date', d(60)); pg.select_option('#acq-b-rep', 'weekly')
    t('a booking without a quote also needs an end for a series', pg.is_disabled('#acq-b-go'))
    pg.click('#acq-modal button:has-text("Cancel")')
    t('no page errors during recurring scenarios', pg.errs == [])
    pg.context.close()

    # =====================================================================  3. Pipeline follow-up consistency
    SEEDP = {
      'ob-pipeline': [{'id': 1700000000001, 'name': 'Jane Roe', 'title': 'CEO', 'company': 'Acme Corp, Inc.', 'stage': 'trial-done', 'score': 30, 'travel': 'heavy', 'followUp': YEST, 'convProb': 'High', 'responseStatus': 'none', 'notes': 'Met at conference.', 'lastContact': d(-10)},
                      {'id': 1700000000002, 'name': 'Neil Open', 'title': 'VP', 'company': 'Zeta Systems', 'stage': 'contacted', 'score': 20, 'travel': 'light', 'followUp': YEST, 'convProb': 'High', 'responseStatus': 'none', 'notes': '', 'lastContact': d(-9)}],
    }
    pg = new_page(b, data=SEEDP)
    open_tab(pg, 'companies'); pg.click('#acq-top button:has-text("Download backup and import")')
    open_tab(pg, 'pipeline')
    cards = pg.locator('#view-pipeline .pipe-card, .pipe-card').count()
    jane_btns = ev(pg, "Array.from(document.querySelectorAll('.pipe-card')).filter(function(c){return c.textContent.indexOf('Jane Roe')!==-1})[0].textContent")
    t('before linking, the Pipeline card has its follow-up prompts', 'Follow-up' in jane_btns and 'Outreach' in jane_btns)
    aq_before = pg.text_content('#aq-items')
    t('before linking, the action queue lists both prospects', 'Jane Roe' in aq_before and 'Neil Open' in aq_before)
    ov_before = pg.text_content('#st-bm')
    t('before linking, two follow-ups count as overdue', '2 overdue' in ov_before)
    acme = ev(pg, "acqFindCo(acq,'Acme Corp').id")
    open_tab(pg, 'companies'); ev(pg, "acqOpenCo(%s)" % json.dumps(acme))
    pg.select_option('#acq-pl-pick', '1700000000001'); pg.click('#acq-detail button:has-text("Link or convert")'); pg.click('#acq-modal button:has-text("Link prospect")')
    open_tab(pg, 'pipeline')
    jane = ev(pg, "Array.from(document.querySelectorAll('.pipe-card')).filter(function(c){return c.textContent.indexOf('Jane Roe')!==-1})[0].outerHTML")
    t('a linked prospect says plainly to follow up in Companies', 'Linked to Companies. Follow up there, not here.' in jane)
    t('the linked card offers Open in Companies and Edit only', 'Open in Companies' in jane and '>Edit<' in jane and all(x not in jane for x in ['>Outreach<', 'Follow-up <', '$Value', 'Advance', 'Remove', 'followup-alert', 'No response']))
    t('the unlinked prospect keeps all its normal prompts', 'Outreach' in ev(pg, "Array.from(document.querySelectorAll('.pipe-card')).filter(function(c){return c.textContent.indexOf('Neil Open')!==-1})[0].textContent"))
    aq = pg.text_content('#aq-items')
    t('the action queue no longer lists the linked prospect, only the unlinked one', 'Jane Roe' not in aq and 'Neil Open' in aq)
    t('overdue count and trial counts leave the linked prospect out', '1 overdue' in pg.text_content('#st-bm'))
    cc = ev(pg, "document.getElementById('cc-body')?document.getElementById('cc-body').textContent:document.body.textContent")
    pg.click('.pipe-card[data-linked="1"] button:has-text("Open in Companies")')
    t('Open in Companies goes to the company page', ev(pg, "acqSel") == acme and pg.is_visible('#acq-detail'))
    open_tab(pg, 'today')
    t('Today shows the follow-up once, in Acquisition, and not in Pipeline', 'Jane Roe' not in sec(pg, 'Pipeline') and 'Neil Open' in sec(pg, 'Pipeline') and ev(pg, "acq.plinks.length") == 1)
    pg_raw = ev(pg, "localStorage.getItem('ob-pipeline')")
    open_tab(pg, 'companies'); ev(pg, "acqOpenCo(%s)" % json.dumps(acme)); pg.click('#acq-detail button:has-text("Undo link")')
    open_tab(pg, 'pipeline')
    t('undoing the link restores the prospect\'s Pipeline prompts, with its data untouched', 'Follow-up' in ev(pg, "Array.from(document.querySelectorAll('.pipe-card')).filter(function(c){return c.textContent.indexOf('Jane Roe')!==-1})[0].textContent") and ev(pg, "localStorage.getItem('ob-pipeline')") == pg_raw)
    t('no page errors in Pipeline scenarios', pg.errs == [])
    pg.context.close()

    # =====================================================================  4. Quote status consistency
    SEEDQ = {'ob-quotes': {'log': [QT(31, 'Alpha Co', 100, 140, YEST), QT(32, 'Bravo Co', 110, 150, YEST), QT(33, 'Charlie Co', 120, 160, YEST), dict(QT(34, 'Delta Won', 130, 170, ''), status='won'), dict(QT(35, 'Echo Lost', 90, 120, ''), status='lost'), QT(36, 'Plain Unlinked', 95, 125, YEST)]}}
    pg = new_page(b, data=SEEDQ); start_empty(pg)
    ca = mk_co(pg, 'Alpha Co'); oa = mk_op(pg, ca, 'Alpha deal')
    cb = mk_co(pg, 'Bravo Co'); ob = mk_op(pg, cb, 'Bravo deal')
    cc_ = mk_co(pg, 'Charlie Co'); oc = mk_op(pg, cc_, 'Charlie deal')
    qa = quote_add(pg, oa, 100, 'sedan', d(9), 'A', 'B', 'qt-1700000000031', 'recurring')
    qb = quote_add(pg, ob, 110, 'sedan', d(9), 'A', 'B', 'qt-1700000000032', 'trip')
    qc = quote_add(pg, oc, 120, 'sedan', d(9), 'A', 'B', 'qt-1700000000033', 'trip')
    st = lambda lid: ev(pg, "qtFind(%s).status" % json.dumps(lid))
    A, B, C = 'qt-1700000000031', 'qt-1700000000032', 'qt-1700000000033'
    open_tab(pg, 'quotes')
    row = pg.text_content('#qt-log')
    t('a linked quote shows its status as managed in Companies and has no status dropdown', 'Managed in Companies. Change it there.' in row and pg.locator('#qt-log [data-qt-managed]').count() == 3)
    t('unlinked quotes keep their own status dropdown', pg.locator('#qt-log select').count() >= 3)
    t('initially every linked quote is Waiting on both sides', st(A) == 'sent' and derived_ok(pg))
    ev(pg, "qtSet(%s,'status','won')" % json.dumps(A))
    t('trying to change a linked quote\'s status from the Quotes tab is refused', st(A) == 'sent')
    # accept
    quote_accept(pg, qa, 1, TODAY)
    t('acceptance in Companies makes the Quotes tab entry Won', st(A) == 'won' and derived_ok(pg))
    open_tab(pg, 'quotes'); t('the Quotes tab explains it: Won, v1 accepted on that date', 'Won: v1 accepted ' + TODAY in pg.text_content('#qt-log'))
    # revision
    quote_revise(pg, qa, 130)
    t('a revision after acceptance leaves it Won and says the revision is waiting', st(A) == 'won' and derived_ok(pg) and ev(pg, "acqStatusLabel(acqQt(%s))" % json.dumps(qa)).find('revision v2 is waiting') != -1)
    quote_accept(pg, qa, 2, TODAY)
    t('accepting the revision keeps it Won, now v2', st(A) == 'won' and 'v2 accepted' in ev(pg, "acqStatusLabel(acqQt(%s))" % json.dumps(qa)))
    # booking cancellation does not change status
    booking_add(pg, oa, qa, d(9), '09:00'); bk = ev(pg, "acq.bookings[0].id")
    ev(pg, "acqBookingCancelOpen(%s)" % json.dumps(bk)); pg.click('#acq-modal button:has-text("Cancel booking")')
    t('cancelling the booking does not un-accept the quote; both tabs still say Won', st(A) == 'won' and ev(pg, "acqAcceptedVer(acqQt(%s)).n" % json.dumps(qa)) == 2 and derived_ok(pg))
    open_tab(pg, 'companies'); ev(pg, "acqOpenCo(%s)" % json.dumps(ca))
    t('the Companies card says so', 'Cancelling a booking does not un-accept the quote' in pg.text_content('#acq-detail'))
    # unlink
    ev(pg, "acqQuoteUnlink(%s)" % json.dumps(qa))
    t('an accepted quote cannot be unlinked, so the two tabs cannot drift that way', ev(pg, "acq.quotes.length") == 3 and st(A) == 'won')
    ev(pg, "acqQuoteUnlink(%s)" % json.dumps(qb))
    t('unlinking a waiting quote hands its status back to the Quotes tab', ev(pg, "acq.quotes.length") == 2 and st(B) == 'sent')
    open_tab(pg, 'quotes'); ev(pg, "qtSet(%s,'status','lost')" % json.dumps(B))
    t('after unlinking it can be changed in the Quotes tab again', st(B) == 'lost')
    ev(pg, "qtSet(%s,'status','sent')" % json.dumps(B))
    # lost via opportunity
    ev(pg, "(function(){var o=acqOp(%s);o.status='closed';o.closeReason='lost';o.closedAt=atlDateStr();o.nextAction=null;acqTouch(o);acqSave();acqRefresh();})()" % json.dumps(oc))
    t('closing the opportunity as lost makes the linked quote Lost in the Quotes tab too', st(C) == 'lost' and derived_ok(pg))
    open_tab(pg, 'today'); t('a lost linked quote no longer produces a reminder', 'Charlie Co' not in sec(pg, 'Quotes'))
    ev(pg, "(function(){var o=acqOp(%s);o.status='open';o.closeReason='';o.closedAt='';acqTouch(o);acqSave();acqRefresh();})()" % json.dumps(oc))
    t('reopening it returns the quote to Waiting on both sides', st(C) == 'sent' and derived_ok(pg))
    cb_ = row_btns(pg, 'Charlie Co'); ub_ = row_btns(pg, 'Plain Unlinked')
    t('a linked quote\'s Today reminder offers Open in Companies and no Won/Lost', cb_ is not None and 'Open in Companies' in cb_ and 'Won' not in cb_ and 'Lost' not in cb_)
    qs = sec(pg, 'Quotes')
    t('the unlinked quote keeps Won and Lost buttons on Today', ub_ is not None and 'Won' in ub_ and 'Lost' in ub_ and 'Open in Companies' not in ub_)
    # discrepancy after a restore or a stale copy: Companies says accepted, Quotes tab says waiting
    ev(pg, "(function(){qtFind(%s).status='sent';qtSave();})()" % json.dumps(A))
    pg.reload(); pg.wait_for_function("typeof acq!=='undefined'&&acqReady")
    t('on load the mismatch is corrected to match Companies', st(A) == 'won' and derived_ok(pg))
    open_tab(pg, 'quotes'); bn = pg.text_content('#qt-log')
    t('and it is surfaced: a red notice names the quote and what changed', 'Quote status corrected: 1' in bn and 'Alpha Co: sent' in bn)
    open_tab(pg, 'companies')
    t('the same notice appears in Companies', 'Quote status corrected: 1' in pg.text_content('#acq-top'))
    t('the correction is logged on the company', ev(pg, "acq.acts.filter(function(a){return /Status check/.test(a.note)&&/Alpha Co/.test(a.note)}).length") == 1)
    pg.click('#acq-status-banner button:has-text("Dismiss")')
    t('the notice can be dismissed; the correction stays logged', pg.locator('#acq-status-banner').count() == 0 and ev(pg, "acq.acts.filter(function(a){return /Status check/.test(a.note)}).length") == 1)
    # the other way: a restore brings back a Quotes tab won/lost that Companies does not support
    ev(pg, "(function(){qtFind(%s).status='won';qtSave();})()" % json.dumps(C))
    pg.reload(); pg.wait_for_function("typeof acq!=='undefined'&&acqReady")
    open_tab(pg, 'companies')
    t('a Quotes tab Won that Companies does not support is corrected back to Waiting and flagged', st(C) == 'sent' and derived_ok(pg) and 'Quote status corrected: 1' in pg.text_content('#acq-top'))
    # restore (Replace) from an older state leaves them consistent
    old_acq = json.loads(ev(pg, "localStorage.getItem('ob-acq')"))
    for r in old_acq['quotes']:
        if r['legacyId'] == A:
            r['versions'] = [r['versions'][0]]; r['versions'][0]['status'] = 'sent'; r['versions'][0]['acceptedAt'] = ''
    pth = write_backup('old.json', old_acq)
    open_backup(pg); pg.set_input_files('#backup-file-input', pth); pg.wait_for_selector('#backup-preview-summary >> text=will restore'); pg.click('#backup-restore-replace-btn'); pg.wait_for_timeout(1800); pg.wait_for_function("typeof acq!=='undefined'&&acqReady")
    t('after a Replace restore that predates the acceptance, Companies and the Quotes tab agree again', derived_ok(pg) and st(A) == 'sent')
    # linking a Won / Lost legacy quote
    dq = ev(pg, "acqCreateCompany('Delta Won','');acqFindCo(acq,'Delta Won').id"); do = mk_op(pg, dq, 'Delta deal')
    ev(pg, "acqQuoteOpen(%s,'qt-1700000000034')" % json.dumps(do))
    t('linking a quote already marked Won in the Quotes tab asks for the acceptance date', pg.is_visible('#acq-q-accbox'))
    pg.click('#acq-modal button:has-text("Save quote")')
    t('without a date it is not saved', ev(pg, "acqQuoteByLegacy('qt-1700000000034')") is None)
    pg.fill('#acq-q-acc', d(-2)); pg.click('#acq-modal button:has-text("Save quote")')
    t('with a date it is saved as accepted, so both sides say Won', ev(pg, "acqAcceptedVer(acqQuoteByLegacy('qt-1700000000034')).acceptedAt") == d(-2) and st('qt-1700000000034') == 'won' and derived_ok(pg))
    eo = ev(pg, "acqCreateCompany('Echo Lost','');acqFindCo(acq,'Echo Lost').id"); eop = mk_op(pg, eo, 'Echo deal')
    ev(pg, "acqQuoteOpen(%s,'qt-1700000000035')" % json.dumps(eop)); pg.click('#acq-modal button:has-text("Save quote")')
    t('linking a quote marked Lost is refused with an explanation, nothing changes', ev(pg, "acqQuoteByLegacy('qt-1700000000035')") is None and st('qt-1700000000035') == 'lost')
    pg.context.close()

    # =====================================================================  5. Test records and the release check
    pg = new_page(b); start_empty(pg); open_tab(pg, 'companies')
    pg.fill('#acq-new-name', 'Real Prospect Inc'); pg.click('#acq-top ~ .card button:has-text("Add company"), button:has-text("Add company")')
    pg.fill('#acq-new-name', 'ZZ TEST Acme'); pg.check('#acq-new-test'); pg.click('button:has-text("Add company")')
    real = ev(pg, "acqFindCo(acq,'Real Prospect Inc').id"); tst = ev(pg, "acqFindCo(acq,'ZZ TEST Acme').id")
    t('a test company is labelled TEST in the list', ev(pg, "acqFindCo(acq,'ZZ TEST Acme').test") is True and 'TEST' in pg.text_content('#acq-list'))
    t('a normal company is not a test', ev(pg, "acqFindCo(acq,'Real Prospect Inc').test") is False)
    t('companies count excludes the test company and the page says tests are left out', ev(pg, "acqCounts().companies") == 1 and ev(pg, "acqCounts().tests") == 1 and 'left out of every number above' in pg.text_content('#acq-top'))
    ct = mk_ct(pg, tst, 'Test Person'); op = mk_op(pg, tst, 'Test deal', ct)
    ev(pg, "acqCtx={kind:'x'};")
    ev(pg, "acq.acts.push({id:acqNewId('ac'),at:atlDateStr(),companyId:%s,oppId:%s,contactId:%s,kind:'attempt',channel:'email',outcome:'conversation',note:'test',spoke:true,need:true,qualified:true,createdAt:Date.now()});acqSave();acqRefresh();" % (json.dumps(tst), json.dumps(op), json.dumps(ct)))
    qq = quote_add(pg, op, 500, 'suv', d(-1), 'A', 'B', '', 'trip'); quote_accept(pg, qq, 1, TODAY)
    booking_add(pg, op, qq, d(-1), '09:00'); bk = ev(pg, "acq.bookings[0].id")
    ev(pg, "acqBookingDone(%s)" % json.dumps(bk))
    ev(pg, "acqSetProjected(%s,'900')" % json.dumps(op))
    c = ev(pg, "acqCounts()"); v = ev(pg, "acqValues()")
    t('attempts, replies and qualified conversations on a test company are not counted', c['attempts'] == 0 and c['replies'] == 0 and c['qualified'] == 0 and c['contacts'] == 0)
    t('accepted, completed and projected value of a test company are not counted', v['accepted'] == 0 and v['completed'] == 0 and v['projected'] == 0 and v['done'] == 0)
    t('the test company\'s own page still shows its values', ev(pg, "acqValueOf([acqOp(%s)]).completed" % json.dumps(op)) == 500)
    open_tab(pg, 'today'); t('Today marks the test record', '[TEST]' in sec(pg, 'Acquisition'))
    ev(pg, "acqToggleTest(%s)" % json.dumps(tst))
    t('removing the test label makes it count', ev(pg, "acqCounts().attempts") == 1 and ev(pg, "acqValues().completed") == 500)
    ev(pg, "acqToggleTest(%s)" % json.dumps(tst))
    t('and marking it as a test again takes it out', ev(pg, "acqCounts().attempts") == 0 and ev(pg, "acqValues().completed") == 0)
    t('the test flag survives backup, reload and clean', ev(pg, "acqClean(JSON.parse(localStorage.getItem('ob-acq'))).companies.filter(function(c){return c.test}).length") == 1 and ev(pg, "acqCheck(acq)") == '')
    t('a hostile test value is treated as not a test', ev(pg, "acqClean({companies:[{id:'co-aa1',name:'X',test:'yes'}]}).companies[0].test") is False)
    # release check
    open_backup(pg); pg.wait_for_function("document.getElementById('acq-rel-check').textContent.indexOf('Matches')!==-1", timeout=8000)
    t('the Data & Backup screen shows the loaded release and that it matches the server file', 'release 1c' in pg.text_content('#backup-info') and 'Matches this page' in pg.text_content('#acq-rel-check'))
    pg.context.close()
    pg = new_page(b); pg.route('**/version.json', lambda r: r.fulfill(status=200, content_type='application/json', body='{"release":"1b","built":"2026-01-01"}'))
    open_backup(pg); pg.wait_for_function("document.getElementById('acq-rel-check').textContent.indexOf('Mismatch')!==-1", timeout=8000)
    t('a stale page is called out: mismatch with instructions to reload before testing', 'Reload with the cache cleared' in pg.text_content('#acq-rel-check') and 'server file says 1b' in pg.text_content('#acq-rel-check'))
    pg.context.close()
    pg = new_page(b); pg.route('**/version.json', lambda r: r.fulfill(status=404, body='no'))
    open_backup(pg); pg.wait_for_function("document.getElementById('acq-rel-check').textContent.indexOf('Could not read')!==-1", timeout=8000)
    t('if the server file cannot be read the screen says the live check is not valid yet', 'Do not treat any live check as valid' in pg.text_content('#acq-rel-check'))
    pg.context.close()
    b.close()

print('FAILS: %d' % fails)
raise SystemExit(1 if fails else 0)

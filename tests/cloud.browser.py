# Real-browser test of Cloud Sync against an in-memory FAKE Supabase (no real database is contacted).
import json, sys, time, re
from playwright.sync_api import sync_playwright
fails=0
def t(n,c):
    global fails
    print(('PASS: ' if c else 'FAIL: ')+n)
    if not c: fails+=1
class Fake:
    def __init__(s): s.rows={}; s.writes=0; s.down=False; s.ts=0; s.pw='right-pass'
    def handle(s,route):
        req=route.request; u=req.url
        if s.down: return route.abort()
        if '/auth/v1/token' in u:
            body=json.loads(req.post_data or '{}')
            if 'grant_type=password' in u and body.get('password')!=s.pw:
                return route.fulfill(status=400,content_type='application/json',body='{"error":"invalid_grant"}')
            return route.fulfill(status=200,content_type='application/json',body=json.dumps({"access_token":"tok","refresh_token":"ref","expires_in":3600,"user":{"id":"u1","email":"pope@odysseyblack.com"}}))
        if '/rest/v1/ob_store' in u:
            if req.method=='GET':
                return route.fulfill(status=200,content_type='application/json',body=json.dumps(list(s.rows.values())))
            if req.method=='POST':
                for r in json.loads(req.post_data):
                    s.ts+=1; s.writes+=1
                    s.rows[r['key']]={"key":r['key'],"value":r['value'],"updated_at":f"2026-10-14T12:00:{s.ts:02d}Z"}
                return route.fulfill(status=200,content_type='application/json',body=json.dumps([s.rows[r['key']] for r in json.loads(req.post_data)]))
        route.continue_()
PIPE=[{"name":"Alice","company":"Acme"},{"name":"Bob","company":"Beta"}]
def sign_in(pg):
    pg.click('#cloud-chip'); pg.fill('#cloud-email','pope@odysseyblack.com'); pg.fill('#cloud-pass','right-pass'); pg.click('#cloud-signed-out button')
with sync_playwright() as p:
    b=p.chromium.launch()
    def nctx(**kw):
        c=b.new_context(**kw); c.add_init_script("try{localStorage.setItem('ob-cloud-gate',JSON.stringify({at:'2026-10-21',note:'test gate'}))}catch(e){}"); return c
    fake=Fake()
    # --- Release 1c gate: without a recorded verification, sign-in is blocked and never reaches the network
    cN=b.new_context(viewport={'width':1440,'height':900}); N=cN.new_page(); hits=[]
    N.route(re.compile(r'supabase\.co'),lambda r:(hits.append(1),r.continue_()))
    N.goto('http://localhost:8765/index.html'); N.click('#cloud-chip')
    t('gate: Cloud Sync is shown as blocked until verification is recorded','Cloud Sync is blocked' in N.inner_text('#cloud-gate'))
    N.fill('#cloud-email','pope@odysseyblack.com'); N.fill('#cloud-pass','right-pass'); N.click('#cloud-signed-out button'); N.wait_for_timeout(400)
    t('gate: sign-in refused with a plain message, no request sent, no session stored','blocked' in N.inner_text('#cloud-msg') and not hits and N.evaluate("localStorage.getItem('ob-cloud-session')") is None)
    N.click('#cloud-gate button'); 
    t('gate: recording needs the box ticked and a note',N.evaluate("localStorage.getItem('ob-cloud-gate')") is None)
    N.check('#cloud-gate-ok'); N.fill('#cloud-gate-note','RLS applied; second account cannot read rows; sign-up restricted'); N.click('#cloud-gate button')
    t('gate: verification recorded and shown',N.evaluate("localStorage.getItem('ob-cloud-gate')") is not None and 'verification recorded' in N.inner_text('#cloud-gate'))
    t('gate: the gate record itself is never synced or in the backup',N.evaluate("APPROVED_BACKUP_KEYS.indexOf('ob-cloud-gate')===-1&&CLOUD_KEYS.indexOf('ob-cloud-gate')===-1"))
    cN.close()
    # --- Device A: has data, cloud empty -> migration push
    ctxA=nctx(viewport={'width':390,'height':844}); A=ctxA.new_page(); errs=[]
    A.on('pageerror',lambda e:errs.append(str(e))); A.route(re.compile(r'supabase\.co'),fake.handle)
    A.goto('http://localhost:8765/index.html'); A.evaluate("localStorage.setItem('ob-pipeline',JSON.stringify(%s))"%json.dumps(PIPE)); A.reload()
    t('chip starts as Cloud: off','off' in A.text_content('#cloud-chip'))
    A.click('#cloud-chip'); A.fill('#cloud-email','pope@odysseyblack.com'); A.fill('#cloud-pass','wrong'); A.click('#cloud-signed-out button'); A.wait_for_timeout(400)
    t('wrong password refused with plain message','failed' in A.inner_text('#cloud-msg') and A.evaluate("localStorage.getItem('ob-cloud-session')") is None)
    t('password field cleared after attempt',A.input_value('#cloud-pass')=='')
    A.fill('#cloud-pass','right-pass'); A.click('#cloud-signed-out button'); A.wait_for_function("document.getElementById('cloud-chip').textContent.includes('saved')")
    t('existing device data uploaded on first sign-in',fake.rows.get('ob-pipeline',{}).get('value')==PIPE)
    t('local data untouched',A.evaluate("JSON.parse(localStorage.getItem('ob-pipeline')).length")==2)
    t('session/meta keys never synced to cloud',not any(k.startswith('ob-cloud') for k in fake.rows))
    w=fake.writes
    # save triggers push
    A.evaluate("saveJSON('ob-gatekeepers',[{id:1,name:'Pat'}])"); A.wait_for_timeout(2500)
    t('new save pushed automatically',fake.rows.get('ob-gatekeepers',{}).get('value')==[{"id":1,"name":"Pat"}] and fake.writes>w)
    # offline: save stays local, chip warns, then recovers
    fake.down=True; A.evaluate("saveJSON('ob-gatekeepers',[{id:1,name:'Pat'},{id:2,name:'Quinn'}])"); A.wait_for_timeout(2500)
    t('offline: data kept locally',A.evaluate("JSON.parse(localStorage.getItem('ob-gatekeepers')).length")==2)
    t('offline: chip says not synced','not synced' in A.text_content('#cloud-chip'))
    fake.down=False; A.evaluate("saveJSON('ob-gatekeepers',[{id:1,name:'Pat'},{id:2,name:'Quinn'}])"); A.wait_for_timeout(2600)
    t('back online: change reaches cloud',len(fake.rows['ob-gatekeepers']['value'])==2)
    # --- Device B: empty -> pulls cloud data, reloads
    ctxB=nctx(viewport={'width':1440,'height':900}); B=ctxB.new_page(); B.route(re.compile(r'supabase\.co'),fake.handle)
    B.goto('http://localhost:8765/index.html'); sign_in(B); B.wait_for_function("(JSON.parse(localStorage.getItem('ob-pipeline')||'[]')).length===2",timeout=8000)
    t('empty device receives cloud data',B.evaluate("JSON.parse(localStorage.getItem('ob-pipeline')).length")==2)
    # --- Device C: different data on both sides, no history -> conflict, nothing overwritten
    ctxC=nctx(viewport={'width':390,'height':844}); C=ctxC.new_page(); C.route(re.compile(r'supabase\.co'),fake.handle)
    C.goto('http://localhost:8765/index.html'); C.evaluate("localStorage.setItem('ob-pipeline',JSON.stringify([{name:'Zed'}]))"); C.reload()
    w=fake.writes; sign_in(C); C.wait_for_selector('#cloud-conflicts .card')
    t('conflict shown with both counts','1 item' in C.inner_text('#cloud-conflicts') and '2 item' in C.inner_text('#cloud-conflicts'))
    t('conflict did not write to cloud',fake.writes==w and len(fake.rows['ob-pipeline']['value'])==2)
    t('conflict did not change device data',C.evaluate("JSON.parse(localStorage.getItem('ob-pipeline')).length")==1)
    C.evaluate("saveJSON('ob-radar',{seen:['x'],watch:{},sprintStart:null,sprintDone:{},hotels:{}})"); C.wait_for_timeout(2300)
    t('no auto-push while conflict unresolved',fake.writes==w)
    C.click('#cloud-conflicts button.btn-outline'); C.wait_for_function("(JSON.parse(localStorage.getItem('ob-pipeline')||'[]')).length===2",timeout=8000)
    t('"Use cloud" applies cloud version',True)
    t('recovery snapshot saved before change',C.evaluate("Object.keys(localStorage).some(function(k){return k.indexOf('ob-pre-restore-snapshot-')===0})"))
    # sign out stops syncing
    A.click('#cloud-signed-in button.btn-ghost'); w=fake.writes
    A.evaluate("saveJSON('ob-gatekeepers',[{id:9}])"); A.wait_for_timeout(2300)
    t('signed out: no further cloud writes',fake.rows['ob-gatekeepers']['value']!=[{'id':9}] and A.evaluate("localStorage.getItem('ob-cloud-session')") is None)
    t('backup allowlist excludes session keys',not A.evaluate("APPROVED_BACKUP_KEYS.some(function(k){return k.indexOf('ob-cloud')===0})"))
    t('no page errors',not errs)
    A.screenshot(path='tests/cloud-390.png')
    b.close()
print('FAILS',fails); sys.exit(1 if fails else 0)

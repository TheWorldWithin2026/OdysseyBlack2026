# Real-browser test of Market Radar company research (server response mocked).
import json
from playwright.sync_api import sync_playwright
fails=0
def t(n,c):
    global fails
    print(('PASS: ' if c else 'FAIL: ')+n)
    if not c: fails+=1
PROFILE={'website':{'url':'https://www.acme.example','source':'https://www.acme.example/about'},
 'address':{'text':'100 Main St, Alpharetta, GA 30009','source':'https://www.acme.example/contact'},
 'phone':{'text':'(770) 555-0100','source':'https://www.acme.example/contact'},
 'people':[{'name':'Jane Roe','title':'Chief Executive Officer','source':'https://www.acme.example/about'}],
 'news':[{'title':'Acme opens Alpharetta office','url':'https://news.example/acme'}],
 'summary':'Acme makes widgets and opened a North American office in Alpharetta.'}
with sync_playwright() as p:
    b=p.chromium.launch()
    for w,h in [(390,844),(1440,900)]:
        ctx=b.new_context(viewport={'width':w,'height':h}); pg=ctx.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.on('dialog',lambda d:d.accept())
        reqs=[]; resp={'status':200,'body':{'status':'OK','profile':PROFILE,'dropped':0}}
        def handler(route):
            reqs.append(json.loads(route.request.post_data or '{}'))
            route.fulfill(status=resp['status'],content_type='application/json',body=json.dumps(resp['body']))
        pg.route('**/.netlify/functions/company-research',handler)
        pg.goto('http://localhost:8765/index.html'); pg.click('.tab[onclick*="radar"]')
        t(f'[{w}] Company Research card is on the Radar with a Research button',pg.is_visible('#rsch-name') and pg.is_visible('#rsch-btn'))
        pg.fill('#rsch-name','x'); pg.click('#rsch-btn')
        t(f'[{w}] too-short or odd names are refused without calling the server',len(reqs)==0 and 'letters and numbers' in pg.text_content('#rsch-status'))
        pg.fill('#rsch-name','Acme <b>Corp</b>'); pg.click('#rsch-btn'); t(f'[{w}] markup in the name is refused',len(reqs)==0)
        pg.fill('#rsch-name','Acme Corp'); pg.click('#rsch-btn')
        pg.wait_for_selector('#rsch-result >> text=Acme Corp')
        t(f'[{w}] request carries only company and city (Atlanta for All areas)',reqs==[{'company':'Acme Corp','city':'Atlanta'}])
        card=pg.text_content('#rsch-result')
        t(f'[{w}] card shows website, address, phone, executive with title, and news',all(x in card for x in ['acme.example','100 Main St, Alpharetta, GA 30009','(770) 555-0100','Jane Roe','Chief Executive Officer','Acme opens Alpharetta office']))
        t(f'[{w}] card says unverified and shows the summary','unverified' in card and 'North American office' in card)
        hrefs=pg.eval_on_selector_all('#rsch-result a','els=>els.map(e=>[e.href,e.target,e.rel])')
        t(f'[{w}] every link is http(s), opens a new tab and has noopener',len(hrefs)>=6 and all(h[0].startswith('http') and h[1]=='_blank' and 'noopener' in h[2] for h in hrefs))
        t(f'[{w}] each fact carries its source link','source: acme.example' in card)
        t(f'[{w}] status explains it is unverified','confirm it before outreach' in pg.text_content('#rsch-status'))
        # area city
        pg.click('#radar-area-chips button:has-text("Alpharetta")'); pg.fill('#rsch-name','Beta Inc'); pg.click('#rsch-btn'); pg.wait_for_selector('#rsch-result >> text=Beta Inc')
        t(f'[{w}] research in the Alpharetta area sends city Alpharetta',reqs[-1]['city']=='Alpharetta')
        # replace same name, saved list, persistence
        pg.fill('#rsch-name','beta inc'); pg.click('#rsch-btn'); pg.wait_for_function("rschState.items.length===2 && rschState.items[0].name==='beta inc'")
        t(f'[{w}] researching the same company again replaces it (2 saved, not 3)',pg.evaluate('rschState.items.length')==2)
        pg.reload(); pg.click('.tab[onclick*="radar"]')
        t(f'[{w}] saved research persists across reload',pg.evaluate('rschState.items.length')==2 and 'Acme Corp' in pg.text_content('#rsch-saved'))
        pg.click('#rsch-saved button:has-text("View") >> nth=1')
        t(f'[{w}] View shows the saved profile again',pg.evaluate('rschState.items.length')==2 and '(770) 555-0100' in pg.text_content('#rsch-result'))
        pg.click('#rsch-saved button:has-text("Delete") >> nth=0')
        t(f'[{w}] delete needs a second click',pg.evaluate('rschState.items.length')==2)
        pg.click('#rsch-saved button:has-text("Click again")'); t(f'[{w}] second click deletes',pg.evaluate('rschState.items.length')==1)
        # gatekeeper hand-off
        pg.evaluate("rschView(rschState.items[0].id)")
        pg.click('#rsch-result button:has-text("Find Gatekeepers")')
        t(f'[{w}] Find Gatekeepers from the card opens the finder with the company filled',pg.input_value('#gk-company')==pg.evaluate('rschState.items[0].name') and pg.is_visible('#gk-xray-list'))
        pg.click('.tab[onclick*="radar"]')
        # watchlist and headline buttons
        n=len(reqs)
        pg.click('#radar-watchlist button:has-text("Research") >> nth=0'); pg.wait_for_function("rschBusy===false")
        t(f'[{w}] watchlist Research button sends that company',len(reqs)==n+1 and len(reqs[-1]['company'])>=2)
        pg.evaluate("radarLastItems=[{id:'t1',title:'Keter opens HQ',url:'https://news.example/k',source:'News',publishedAt:'2026-10-02T00:00:00Z',areas:['gwinnett']}];renderRadarScan()")
        pg.click('#radar-scan-list button:has-text("Research")'); t(f'[{w}] headline Research with no company typed asks for the name',len(reqs)==n+1)
        pg.fill('#radar-co-0','Keter'); pg.click('#radar-scan-list button:has-text("Research")'); pg.wait_for_function("rschBusy===false")
        t(f'[{w}] headline Research sends the typed company and the headline area (Gwinnett County)',reqs[-1]=={'company':'Keter','city':'Gwinnett County'})
        # errors
        for code,status,frag in [('web_search_not_enabled',502,'not turned on'),('timeout',504,'too long'),('rate_limited',429,'Too many lookups'),('daily_cap',429,'daily lookup limit'),('weird',502,'did not work')]:
            resp['status']=status; resp['body']={'error':code}
            pg.fill('#rsch-name','Gamma LLC'); pg.click('#rsch-btn'); pg.wait_for_function("rschBusy===false")
            t(f'[{w}] error {code} gives a plain message',frag in pg.text_content('#rsch-status'))
        t(f'[{w}] failed lookups save nothing new',pg.evaluate("rschState.items.every(function(x){return x.name!=='Gamma LLC';})"))
        pg.unroute('**/.netlify/functions/company-research'); pg.route('**/.netlify/functions/company-research',lambda r:r.abort())
        pg.fill('#rsch-name','Gamma LLC'); pg.click('#rsch-btn'); pg.wait_for_function("rschBusy===false")
        t(f'[{w}] network failure is handled and the button works again',('did not work' in pg.text_content('#rsch-status')) and not pg.is_disabled('#rsch-btn') and not errs)
        # nothing found
        pg.unroute('**/.netlify/functions/company-research')
        pg.route('**/.netlify/functions/company-research',lambda r:r.fulfill(status=200,content_type='application/json',body=json.dumps({'status':'OK','profile':{'website':None,'address':None,'phone':None,'people':[],'news':[],'summary':''},'dropped':2})))
        pg.fill('#rsch-name','Delta Co'); pg.click('#rsch-btn'); pg.wait_for_selector('#rsch-result >> text=Delta Co')
        t(f'[{w}] empty result says nothing could be sourced, shows Not found, and notes dropped items','Nothing could be sourced' in pg.text_content('#rsch-status') and '2 items were left out' in pg.text_content('#rsch-status') and 'Not found in public sources' in pg.text_content('#rsch-result'))
        # double click sends one request
        pg.unroute('**/.netlify/functions/company-research'); cnt=[0]
        def slow(route):
            cnt[0]+=1; import time; time.sleep(0.6); route.fulfill(status=200,content_type='application/json',body=json.dumps({'status':'OK','profile':PROFILE,'dropped':0}))
        pg.route('**/.netlify/functions/company-research',slow)
        pg.fill('#rsch-name','Echo Co'); pg.evaluate("rschGo();rschGo();rschGo()"); pg.wait_for_function("rschBusy===false")
        t(f'[{w}] repeated clicks while busy send one request',cnt[0]==1)
        # layout
        pg.unroute('**/.netlify/functions/company-research')
        long='x'*180
        pg.route('**/.netlify/functions/company-research',lambda r:r.fulfill(status=200,content_type='application/json',body=json.dumps({'status':'OK','profile':{'website':{'url':'https://www.acme.example/'+long,'source':'https://www.acme.example/'+long},'address':{'text':long,'source':'https://a.example/'+long},'phone':None,'people':[],'news':[{'title':long,'url':'https://n.example/'+long}],'summary':long},'dropped':0})))
        pg.fill('#rsch-name','Foxtrot Co'); pg.click('#rsch-btn'); pg.wait_for_selector('#rsch-result >> text=Foxtrot Co')
        t(f'[{w}] long values do not cause horizontal scroll',pg.evaluate("document.documentElement.scrollWidth<=window.innerWidth+1"))
        t(f'[{w}] no page errors',not errs)
        ctx.close()
    # hostile server response and hostile stored data
    ctx=b.new_context(viewport={'width':1200,'height':900}); pg=ctx.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
    bad={'website':{'url':'javascript:window.__pwn=1','source':'https://ok.example/a'},'address':{'text':'<img src=x onerror=window.__pwn=1>','source':'https://ok.example/b'},'phone':{'text':'555','source':'javascript:alert(1)'},
         'people':[{'name':'<script>window.__pwn=1</script>Ann Lee','title':'<b>CEO</b>','source':'https://ok.example/c'},{'name':'X','source':'https://ok.example/d'}],'news':[{'title':'ok','url':'data:text/html,<script>1</script>'},{'title':'fine news','url':'https://ok.example/e'}],'summary':'<svg onload=window.__pwn=1>'}
    pg.route('**/.netlify/functions/company-research',lambda r:r.fulfill(status=200,content_type='application/json',body=json.dumps({'status':'OK','profile':bad,'dropped':0})))
    pg.goto('http://localhost:8765/index.html'); pg.click('.tab[onclick*="radar"]'); pg.fill('#rsch-name','Evil Co'); pg.click('#rsch-btn'); pg.wait_for_selector('#rsch-result >> text=Evil Co')
    s=pg.evaluate("rschState.items[0]")
    t('hostile profile: bad URLs and unsourced facts are dropped, text is stripped of markup',s['website'] is None and s['phone'] is None and len(s['people'])==1 and len(s['news'])==1 and '<' not in json.dumps(s['address']) and '<' not in s['summary'] and '<' not in s['people'][0]['name'])
    t('hostile profile executes nothing and links stay http(s)',pg.evaluate("window.__pwn")is None and all(h.startswith('http') for h in pg.eval_on_selector_all('#rsch-result a','els=>els.map(e=>e.href)')))
    hostile={'items':[{'id':'rp-1','name':'<img src=x onerror=window.__pwn=1>','city':'x'*200,'at':'not-a-date','website':{'url':'javascript:1','source':'https://a.example'},'people':'oops','news':[None,5]},None,5,{'id':'rp-9999999','name':'Real Co','at':'2026-10-01'},{'id':'rp-9999999','name':'Dup Co'}]}
    pg.evaluate("localStorage.setItem('ob-research',%s)"%json.dumps(json.dumps(hostile))); pg.reload(); pg.click('.tab[onclick*="radar"]')
    s=pg.evaluate("rschState.items")
    t('hostile stored data: junk dropped, ids unique, dates and lengths sanitized',len(s)==3 and len(set(x['id'] for x in s))==3 and s[0]['at']=='' and len(s[0]['city'])<=40 and s[0]['website'] is None and s[0]['people']==[] and s[0]['news']==[])
    t('hostile stored names are escaped, not executed',pg.evaluate("window.__pwn")is None and not errs)
    t('ob-research is an approved backup/sync key with a label',pg.evaluate("APPROVED_BACKUP_KEYS.indexOf('ob-research')!==-1 && cloudKeyLabel('ob-research')==='Company research'"))
    ctx.close(); b.close()
print('ALL PASSED' if not fails else '%d FAILED'%fails)
raise SystemExit(1 if fails else 0)

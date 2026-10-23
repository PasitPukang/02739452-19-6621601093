// Local Chromium DevTools check: no Selenium, external browser package or uploaded screenshots.
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
import path from 'node:path';

const root=process.cwd(), output=path.join(root,'audit','screenshots');
await mkdir(output,{recursive:true});
const target=await (await fetch('http://127.0.0.1:9223/json/new?about:blank',{method:'PUT'})).json();
const socket=new WebSocket(target.webSocketDebuggerUrl), pending=new Map();let sequence=0;
const errors=[];
await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true})});
socket.addEventListener('message',event=>{const message=JSON.parse(event.data);if(message.id){const waiter=pending.get(message.id);pending.delete(message.id);if(message.error)waiter.reject(new Error(message.error.message));else waiter.resolve(message.result)}else if(message.method==='Runtime.exceptionThrown'){const detail=message.params.exceptionDetails;errors.push({text:detail.text,description:detail.exception?.description,url:detail.url})}});
function call(method,params={}){return new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}))})}
async function evaluate(expression){const result=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(result.exceptionDetails)throw new Error(result.exceptionDetails.text);return result.result.value}
async function wait(expression,label){for(let attempt=0;attempt<100;attempt++){if(await evaluate(expression))return;await new Promise(r=>setTimeout(r,250))}throw new Error('Timed out: '+label)}
async function navigate(url){await call('Page.navigate',{url});await wait("document.readyState==='complete'",url)}
async function screenshot(name){const result=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await writeFile(path.join(output,name),Buffer.from(result.data,'base64'))}
await call('Page.enable');await call('Runtime.enable');
await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1050,deviceScaleFactor:1,mobile:false});

if(process.argv.includes('--pdf-only')){
  await navigate(pathToFileURL(path.join(root,'submission','summary.html')).href);
  await wait('[...document.images].every(i=>i.complete)', 'report images');
  const pages=await evaluate("[...document.querySelectorAll('.page')].map(p=>({height:p.getBoundingClientRect().height,contentBottom:p.querySelector('.footer').previousElementSibling.getBoundingClientRect().bottom-p.getBoundingClientRect().top,footerTop:p.querySelector('.footer').getBoundingClientRect().top-p.getBoundingClientRect().top}))");
  assert.equal(pages.length,3);
  assert.ok(pages.every(p=>p.height<1032&&p.contentBottom<=p.footerTop),'Report overflow: '+JSON.stringify(pages));
  const result=await call('Page.printToPDF',{printBackground:true,preferCSSPageSize:true});
  const pdf=Buffer.from(result.data,'base64');
  assert.equal((pdf.toString('latin1').match(/\/Type \/Page\b/g)||[]).length,3,'PDF must be three pages');
  await writeFile(path.join(root,'submission','19_6621601093_summary.pdf'),pdf);
  console.log('PDF written: submission/19_6621601093_summary.pdf');
}else{
  await navigate('http://localhost:8091');
  await wait("document.querySelector('#k-total')?.textContent==='151'",'151 actual database records');
  assert.equal(await evaluate("document.querySelectorAll('#pokemon-rows tr').length"),20);
  await screenshot('dashboard.png');
  await evaluate("document.querySelector('#next').click()");
  assert.match(await evaluate("document.querySelector('#page-info').textContent"),/21/);
  await evaluate("document.querySelector('#type').value='fire';document.querySelector('#type').dispatchEvent(new Event('input',{bubbles:true}))");
  await wait("Number(document.querySelector('#k-filtered').textContent)>0&&Number(document.querySelector('#k-filtered').textContent)<151",'type filter');
  await evaluate("document.querySelector('#filters').reset();const q=document.querySelector('input[name=q]');q.value='Pikachu';q.dispatchEvent(new Event('input',{bubbles:true}))");
  await wait("document.querySelector('#k-filtered').textContent==='1'",'name filter');
  assert.match(await evaluate("document.querySelector('#pokemon-rows').textContent"),/Pikachu/);
  assert.equal(await evaluate("fetch('/api/pokemon?sort=invalid').then(r=>r.status)"),400);
  await evaluate("document.querySelector('#filters').reset();document.querySelector('#refresh').click()");
  await wait("document.querySelector('#k-filtered').textContent==='151'",'filter reset');
  await evaluate("document.querySelector('#catalog').scrollIntoView()");
  await screenshot('catalog.png');
  await evaluate("document.querySelector('#pipeline').scrollIntoView()");
  await screenshot('pipeline.png');
  await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  await evaluate('scrollTo(0,0)');
  assert.equal(await evaluate('document.documentElement.scrollWidth<=innerWidth'),true,'mobile page overflow');
  await screenshot('dashboard-mobile.png');
  assert.equal(errors.length,0,'Dashboard exceptions: '+JSON.stringify(errors));
  await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1050,deviceScaleFactor:1,mobile:false});
  const env=await readFile('.env','utf8');
  const password=env.split(/\r?\n/).find(line=>line.startsWith('AIRFLOW_ADMIN_PASSWORD=')).split('=').slice(1).join('=');
  await navigate('http://localhost:8089/login/');
  await wait("document.querySelector('input[name=username]')||!location.pathname.includes('/login')",'Airflow login');
  if(await evaluate("Boolean(document.querySelector('input[name=username]'))")){
    await evaluate(`document.querySelector('input[name=username]').value='admin';const passwordField=document.querySelector('input[name=password]');passwordField.value=${JSON.stringify(password)};passwordField.closest('form').requestSubmit()`);
    await wait("!location.pathname.includes('/login')",'authenticated Airflow');
  }
  const evidence=JSON.parse(await readFile('audit/pokemon_validation.json','utf8'));
  const run=evidence.cases.find(c=>c.name==='final').run.run_id;
  const base='http://localhost:8089/dags/pokemon_pipeline/grid?dag_run_id='+encodeURIComponent(run);
  await navigate(base+'&tab=graph');
  await wait("document.body.textContent.includes('pokemon_pipeline')",'Airflow DAG graph');
  await new Promise(r=>setTimeout(r,3500));
  await screenshot('airflow-graph.png');
  await navigate('http://localhost:8089/dags/pokemon_pipeline/grid');
  await new Promise(r=>setTimeout(r,3000));
  await screenshot('airflow-grid.png');
  await writeFile('audit/browser_validation.json',JSON.stringify({dashboard_checks:'passed',canonical_rows:151,pagination:true,type_filter:true,name_filter:true,invalid_filter_http_status:400,mobile_overflow:false,airflow_authenticated:true,airflow_runtime_exceptions:errors},null,2));
  console.log('Browser checks passed: 151 rows, pagination, type/name filters, invalid-filter 400, mobile layout, authenticated Airflow screenshots');
}
socket.close();

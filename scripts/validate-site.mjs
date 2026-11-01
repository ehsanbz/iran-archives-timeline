import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const read=p=>fs.readFileSync(p,'utf8');
const layout=read('_layouts/dashboard.html');
const tabs=['overview','timeline','map','topics','people','compare','sources'];
const checkHtml=html=>{
 for(const tab of tabs){assert.ok(html.includes(`id="tab-${tab}"`),`Missing tab ${tab}`);assert.ok(html.includes(`id="panel-${tab}"`),`Missing panel ${tab}`);}
 for(const token of ['buildGeography','bindMapInteractions','solarMonthKey','showPerson','dossierBrowser','Vazirmatn','data/archive.json','validateArchive'])assert.ok(html.includes(token),`Missing feature ${token}`);
 assert.match(html,/data:font\/woff2;base64,/);
 assert.doesNotMatch(html,/<script[^>]+src=/i);
};
checkHtml(layout);
assert.ok(!fs.existsSync('.nojekyll'),'Do not bypass the protected Jekyll entry point');
assert.match(read('_config.yml'),/^  - index\.html$/m,'Legacy index must be excluded');
assert.match(read('home.html'),/layout: dashboard\npermalink: \/index\.html/);
assert.match(read('dashboard.html'),/layout: dashboard\npermalink: \/dashboard\.html/);
const payload=JSON.parse(read('data/archive.json'));
const script=layout.match(/<script>([\s\S]*?)<\/script>/)[1];
new vm.Script(script);
function element(id){return {id,value:'',checked:true,hidden:false,innerHTML:'',textContent:'',style:{},dataset:{},classList:{add(){},remove(){}},addEventListener(){},setAttribute(){},getAttribute(){return null},querySelectorAll(){return []},focus(){},scrollIntoView(){}};}
async function app(response,protocol='file:'){
 const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,element(id));return elements.get(id)};
 const tabElements=tabs.map(t=>Object.assign(get('tab-'+t),{dataset:{tab:t}}));
 const panels=tabs.map(t=>get('panel-'+t));
 const doc={baseURI:'https://example.test/archive/',body:element('body'),activeElement:element('focus'),addEventListener(){},querySelector:s=>get(s.startsWith('#')?s.slice(1):s),querySelectorAll:s=>s==='.tab'?tabElements:s==='.panel'?panels:[]};
 const context=vm.createContext({Intl,Date,Map,Set,URL,AbortSignal,console:{warn(){},error(){}},document:doc,location:{protocol},fetch:async()=>({ok:true,json:async()=>response}),setTimeout,clearTimeout});
 // Expose a narrow test interface from the actual app, inside its async closure.
 const instrumented=script.replace("\n})().catch(error=>",'\nglobalThis.appTest={data,R,GEO,CASES,validateArchive,setTab,showPerson,solarMonthKey,solarMonthLabel,S};\n})().catch(error=>');
 await vm.runInContext(instrumented,context);
 assert.ok(context.appTest,'Dashboard initialization failed: '+get('data-health').textContent);
 return {api:context.appTest,get};
}
const offline=await app();
offline.api.validateArchive(payload);
const live=await app(payload,'https:');
assert.equal(live.api.data.length,payload.records.length);
assert.equal(live.get('data-health').textContent,'دریافت داده‌ها موفق بود');
for(const tab of tabs){live.api.setTab(tab);assert.ok(live.get('panel-'+tab).innerHTML.length>100,`Empty ${tab}`);}
live.api.showPerson('رضا پهلوی');assert.equal(live.get('person-overlay').hidden,false);assert.ok(live.get('sheetcontent').innerHTML.includes('منبع'));
assert.equal(live.api.solarMonthKey('2026-03-20'),'1404-12');
assert.equal(live.api.solarMonthKey('2026-03-21'),'1405-01');
assert.equal(live.api.solarMonthLabel('1402-07'),'مهر ۱۴۰۲');
const rome=Object.values(live.api.GEO).filter(ps=>ps.some(p=>p.id==='rome'));
assert.ok(rome.length>=6,'Rome references were lost');
for(const id of ['war12','war40','dey1404','hezbollah','hamas','houthis','promise1','promise2','promise3','promise4'])assert.ok(live.api.CASES.some(c=>c.id===id),'Missing dossier '+id);
// Simulate a later daily update without changing a byte of the UI template.
const next=structuredClone(payload),newRow=[...payload.records[0]];
newRow[1]='2027-01-05';newRow[3]='REGRESSION-TEST';newRow[5]='در رم';
next.records.push(newRow);next.asOf='2026-11-01';
const future=await app(next,'https:');
assert.equal(future.api.data.length,payload.records.length+1);
assert.ok(future.api.data.at(-1).places.some(p=>p.id==='rome'&&p.kind==='event'));
assert.equal(future.api.data.at(-1).monthKey,'1405-10');
assert.equal(future.api.data.at(-1).planned,true);
assert.throws(()=>live.api.validateArchive({...payload,records:payload.records.slice(1)}),/lost/);
assert.throws(()=>live.api.validateArchive({...payload,records:[...payload.records,payload.records[0]]}),/Duplicate/);
const invalid=await app({records:[]},'https:');
assert.equal(invalid.api.data.length,offline.api.data.length);
assert.match(invalid.get('data-health').textContent,/موفق نبود/);
if(process.argv[2]){const output=read(process.argv[2]+'/index.html');checkHtml(output);assert.ok(!output.includes('{% raw %}'),'Liquid was not processed');JSON.parse(read(process.argv[2]+'/data/archive.json'));}
console.log(JSON.stringify({passed:true,records:payload.records.length,dates:new Set(payload.records.map(r=>r[1])).size,tabs:tabs.length,romeReferences:rome.length,dataOnlyRefresh:true,newRowGeography:true,solarNewYear:true,invalidDataFallback:true,personSidebar:true}));

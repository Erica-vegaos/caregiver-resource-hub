/* Search acceptance tests v1.0.0. Synthetic fixtures; no coverage claims. */
const test = require('node:test');
const assert = require('node:assert/strict');
const S = require('../src/search.cjs');
const now = Date.parse('2026-11-14T09:00:00+08:00');
const base = {id:'a',title:'家屬支持團體',organizer:'臺北市協會',city:'台北市',mode:'實體',category:'支持團體',start:'2026-11-20T09:00:00+08:00',end:'2026-11-20T11:00:00+08:00',checked_at:'2026-11-14T08:00:00+08:00',freshness:'fresh',caregiver_eligible:true,registration_status:'unknown',event_status:'scheduled',eligibility:'精神疾病家屬',summary:'雙相情緒障礙症溝通與照顧'};
const e = changes => ({...base,...changes});
test('all 22 counties including offshore islands',()=>{assert.equal(new Set(S.CITIES).size,22);assert.ok(S.CITIES.includes('連江縣'));});
test('normalizes 台臺, fullwidth ASCII, case and diagnosis aliases',()=>{
 assert.equal(S.normalize('臺北 ＡＢＣ'), '台北 abc');
 assert.equal(S.search([base],{query:'躁鬱'} ,now).length,1);
 assert.equal(S.search([e({summary:'精神分裂症家屬交流'})],{query:'思覺失調'},now).length,1);
});
test('all terms must match, across fields',()=>{
 assert.equal(S.search([base],{query:'臺北 躁鬱 團體'},now).length,1);
 assert.equal(S.search([base],{query:'台北 失智'},now).length,0);
});
test('keyword matches summary, tags, category and venue',()=>{
 assert.equal(S.search([e({tags:['手足'],venue:'大安區'})],{query:'手足 大安區'},now).length,1);
});
test('title relevance outranks incidental description',()=>{
 const incidental=e({id:'b',start:'2026-11-15T09:00:00+08:00',summary:'家屬支持團體'});
 incidental.title='交流時光';
 assert.deepEqual(S.search([incidental,base],{query:'家屬支持團體'},now).map(x=>x.id),['a','b']);
});
test('no query sorts by actual event date',()=>{
 assert.deepEqual(S.search([base,e({id:'b',start:'2026-11-15T09:00:00+08:00'})],{},now).map(x=>x.id),['b','a']);
});
test('county and participation mode are independent filters',()=>{
 const online=e({id:'o',city:'全台',mode:'線上'}),hybrid=e({id:'h',city:'台中市',mode:'混合'});
 assert.deepEqual(S.search([base,online,hybrid],{city:'臺北市'},now).map(x=>x.id),['a']);
 assert.deepEqual(S.search([base,online,hybrid],{mode:'線上'},now).map(x=>x.id).sort(),['h','o']);
 assert.equal(S.search([base,online],{city:'台北市',mode:'線上'},now).length,0);
});
test('unknown fee/seats never become open and stale open not shown as confirmed',()=>{
 assert.equal(S.search([base],{registration:'open'},now).length,0);
 assert.equal(S.search([base],{registration:'unknown'},now).length,1);
 assert.equal(S.search([e({registration_status:'open',checked_at:'2026-11-01T10:00:00+08:00'})],{registration:'open'},now).length,0);
});
test('past/cancelled/false eligibility not future results',()=>{
 const old=e({id:'old',start:'2026-11-01T09:00:00+08:00',end:'2026-11-01T11:00:00+08:00'});
 assert.equal(S.search([old,e({event_status:'cancelled'}),e({caregiver_eligible:false})],{},now).length,0);
 assert.equal(S.search([old],{period:'past'},now).length,1);
});
test('calendar date range compares Taipei dates and end-date overlap',()=>{
 assert.equal(S.search([base],{from:'2026-11-21'},now).length,0);
 assert.equal(S.search([base],{to:'2026-11-19'},now).length,0);
 assert.equal(S.search([base],{from:'2026-11-20',to:'2026-11-20'},now).length,1);
});
test('date-only activity remains upcoming throughout source calendar day',()=>{
 const row=e({start:'2026-11-14T00:00:00+08:00',end:'2026-11-14T23:59:00+08:00',date_precision:'date'});
 assert.equal(S.search([row],{},now).length,1);
});
test('saved filters and malformed event rejection',()=>{
 assert.equal(S.search([base],{tab:'saved'},now,new Set(['a'])).length,1);
 assert.equal(S.search([base],{tab:'saved'},now,[]).length,0);
 assert.equal(S.search([e({start:'invalid'})],{},now).length,0);
});
test('inverted date range has no matches even for spanning events',()=>{
 const spanning=e({start:'2026-11-01T00:00:00+08:00',end:'2026-12-01T23:59:00+08:00'});
 assert.equal(S.search([spanning],{from:'2026-11-25',to:'2026-11-20'},now).length,0);
});

// v1.1.0: topic selection is a strict gate, with general support opt-in.
const topicRows = [
 e({id:'sch',title:'思覺失調家屬講座',summary:''}),
 e({id:'dep',title:'憂鬱症陪伴講座',summary:''}),
 e({id:'bip',title:'雙相情感障礙症家屬講座',summary:''}),
 e({id:'general',title:'家屬交流支持團體',summary:''}),
 e({id:'unknown',title:'資訊分享',summary:'',category:'其他',eligibility:'符合公告資格者'})
];
test('choosing schizophrenia excludes depression and bipolar lectures',()=>{
 assert.deepEqual(S.search(topicRows,{topic:'schizophrenia'},now).map(x=>x.id),['sch']);
});
test('depression and bipolar remain separate topics',()=>{
 assert.deepEqual(S.search(topicRows,{topic:'depression'},now).map(x=>x.id),['dep']);
 assert.deepEqual(S.search(topicRows,{topic:'bipolar'},now).map(x=>x.id),['bip']);
});
test('general support is opt-in and follows specific matches even if earlier',()=>{
 const general=e({id:'early',title:'家屬交流團體',summary:'',start:'2026-11-15T09:00:00+08:00'});
 assert.deepEqual(S.search([...topicRows,general],{topic:'schizophrenia',includeGeneral:true},now).map(x=>x.id),['sch','early','general']);
 assert.deepEqual(S.search(topicRows,{topic:'general'},now).map(x=>x.id),['general']);
});
test('unknown scope and organizer names do not become specific or general matches',()=>{
 const incidental=e({title:'資訊分享',summary:'',category:'其他',eligibility:'依公告',organizer:'思覺失調憂鬱躁鬱協會',notes:['思覺失調']});
 assert.equal(S.search([incidental],{topic:'schizophrenia',includeGeneral:true},now).length,0);
 assert.equal(S.search([incidental],{topic:'all'},now).length,1);
});
test('missing relevant activity stays empty, with no automatic broadening',()=>{
 assert.equal(S.search(topicRows.filter(x=>x.id!=='sch'),{topic:'schizophrenia'},now).length,0);
});
test('topic and geography/online/date criteria apply together',()=>{
 assert.equal(S.search(topicRows,{topic:'schizophrenia',city:'台中市'},now).length,0);
 assert.equal(S.search(topicRows,{topic:'schizophrenia',mode:'線上'},now).length,0);
 assert.equal(S.search(topicRows,{topic:'schizophrenia',to:'2026-11-19'},now).length,0);
});
test('schizophrenia alias is recognized, while explicit exclusion is rejected',()=>{
 assert.equal(S.topicMatch(e({title:'精神分裂症家屬講座',summary:''}),'schizophrenia'),true);
 const excluded=e({title:'家屬支持團體',summary:'',eligibility:'不含憂鬱症家屬'});
 assert.equal(S.topicMatch(excluded,'depression',true),false);
 assert.equal(S.topicInfo(excluded).general,false);
});
test('invalid topics fail closed and string true does not opt into general support',()=>{
 assert.equal(S.search(topicRows,{topic:'unrecognized'},now).length,0);
 assert.deepEqual(S.search(topicRows,{topic:'schizophrenia',includeGeneral:'true'},now).map(x=>x.id),['sch']);
});

test('current shipped coverage supports needs rather than invented disease-specific entry',()=>{
 const D=require('../data/events.json');
 const counts=Object.fromEntries(['exchange','learn','relax','community'].map(need=>[need,S.search(D.events,{need},now).length]));
 assert.deepEqual(counts,{exchange:3,learn:2,relax:2,community:1});
 assert.equal(S.search(D.events,{topic:'schizophrenia'},now).length,0);
 assert.equal(S.search(D.events,{topic:'depression'},now).length,0);
 assert.equal(S.search(D.events,{topic:'bipolar'},now).length,0);
});
test('community events do not become exercise and relaxation events',()=>{
 const carnival=e({title:'心光燦爛嘉年華',category:'紓壓活動',tags:['共融']});
 assert.equal(S.needMatch(carnival,'community'),true);assert.equal(S.needMatch(carnival,'relax'),false);
 assert.equal(S.needMatch(carnival,'unknown'),false);
});
test('needs intersect with city and do not imply registration remains open',()=>{
 const D=require('../data/events.json');
 assert.equal(S.search(D.events,{need:'exchange',city:'台北市'},now).length,2);
 assert.equal(S.search(D.events,{need:'relax',registration:'open'},now).length,0);
});

test('unmapped valid activities go to other without hiding or reclassifying known needs',()=>{
 const other=e({title:'權益資訊服務',category:'權益諮詢',summary:''});
 assert.equal(S.needMatch(other,'other'),true);
 assert.equal(S.needMatch(topicRows[0],'other'),false);
 assert.equal(S.search([other],{need:'other'},now).length,1);
 const D=require('../data/events.json');
 assert.equal(S.search(D.events,{need:'other'},now).length,0);
});

const test=require('node:test');
const assert=require('node:assert/strict');
const drafts=require('../web/drafts.js');
class MemoryStorage {
  constructor(){this.items=new Map();}
  get length(){return this.items.size;}
  key(index){return [...this.items.keys()][index] ?? null;}
  getItem(key){return this.items.get(key) ?? null;}
  setItem(key,value){this.items.set(key,String(value));}
  removeItem(key){this.items.delete(key);}
}
let serial=0,clock=100;
const options={newId:()=>String(++serial),now:()=>++clock};
const edit=title=>({title,style:'editorial',aspect:'9:16',scenes:[{heading:title,caption:'草稿内容',duration:5}]});

test('saving in one window preserves the closed second window draft',()=>{
  const storage=new MemoryStorage(),sessionA=new MemoryStorage(),sessionB=new MemoryStorage();
  const a=drafts.create(storage,sessionA,options),b=drafts.create(storage,sessionB,options);
  b.write('project',1,edit('窗口 B 尚未保存'));
  a.write('project',1,edit('窗口 A 已保存'));a.clearOwn('project');
  const reopened=drafts.create(storage,sessionB,options);
  assert.deepEqual(reopened.list('project').map(r=>r.edit.title),['窗口 B 尚未保存']);
});

test('duplicated browser tabs with the same session still use separate draft owners',()=>{
  const storage=new MemoryStorage(),session=new MemoryStorage();
  const a=drafts.create(storage,session,options),b=drafts.create(storage,session,options);
  a.write('project',1,edit('A'));b.write('project',1,edit('B'));
  a.clearOwn('project');
  assert.equal(b.list('project')[0].edit.title,'B');
});

test('reload prefers this browser session while keeping other choices available',()=>{
  const storage=new MemoryStorage(),sessionA=new MemoryStorage(),sessionB=new MemoryStorage();
  drafts.create(storage,sessionA,options).write('project',1,edit('A earlier'));
  drafts.create(storage,sessionB,options).write('project',2,edit('B newer'));
  const reopened=drafts.create(storage,sessionA,options);
  assert.deepEqual(reopened.list('project').map(r=>r.edit.title),['A earlier','B newer']);
});

test('recovery removes only the unchanged source after its copy is stored',()=>{
  const storage=new MemoryStorage(),a=drafts.create(storage,new MemoryStorage(),options);
  a.write('project',1,edit('old'));
  const b=drafts.create(storage,new MemoryStorage(),options),record=b.list('project')[0];
  b.write('project',2,record.edit);
  a.write('project',1,edit('edited elsewhere during recovery'));
  assert.equal(b.remove(record),false);
  assert.equal(b.list('project').length,2);
  const latest=b.list('project').find(r=>!r.own);
  assert.equal(b.remove(latest),true);
  assert.equal(b.list('project')[0].edit.title,'old');
});

test('legacy drafts remain recoverable despite corrupt or unrelated entries',()=>{
  const storage=new MemoryStorage(),session=new MemoryStorage();
  storage.setItem('frame-draft:project',JSON.stringify({baseVersion:3,edit:edit('legacy'),updatedAt:10}));
  storage.setItem('frame-draft:project:broken','{broken');
  storage.setItem('frame-draft:project:incomplete',JSON.stringify({baseVersion:1,updatedAt:20,edit:{title:'broken',scenes:[{}]}}));
  storage.setItem('frame-draft:project-other',JSON.stringify({baseVersion:1,edit:edit('other'),updatedAt:20}));
  const store=drafts.create(storage,session,options);
  assert.deepEqual(store.list('project').map(r=>r.edit.title),['legacy']);
  assert.equal(storage.length,4);
});

test('a full browser storage reports failure without deleting existing drafts',()=>{
  const storage=new MemoryStorage(),a=drafts.create(storage,new MemoryStorage(),options);
  a.write('project',1,edit('safe'));
  const b=drafts.create(storage,new MemoryStorage(),options);
  storage.setItem=()=>{throw new Error('Quota exceeded');};
  assert.throws(()=>b.write('project',2,edit('new')),/Quota/);
  assert.equal(b.list('project')[0].edit.title,'safe');
});

test('drafts still persist when session storage is unavailable',()=>{
  const storage=new MemoryStorage();
  const session={getItem(){throw new Error('Session disabled');}};
  const store=drafts.create(storage,session,options);
  store.write('project',1,edit('still recoverable'));
  assert.equal(store.list('project')[0].edit.title,'still recoverable');
});

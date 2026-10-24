const test = require('node:test');
const assert = require('node:assert/strict');
const brief = require('../web/brief.js');
class MemoryStorage {
  constructor(){this.items=new Map();}
  getItem(key){return this.items.get(key) ?? null;}
  setItem(key,value){this.items.set(key,String(value));}
  removeItem(key){this.items.delete(key);}
}
const input = () => ({kind:'merchant',style:'editorial',aspect:'9:16',duration:30,
  industry:'flowers',scenario:'offer',example:true,prompt:'还没写完的另一个创意',mode:'template',
  fields:{store_name:'一枝花房（演示）',product:'日常花束',selling_point:'可以沟通颜色',offer:'',address:'虚构路 18 号',cta:'欢迎到店看看'}});

test('reload recovers incomplete briefs, both modes, style, and disclosure without trimming input',()=>{
  const storage=new MemoryStorage(), value=input();value.fields.offer='  ';
  brief.create(storage).write(value);
  assert.deepEqual(brief.create(storage).read(),value);
  assert.deepEqual(brief.readiness(value).missing,[{field:'offer',label:'活动信息'}]);
});
test('separate browser windows never overwrite or clear each others pending brief',()=>{
  const a=brief.create(new MemoryStorage()),b=brief.create(new MemoryStorage());
  const value=input();a.write(value);b.write({...value,prompt:'另一窗口的想法'});a.clear();
  assert.equal(a.read(),null);assert.equal(b.read().prompt,'另一窗口的想法');
});
test('normalization drops unrelated values and rejects oversized, invalid, and corrupt drafts',()=>{
  const storage=new MemoryStorage(),store=brief.create(storage);
  store.write({...input(),secret:'not a supported field'});
  assert.equal('secret' in store.read(),false);
  for(const value of [{...input(),kind:'unknown'},{...input(),duration:31},{...input(),prompt:'a'.repeat(801)},
    {...input(),fields:{...input().fields,cta:null}}])assert.throws(()=>store.write(value));
  for(const raw of ['{','null',JSON.stringify({format:2,brief:input()}),'x'.repeat(16001)]){
    storage.setItem('frame-new-brief-v1',raw);assert.equal(store.read(),null);
  }
});
test('storage quota failures preserve previous content and can be surfaced by the caller',()=>{
  const storage=new MemoryStorage(),store=brief.create(storage),value=input();store.write(value);
  storage.setItem=()=>{throw new Error('Quota exceeded');};
  assert.throws(()=>store.write({...value,prompt:'new text'}),/Quota/);
  assert.deepEqual(store.read(),value);
});
test('activity details become required only for the activity scenario; whitespace never counts',()=>{
  const value=input();assert.equal(brief.readiness(value).completed,5);
  value.scenario='visit';assert.equal(brief.readiness(value).missing.length,0);
  value.fields.store_name='  ';assert.equal(brief.readiness(value).missing[0].field,'store_name');
  value.kind='creative';value.prompt='    a  ';assert.equal(brief.readiness(value).completed,0);
  value.prompt='我的小店故事';assert.equal(brief.readiness(value).completed,1);
});
test('poster uses only supplied facts, follows the selected purpose, and labels empty input',()=>{
  const value=input();value.fields.offer='周六到店可了解插花活动';
  assert.equal(brief.poster(value).caption,value.fields.offer);
  value.scenario='visit';assert.equal(brief.poster(value).heading,value.fields.store_name);
  assert.equal(brief.poster(value).caption,value.fields.product);
  value.scenario='product';assert.equal(brief.poster(value).heading,value.fields.product);
  assert.equal(brief.poster(value).caption,value.fields.selling_point);
  value.fields.product='';assert.equal(brief.poster(value).placeholder,true);
  assert.equal(brief.poster(value).heading,'你的主推产品');
});

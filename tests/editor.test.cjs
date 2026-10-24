const {test} = require("node:test");
const assert = require("node:assert/strict");
const editor = require("../web/editor.js");
const project = () => ({title:"门店宣传", style:"editorial", aspect:"9:16", cover_scene:1,
  scenes:[editor.scene({heading:"A"}),editor.scene({heading:"B",asset_id:"a".repeat(32)}),editor.scene({heading:"C"})]});

test("reordering follows the cover and never mutates the saved project", () => {
  const original = project(), moved = editor.transform(original,"up",1);
  assert.deepEqual(moved.scenes.map(s=>s.heading),["B","A","C"]);
  assert.equal(moved.cover_scene,0);
  assert.equal(original.cover_scene,1);
  assert.deepEqual(original.scenes.map(s=>s.heading),["A","B","C"]);
});
test("duplicates retain photo composition while keeping edits independent", () => {
  const original = project(), next = editor.transform(original,"duplicate",1);
  assert.equal(next.scenes[2].asset_id,original.scenes[1].asset_id);
  next.scenes[2].caption = "另一段文案";
  assert.notEqual(next.scenes[1].caption,next.scenes[2].caption);
  assert.equal(next.cover_scene,1);
});
test("deleting the cover always selects a remaining scene", () => {
  const original = project(); original.cover_scene=2;
  assert.equal(editor.transform(original,"remove",2).cover_scene,1);
  const only = {...original, cover_scene:0, scenes:[original.scenes[0]]};
  assert.throws(()=>editor.transform(only,"remove",0),/至少/);
});
test("add/duplicate guard available time and scene count", () => {
  const full = project(); full.scenes.forEach(s=>s.duration=20);
  assert.throws(()=>editor.transform(full,"add",2),/时长/);
  assert.throws(()=>editor.transform(full,"duplicate",1),/时长/);
  const eight = project(); eight.scenes=Array.from({length:8},()=>editor.scene({duration:2}));
  assert.throws(()=>editor.transform(eight,"add",0),/8/);
});
test("legacy projects gain composition defaults without changing content", () => {
  const old = {title:"旧作品",style:"cinema",aspect:"1:1",scenes:[{heading:"旧标题",caption:"旧字幕",duration:15}]};
  const edit = editor.editable(old);
  assert.equal(edit.scenes[0].crop_x,.5);
  assert.equal(edit.cover_scene,0);
  assert.equal(edit.scenes[0].heading,"旧标题");
  assert.equal(editor.validate(edit),edit);
  edit.scenes[0].duration=0;
  assert.throws(()=>editor.validate(edit),/2–20/);
});
test("voiceover drafts remain independent when duplicated and enforce limits", () => {
  const original=project();original.scenes[0].voiceover="让画面简短，让口播完整。";
  const next=editor.transform(original,"duplicate",0);
  next.scenes[1].voiceover="另一种讲述方式。";
  assert.equal(next.scenes[0].voiceover,original.scenes[0].voiceover);
  next.scenes[1].voiceover="长".repeat(161);
  assert.throws(()=>editor.validate(next),/160/);
});

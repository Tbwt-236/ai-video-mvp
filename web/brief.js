/* New-project drafts are local to this browser window, including across reloads. */
(function (root) {
  "use strict";
  const key = "frame-new-brief-v1";
  const limits = {store_name:24, product:32, selling_point:48, offer:40, address:48, cta:32};
  const labels = {store_name:"店名", product:"主推产品", selling_point:"到店理由", offer:"活动信息", address:"门店地址", cta:"到店邀请"};
  function normalize(value) {
    if (!value || typeof value !== "object" || !value.fields) return null;
    const enums = {kind:["merchant","creative"], style:["cinema","editorial","tech"], aspect:["9:16","16:9","1:1"],
      industry:["coffee","food","bakery","beauty","pet","flowers"], scenario:["visit","product","offer","story"], mode:["template","ai"]};
    for (const [field, values] of Object.entries(enums)) if (!values.includes(value[field])) return null;
    if (![15,30,45,60].includes(value.duration) || typeof value.example !== "boolean" ||
        typeof value.prompt !== "string" || value.prompt.length > 800) return null;
    const fields = {};
    for (const [field, max] of Object.entries(limits)) {
      if (typeof value.fields[field] !== "string" || value.fields[field].length > max) return null;
      fields[field] = value.fields[field];
    }
    return {...Object.fromEntries(Object.keys(enums).map(field=>[field,value[field]])),
      duration:value.duration, example:value.example, prompt:value.prompt, fields};
  }
  function create(storage) {
    return {
      read() {
        const raw = storage.getItem(key);
        if (!raw || raw.length > 16000) return null;
        try { const record = JSON.parse(raw); return record?.format === 1 ? normalize(record.brief) : null; }
        catch { return null; }
      },
      write(value) {
        const brief = normalize(value);
        if (!brief) throw new Error("Invalid new-project draft");
        storage.setItem(key, JSON.stringify({format:1, brief}));
      },
      clear() { storage.removeItem(key); },
    };
  }
  function readiness(brief) {
    if (brief.kind === "creative") {
      const ready = brief.prompt.trim().length >= 5;
      return {total:1, completed:Number(ready), missing:ready ? [] : [{field:"prompt",label:"至少 5 个字的创意描述"}]};
    }
    const required = Object.keys(limits).filter(field=>field !== "offer" || brief.scenario === "offer");
    const missing = required.filter(field=>!brief.fields[field].trim()).map(field=>({field,label:labels[field]}));
    return {total:required.length, completed:required.length-missing.length, missing};
  }
  function poster(brief) {
    if (brief.kind === "creative") return {heading:"把想法，写成故事", caption:brief.prompt.trim() || "先写下主题、受众和想传递的感觉。", placeholder:!brief.prompt.trim()};
    const fields = Object.fromEntries(Object.entries(brief.fields).map(([k,v])=>[k,v.trim()]));
    const productFirst = ["product","offer"].includes(brief.scenario);
    const heading = productFirst ? fields.product : fields.store_name;
    const caption = brief.scenario === "offer" ? fields.offer : brief.scenario === "visit" ? fields.product : fields.selling_point;
    const hint = brief.scenario === "offer" ? "填写活动内容和适用时间。" : brief.scenario === "visit" ? "这里会出现你本次主推的产品。" : "写下真实特色，让顾客了解你的小店。";
    return {heading:heading || (productFirst ? "你的主推产品" : "你的小店名字"), caption:caption || hint, placeholder:!heading};
  }
  const api = {create, normalize, readiness, poster};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.FrameBrief = api;
})(typeof window !== "undefined" ? window : globalThis);

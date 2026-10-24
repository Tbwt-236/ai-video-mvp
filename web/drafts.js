/* Each editing page owns its draft; saving in one tab cannot erase another's. */
(function (root) {
  "use strict";
  const newId = () => root.crypto?.randomUUID ? root.crypto.randomUUID() : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  function create(storage, session, settings={}) {
    const id=settings.newId || newId, now=settings.now || Date.now;
    let group;
    try{
      group=session.getItem("frame-draft-session");
      if(!group){group=id();session.setItem("frame-draft-session",group);}
    }catch{group=id();}
    const owner=id();
    const key=project=>`frame-draft:${project}:${owner}`;
    return {
      write(project,baseVersion,edit) {
        storage.setItem(key(project),JSON.stringify({baseVersion,edit,updatedAt:now(),session:group}));
      },
      clearOwn(project) { storage.removeItem(key(project)); },
      list(project) {
        const prefix=`frame-draft:${project}`, records=[];
        for(let index=0;index<storage.length;index++){
          const name=storage.key(index);
          if(name!==prefix && !name?.startsWith(prefix+":"))continue;
          const raw=storage.getItem(name);
          try{
            const record=JSON.parse(raw);
            if(!record?.edit || !Array.isArray(record.edit.scenes) || !record.edit.scenes.length || record.edit.scenes.length>8 ||
              !Number.isInteger(record.baseVersion) || record.baseVersion<1 || !Number.isFinite(record.updatedAt))continue;
            if(typeof record.edit.title!=="string" || !["cinema","editorial","tech"].includes(record.edit.style) ||
              !["9:16","16:9","1:1"].includes(record.edit.aspect) ||
              record.edit.scenes.some(scene=>!scene || typeof scene.heading!=="string" || typeof scene.caption!=="string" || !Number.isFinite(scene.duration)))continue;
            records.push({...record,key:name,raw,own:name===key(project),sameSession:record.session===group});
          }catch{ /* One damaged entry must not hide the other recoverable drafts. */ }
        }
        return records.sort((a,b)=>Number(b.own)-Number(a.own) || Number(b.sameSession)-Number(a.sameSession) || b.updatedAt-a.updatedAt);
      },
      remove(record) {
        if(!record?.key?.startsWith("frame-draft:") || storage.getItem(record.key)!==record.raw)return false;
        storage.removeItem(record.key);
        return true;
      },
    };
  }
  const api={create};
  if(typeof module!=="undefined" && module.exports)module.exports=api;
  else root.FrameDrafts=api;
})(typeof window!=="undefined" ? window : globalThis);

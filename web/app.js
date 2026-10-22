"use strict";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const icon = (name) => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
const esc = (value) => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const E = window.FrameEditor;
const state = {projects: [], current: null, style: "cinema", aspect: "9:16", scene: 0,
  dirty: false, playing: false, job: null, poll: null, playTimer: null, saving: false, serial: 0, config: null, briefKind: "merchant", merchantExample: false, uploading: 0, draft:null, assets:[], history:[], future:[], pendingDraft:null, previewRevision:0, previewController:null, previewObject:null, previewTimer:null, mediaTarget:0, lastEditAt:0, lastEditKey:""};
let toastTimer;

function toast(message, error = false) {
  clearTimeout(toastTimer);
  $("#toast").textContent = message;
  $("#toast").classList.toggle("error", error);
  $("#toast").hidden = false;
  toastTimer = setTimeout(() => { $("#toast").hidden = true; }, error ? 6000 : 3200);
}

async function api(url, options = {}) {
  try { return await window.FrameHTTP.requestJSON(url,options); }
  catch(error){if(error.code==="NETWORK")connectionStatus(false);throw error;}
}
function connectionStatus(online) {
  $("#connection").classList.toggle("offline",!online);
  $("#connection").innerHTML='<span class="status-dot"></span>'+(online ? "本地工作室":"服务连接异常");
  $("#retry-connection").hidden=online;
}

function showError(selector, message = "") {
  $(selector).hidden = !message;
  $(selector).textContent = message;
}

function seconds(value) { return `${String(Math.floor(value/60)).padStart(2,"0")}:${String(value%60).padStart(2,"0")}`; }
function total() { return state.draft ? state.draft.scenes.reduce((sum,s) => sum + (Number(s.duration)||0),0) : Number($("#duration").value); }
function previewUrl(project, index) { return `/api/projects/${project.id}/scenes/${index}.png?v=${project.version}`; }

function currentRoute() { return !$("#library-view").hidden ? "#library" : state.current ? `#project=${state.current.id}` : "#new"; }
function rememberRoute(route=currentRoute(),replace=false) {
  if(location.hash!==route)history[replace ? "replaceState":"pushState"](null,"",route);
}
async function restoreRoute() {
  if(!canLeave()){rememberRoute(currentRoute(),true);return;}
  const route=location.hash;
  if(route==="#library"){setPage("library");return;}
  const match=route.match(/^#project=([a-f0-9-]{36})$/);
  if(match){await openProject(match[1]);return;}
  if(route==="#new" && state.current)newProject();
}

function setPage(page) {
  $("#studio-view").hidden = page !== "studio";
  $("#library-view").hidden = page !== "library";
  $("#nav-studio").classList.toggle("active", page === "studio");
  $("#nav-library").classList.toggle("active", page === "library");
  $("#breadcrumb").textContent = page === "studio" ? "创作工作台" : "我的作品";
  if (page === "library") { stopPreview();$("#final-video").pause();stopVoice();renderLibrary(); }
  updateDock();
  rememberRoute();
}

function setStep(step) {
  $("#step-idea").classList.toggle("active", step === 1);
  $("#step-board").classList.toggle("active", step === 2);
  $("#step-export").classList.toggle("active", step === 3);
  $("#step-board").disabled = !state.current;
  $("#step-export").disabled = !state.current;
}

function canLeave() {
  if (state.uploading || state.saving || state.importing || state.creating) { toast("请等待当前作品操作完成。", true); return false; }
  if (state.dirty) persistDraft();
  return true;
}

function newProject() {
  if (!canLeave()) return;
  state.serial++;
  clearTimeout(state.poll);
  stopPreview();
  state.current = null; state.draft = null; state.assets = []; state.job = null; state.dirty = false;
  $(".preview-column").scrollTop=0;
  stopVoice();updateAudioControls();clearPreflight();
  clearTimeout(state.previewTimer); state.previewController?.abort(); state.previewRevision++;
  $("#history-panel").hidden = true;
  $("#brief-form").reset(); state.merchantExample = false; $("#merchant-example-note").hidden = true;
  selectIndustry(state.industry || "coffee");renderMerchantReuse();
  $("#narration").checked = Boolean(state.config?.narration_available);
  updateAudioControls();
  setBriefKind(state.briefKind);
  $("#final-video").pause(); $("#final-video").removeAttribute("src");
  $("#final-video").hidden = true;
  $("#scene-preview").hidden = true;
  $("#sample-poster").hidden = false;
  $(".preview-transport").hidden = false; $("#timeline").hidden = false;
  $("#brief-panel").hidden = false;
  $("#storyboard-panel").hidden = true;
  $("#preview-badge").textContent = "风格示意";
  $("#preview-hint").textContent = "生成分镜后，在这里预览你的故事";
  $("#play-preview").disabled = true;
  $("#next-preview").disabled = true;
  $("#timeline").innerHTML = "<span></span><span></span><span></span>";
  $("#export-video").disabled = true; $("#export-video").hidden = false;
  $("#export-video span").textContent = "导出视频";
  $("#download-actions").hidden = true; $("#job-progress").hidden = true;
  $("#export-note").textContent = "生成分镜，距离成片再近一步";
  $("#generate").disabled = false; $("#generate").classList.remove("loading");
  $("#generate span").textContent = "生成我的分镜";
  showError("#form-error"); showError("#export-error"); showError("#save-error");
  setAspect(state.aspect); setStyle(state.style); setPage("studio"); setStep(1); renderRecent();
  window.scrollTo({top:0, behavior:"smooth"});
}

function setStyle(style) {
  state.style = style;
  $$("[data-style].style-option").forEach(button => {
    const selected = button.dataset.style === style;
    button.classList.toggle("selected", selected); button.setAttribute("aria-pressed", selected);
  });
  $("#sample-poster").className = `sample-poster ${style}`;
}

function setAspect(aspect) {
  state.aspect = aspect;
  $$("#aspect-options button").forEach(button => {
    const selected = button.dataset.aspect === aspect;
    button.classList.toggle("selected", selected); button.setAttribute("aria-pressed", selected);
  });
  if (!state.current) { $("#preview-spec").textContent = aspect; updateStage(aspect); updateTime(); }
  updateExportDimensions();
}

function updateStage(aspect) {
  $("#preview-stage").dataset.aspect = aspect;
  $("#preview-stage").style.aspectRatio = aspect.replace(":", "/");
  $("#preview-stage").style.maxWidth = aspect === "9:16" ? "282px" : "100%";
}

function renderRecent() {
  const projects = state.projects.filter(p=>!p.archived);
  $("#project-count").textContent = projects.length;
  $("#recent-projects").innerHTML = projects.slice(0,6).map(project =>
    `<button class="recent-item ${state.current?.id===project.id ? "selected" : ""}" data-project="${project.id}" data-style="${project.style}" title="${esc(project.title)}"><i></i><span>${esc(project.title)}</span></button>`).join("");
}

function renderLibrary() {
  const query = $("#project-search").value.trim().toLowerCase(), filter = $("#library-filter").value;
  const projects = state.projects.filter(p => (filter === "all" || Boolean(p.archived) === (filter === "archived")) && `${p.title} ${p.prompt}`.toLowerCase().includes(query));
  $("#library-count").textContent = projects.length;
  $("#library-grid").innerHTML = projects.length ? projects.map(p =>
    `<article class="project-card"><button class="project-cover project-open" data-project="${p.id}" aria-label="打开 ${esc(p.title)}"><img src="${previewUrl(p,p.cover_scene||0)}" alt="${esc(p.title)}封面" loading="lazy"><span>${p.archived ? "已归档" : p.example ? "示例作品" : p.source === "deepseek" ? "AI 分镜" : p.source === "merchant_template" ? "门店宣传" : "本地模板"}</span></button><h3>${esc(p.title)}</h3><p>${p.aspect} · ${p.duration} 秒 · ${p.scenes.length} 个分镜</p><div class="project-actions"><button data-project="${p.id}">打开作品</button><button data-project-action="duplicate" data-id="${p.id}">复制</button><button data-project-action="${p.archived ? "restore":"archive"}" data-id="${p.id}">${p.archived ? "恢复":"归档"}</button></div><small class="project-updated">${new Date(p.updated_at).toLocaleDateString("zh-CN")}</small></article>`).join("") : `<div class="empty-library">${query ? "没有找到匹配的作品，试试其他关键词。" : filter === "archived" ? "还没有归档作品。归档后仍可恢复。" : "还没有作品，从一支短片开始。"}</div>`;
}

async function refreshProjects() {
  state.projects = await api("/api/projects?include_archived=true"); renderRecent();
  renderMerchantReuse();
  if (!$("#library-view").hidden) renderLibrary();
}

async function openProject(id) {
  if (!canLeave()) return;
  const serial = ++state.serial;
  try {
    const project = await api(`/api/projects/${id}`);
    if (serial !== state.serial) return;
    clearTimeout(state.poll); stopPreview();
    state.current = project; state.dirty = false; state.scene = 0; state.job = null;
    $(".preview-column").scrollTop=0;
    stopVoice();
    displayBoard(); setPage("studio"); renderRecent();
    window.scrollTo({top:0, behavior:"smooth"});
    const [jobs, assets] = await Promise.all([api(`/api/projects/${id}/jobs`),api(`/api/projects/${id}/assets`)]);
    if (serial !== state.serial) return;
    state.assets = assets; renderHistory(jobs);
    const candidates=jobs.filter(j=>j.version===project.version);
    const matching=candidates.find(j=>["queued","rendering","cancelling"].includes(j.status)) || candidates.find(j=>j.status==="completed") || candidates[0];
    if (matching) { restoreExportSettings(matching); handleJob(matching); }
  } catch (error) { toast(error.message, true);rememberRoute(currentRoute(),true); }
}

function displayBoard() {
  const p = state.current;
  state.draft = E.editable(p); state.assets = []; resetHistory();
  $("#custom-color").checked = Boolean(p.accent_color); $("#accent-color").value = p.accent_color || "#c2d69b";
  $("#history-panel").hidden = true;
  $("#brief-panel").hidden = true; $("#storyboard-panel").hidden = false;
  $("#project-title").value = p.title; $("#board-style").value = p.style; $("#board-aspect").value = p.aspect;
  $("#board-source").textContent = p.source === "merchant_template" ? (p.example ? "◈ 虚构门店示例" : "◈ 门店信息模板") : p.source === "deepseek" ? "✳ DeepSeek AI 分镜" : "◈ 本地模板 · 可自由编辑";
  $("#demo-disclosure").hidden=p.example_assets!=="ai";
  $("#demo-disclosure").textContent=p.example_assets==="ai" ? "AI 演示照片 · 虚构门店。示例将同一张照片用于不同镜头，正式宣传请换成真实门店照片与信息。" : "";
  $("#save-status").textContent = "已保存至本地";
  renderMerchantSummary();
  showError("#save-error"); showError("#export-error");
  renderScenes(); updateBoardTotal(); showScene(0); setStep(2); resetExport(); findDraft();updateAudioControls();clearPreflight();updateDock();
  rememberRoute(`#project=${p.id}`);
}

function assetUrl(asset) { return `/api/projects/${state.current.id}/assets/${asset}.jpg`; }
function options(values, current) { return values.map(([key,label])=>`<option value="${key}" ${key===current ? "selected":""}>${label}</option>`).join(""); }
function renderScenes() {
  const p = state.draft;
  $("#scenes").innerHTML = p.scenes.map((scene,i) => {
    const source = scene.asset_id ? assetUrl(scene.asset_id) : i < state.current.scenes.length ? previewUrl(state.current,i) : "/favicon.svg";
    return `<article class="scene-card ${i===state.scene ? "active":""}" data-index="${i}" data-asset-id="${esc(scene.asset_id || "")}">
      <div class="scene-card-head"><span class="scene-number">${String(i+1).padStart(2,"0")}</span><span>${p.cover_scene===i ? "★ 封面分镜" : "分镜画面"}</span><label>时长 <input type="number" min="2" max="20" step="1" value="${scene.duration}" data-field="duration" aria-label="分镜 ${i+1} 时长">秒</label></div>
      <div class="scene-content"><button class="scene-thumb" data-preview="${i}" aria-label="预览分镜 ${i+1}"><img src="${source}" alt="分镜 ${i+1}" loading="lazy"></button><div><label for="heading-${i}">画面标题</label><input id="heading-${i}" data-field="heading" maxlength="32" value="${esc(scene.heading)}" required><label for="caption-${i}">画面字幕</label><textarea id="caption-${i}" data-field="caption" maxlength="96" required>${esc(scene.caption)}</textarea><div class="scene-counter">${scene.caption.length} / 96</div></div></div>
      <div class="scene-photo"><label class="photo-upload">${icon("plus")} ${scene.asset_id ? "更换照片" : "上传照片"}<input type="file" accept="image/jpeg,image/png,image/webp" data-upload="${i}" aria-label="分镜 ${i+1} 照片"></label><button class="text-button" data-media="${i}">从照片库选择</button><button type="button" class="remove-photo" ${scene.asset_id ? "" : "hidden"}>移除照片</button><span class="photo-status">${scene.asset_id ? "使用门店照片" : "使用图形背景"}</span></div>
      <details class="composition"><summary>画面构图 <small>裁切 · 文字 · 运动</small></summary><div class="composition-grid">
        <label>照片适配<select data-field="photo_fit" aria-label="照片适配">${options([["cover","铺满画面"],["contain","完整展示"]],scene.photo_fit)}</select></label>
        <label>文字位置<select data-field="text_position" aria-label="文字位置">${options([["bottom","下方"],["center","居中"],["top","上方"]],scene.text_position)}</select></label>
        <label>镜头运动<select data-field="motion" aria-label="镜头运动">${options([["zoom_in","缓慢推进"],["zoom_out","缓慢拉远"],["still","静止画面"],["pan_left","向左移动"],["pan_right","向右移动"]],scene.motion)}</select></label>
        <label>照片放大 <output data-output="zoom">${Number(scene.zoom).toFixed(1)}×</output><input data-field="zoom" type="range" min="1" max="2" step="0.05" value="${scene.zoom}" aria-label="分镜 ${i+1} 照片放大"></label>
        <label>横向取景 <output data-output="crop_x">${Math.round(scene.crop_x*100)}%</output><input data-field="crop_x" type="range" min="0" max="1" step="0.01" value="${scene.crop_x}" aria-label="分镜 ${i+1} 横向取景"></label>
        <label>纵向取景 <output data-output="crop_y">${Math.round(scene.crop_y*100)}%</output><input data-field="crop_y" type="range" min="0" max="1" step="0.01" value="${scene.crop_y}" aria-label="分镜 ${i+1} 纵向取景"></label>
      </div><p>取景、放大与镜头运动用于「铺满画面」；「完整展示」保持静止，确保照片不被裁切。</p></details>
      <details class="scene-voice" ${scene.voiceover ? "open":""}><summary>独立口播稿 <small>${scene.voiceover ? "已自定义":"可选 · 默认朗读字幕"}</small></summary><label for="voiceover-${i}">这一幕想说的话</label><textarea id="voiceover-${i}" data-field="voiceover" maxlength="160" placeholder="留空会朗读画面字幕。可在这里写更完整的产品介绍，让画面保持简洁。">${esc(scene.voiceover || "")}</textarea><div class="voice-counter">${(scene.voiceover || "").length} / 160</div><p>开启中文配音后生效。口播字幕文件使用这段文案，画面仍显示上方的简短字幕。</p></details>
      <div class="scene-actions"><button data-scene-action="up" ${i===0 ? "disabled":""} aria-label="上移分镜 ${i+1}">↑ 上移</button><button data-scene-action="down" ${i===p.scenes.length-1 ? "disabled":""} aria-label="下移分镜 ${i+1}">↓ 下移</button><button data-scene-action="duplicate">复制</button><button data-scene-action="cover" ${p.cover_scene===i ? "disabled":""}>设为封面</button><button data-scene-action="remove" ${p.scenes.length===1 ? "disabled":""}>删除</button></div>
    </article>`;
  }).join("");
}

function collectEdit() {
  const scenes = $$(".scene-card").map((card,i) => {
    const item = E.scene(state.draft.scenes[i]);
    card.querySelectorAll("[data-field]").forEach(input=> {
      item[input.dataset.field] = ["duration","crop_x","crop_y","zoom"].includes(input.dataset.field) ? Number(input.value) : input.value.trim();
    });
    item.asset_id = card.dataset.assetId || null;
    item.voiceover=item.voiceover || null;
    return item;
  });
  return {title:$("#project-title").value.trim(),style:$("#board-style").value,aspect:$("#board-aspect").value,scenes,
    cover_scene:state.draft.cover_scene,accent_color:$("#custom-color").checked ? $("#accent-color").value : null,
    merchant:state.draft.merchant};
}
function readEdit() { return {...E.validate(collectEdit()), version:state.current.version}; }
function updateBoardTotal() {
  $("#board-total").textContent = `${state.draft.scenes.length} 个分镜 · 共 ${total()} 秒`;
  try { E.validate(state.draft); showError("#save-error"); }
  catch (error) { showError("#save-error",error.message); }
}
function persistDraft() {
  if (!state.current || !state.draft) return;
  try {
    if (state.dirty) localStorage.setItem(`frame-draft:${state.current.id}`,JSON.stringify({baseVersion:state.current.version,edit:state.draft,updatedAt:Date.now()}));
    else localStorage.removeItem(`frame-draft:${state.current.id}`);
  } catch { $("#save-status").textContent = "草稿空间不足，请保存分镜"; }
}
function findDraft() {
  state.pendingDraft = null; $("#draft-banner").hidden = true;
  try {
    const cached = JSON.parse(localStorage.getItem(`frame-draft:${state.current.id}`) || "null");
    if (cached?.edit?.scenes?.length && cached.edit.scenes.length<=8) {
      cached.edit=E.editable({...cached.edit,merchant:cached.edit.merchant===undefined ? state.current.merchant : cached.edit.merchant});
      if(JSON.stringify(cached.edit)===JSON.stringify(state.draft))return;
      state.pendingDraft = cached; $("#draft-banner").hidden = false;
      $("#draft-message").textContent = cached.baseVersion === state.current.version ? "发现未保存的本机草稿。" : "发现旧版本草稿；恢复后请核对最新内容再保存。";
    }
  } catch { /* A damaged local draft does not prevent opening the saved project. */ }
}
function historyButtons() { $("#undo-edit").disabled = state.history.length<2; $("#redo-edit").disabled = !state.future.length; }
function resetHistory() { state.history=[E.clone(state.draft)]; state.future=[]; state.lastEditAt=0; historyButtons(); }
function rememberEdit(force=false) {
  const previous=state.history[state.history.length-1];
  if (JSON.stringify(previous)===JSON.stringify(state.draft)) return;
  const active=document.activeElement, key=`${active?.id || active?.dataset.field || ""}:${active?.closest(".scene-card")?.dataset.index || ""}`;
  if (!force && state.history.length>1 && key===state.lastEditKey && Date.now()-state.lastEditAt<700) state.history[state.history.length-1]=E.clone(state.draft);
  else state.history.push(E.clone(state.draft));
  if(state.history.length>40)state.history.shift();
  state.future=[];state.lastEditAt=Date.now();state.lastEditKey=key;historyButtons();
}
function markDirty({record=true,force=false}={}) {
  if (!state.current) return;
  state.draft=collectEdit();
  state.dirty=JSON.stringify(state.draft)!==JSON.stringify(E.editable(state.current));
  if(record)rememberEdit(force);
  state.previewController?.abort();state.previewRevision++;
  stopVoice();clearPreflight();
  stopPreview();clearTimeout(state.poll);state.job=null;
  if (!state.config?.narration_available) $("#narration").checked=false;
  updateAudioControls();
  $("#save-status").textContent=state.dirty ? "已暂存草稿 · 待保存":"已保存至本地";
  $("#draft-banner").hidden=true;persistDraft();
  $("#download-actions").hidden=true;$("#export-video").hidden=false;$("#export-video").disabled=false;
  $("#export-video span").textContent=state.dirty ? "保存并导出视频":"导出视频";
  $("#export-note").textContent="导出将使用最新保存的分镜";
  updateBoardTotal();
  clearTimeout(state.previewTimer);
  state.previewTimer=setTimeout(()=>showScene(Math.min(state.scene,state.draft.scenes.length-1)),450);
}
function applyDraft(edit, record=true) {
  state.draft=E.clone(edit);
  $("#project-title").value=edit.title;$("#board-style").value=edit.style;$("#board-aspect").value=edit.aspect;
  $("#custom-color").checked=Boolean(edit.accent_color);$("#accent-color").value=edit.accent_color || "#c2d69b";
  state.scene=Math.min(state.scene,edit.scenes.length-1);renderScenes();renderMerchantSummary();markDirty({record,force:true});historyButtons();
}
async function refreshDraftPreview(index) {
  const revision=++state.previewRevision, id=state.current.id;
  state.previewController?.abort();
  if (!state.dirty) { $("#scene-preview").src=previewUrl(state.current,index); return; }
  let body;
  try { body={...readEdit(),index}; }
  catch(error) { $("#preview-hint").textContent=error.message;return; }
  state.previewController=new AbortController();
  $("#preview-hint").textContent="正在更新草稿画面…";
  try {
    const response=await fetch(`/api/projects/${id}/preview`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body),signal:state.previewController.signal});
    if(!response.ok)throw await window.FrameHTTP.responseError(response,"画面更新失败，请重试。");
    const blob=await response.blob();
    if(revision!==state.previewRevision || state.current?.id!==id)return;
    if(state.previewObject)URL.revokeObjectURL(state.previewObject);
    state.previewObject=URL.createObjectURL(blob);$("#scene-preview").src=state.previewObject;
    $("#preview-hint").textContent="草稿画面 · 保存后即可导出";
  } catch(error) { if(error.name!=="AbortError" && revision===state.previewRevision)$("#preview-hint").textContent=window.FrameHTTP.friendlyError(error).message; }
}

async function saveBoard() {
  if (state.uploading) { showError("#save-error", "请等待照片上传完成后保存。"); return false; }
  if (!state.current || !state.dirty) return true;
  if (state.saving) return false;
  const id = state.current.id;
  try {
    const body = readEdit();
    state.saving = true;
    // Lock the editable controls until the saved snapshot is acknowledged.
    $$("#storyboard-panel input, #storyboard-panel textarea, #storyboard-panel select, #save-board").forEach(el => el.disabled = true);
    const project = await api(`/api/projects/${id}`, {method:"PUT",body:JSON.stringify(body)});
    if (state.current?.id !== id) return false;
    state.current = project; state.draft=E.editable(project); state.dirty = false; state.job = null; clearTimeout(state.poll);
    persistDraft(); resetHistory();
    $("#save-status").textContent = "已保存至本地";
    renderScenes(); updateBoardTotal(); showScene(Math.min(state.scene,project.scenes.length-1)); resetExport();
    showError("#save-error"); await refreshProjects();
    return true;
  } catch(error) { showError("#save-error",error.message + (error.message.includes("其他窗口") ? " 当前草稿仍在，可点击「另存副本」保留这一版。":"")); return false; }
  finally {
    state.saving = false;
    $$("#storyboard-panel input, #storyboard-panel textarea, #storyboard-panel select, #save-board").forEach(el => el.disabled = false);
  }
}

function updateTime() {
  const elapsed = state.draft ? state.draft.scenes.slice(0,state.scene).reduce((n,s)=>n+s.duration,0) : 0;
  $("#preview-time").innerHTML = `${seconds(elapsed)} <small>/ ${seconds(total())}</small>`;
}

function showScene(index) {
  const p=state.draft;if(!p)return;
  index=Math.max(0,Math.min(index,p.scenes.length-1));if(index!==state.scene)stopVoice();state.scene=index;
  $(".preview-transport").hidden=false;$("#timeline").hidden=false;
  $("#final-video").pause();$("#final-video").hidden=true;$("#sample-poster").hidden=true;$("#scene-preview").hidden=false;
  $("#scene-preview").alt=`分镜 ${index+1}：${p.scenes[index].heading}`;
  $("#preview-badge").textContent=`${state.dirty ? "草稿 · ":""}分镜 ${index+1} / ${p.scenes.length}`;
  $("#preview-spec").textContent=p.aspect;
  $("#preview-hint").textContent="分镜静帧预览 · 导出时背景缓动，店名与字幕保持稳定";
  $("#play-preview").disabled=false;$("#next-preview").disabled=false;
  $("#timeline").innerHTML=p.scenes.map((item,i)=>`<button data-preview="${i}" class="${i===index ? "active":""}" style="flex:${Number(item.duration)||1}" aria-label="跳转到分镜 ${i+1}" title="${esc(item.heading)} · ${item.duration}秒"></button>`).join("");
  $$(".scene-card").forEach((card,i)=>card.classList.toggle("active",i===index));
  updateStage(p.aspect);updateTime();refreshDraftPreview(index);
}

function stopPreview() {
  clearTimeout(state.playTimer); state.playing = false;
  $("#preview-stage").classList.remove("playing");
  $("#play-preview").innerHTML = icon("play");
  $("#play-preview").setAttribute("aria-label", "播放分镜预览");
}

function nextDuringPlayback() {
  if (!state.playing || !state.current) return;
  if (state.scene === state.draft.scenes.length-1) { stopPreview(); return; }
  showScene(state.scene+1);
  state.playTimer = setTimeout(nextDuringPlayback,state.draft.scenes[state.scene].duration*1000);
}

function togglePreview() {
  if (!state.current) return;
  if (state.playing) { stopPreview(); return; }
  if (state.scene === state.draft.scenes.length-1 || !$("#final-video").hidden) showScene(0);
  state.playing = true;
  $("#preview-stage").classList.add("playing");
  $("#play-preview").textContent = "Ⅱ";
  $("#play-preview").setAttribute("aria-label", "暂停分镜预览");
  state.playTimer = setTimeout(nextDuringPlayback,state.draft.scenes[state.scene].duration*1000);
}

function exportSettings() {
  const narration=$("#narration").checked,music=$("#music").checked;
  return {music,narration,quality:$("#quality").value,speech_rate:narration ? Number($("#speech-rate").value):210,music_volume:music ? Number($("#music-volume").value)/100:.5,music_style:music ? $("#music-style").value:"ambient"};
}
function settingsMatch(job) {
  const expected=exportSettings();
  return job.music===expected.music && Boolean(job.narration)===expected.narration && (job.quality || "720p")===expected.quality && (job.speech_rate || 210)===expected.speech_rate && (job.music_volume ?? .5)===expected.music_volume && (job.music_style || "ambient")===expected.music_style;
}
function restoreExportSettings(job) {
  $("#music").checked=job.music;$("#narration").checked=Boolean(job.narration);$("#quality").value=job.quality || "720p";
  $("#music-style").value=job.music_style || "ambient";
  const rate=String(job.speech_rate || 210);
  if(![...$("#speech-rate").options].some(option=>option.value===rate))$("#speech-rate").add(new Option(`自定 · ${rate}`,rate));
  $("#speech-rate").value=rate;$("#music-volume").value=Math.round((job.music_volume ?? .5)*100);updateAudioControls();
}
function updateAudioControls() {
  updateExportDimensions();
  $("#music-volume-row").hidden=!$("#music").checked;
  $("#music-settings").hidden=!$("#music").checked;
  $("#music-audio").volume=Number($("#music-volume").value)/100;
  $("#music-volume-value").textContent=`${$("#music-volume").value}%`;
  $("#voice-settings").hidden=!$("#narration").checked;
  $("#narration").disabled=!state.config?.narration_available && !$("#narration").checked;
  $("#voice-preview").disabled=!state.current || !state.config?.narration_available || Boolean(state.voiceController);
  $("#check-export").disabled=!state.current;
}
function updateExportDimensions() {
  const aspect=state.draft?.aspect || state.aspect;
  const size=({"9:16":[720,1280],"16:9":[1280,720],"1:1":[720,720]})[aspect] || [720,1280];
  const scale=$("#quality").value==="1080p" ? 1.5:1;
  $("#export-dimensions").textContent=`${size[0]*scale} × ${size[1]*scale} · ${aspect}`;
}
function stopVoice() {
  stopMusic();
  state.voiceRevision=(state.voiceRevision || 0)+1;state.voiceController?.abort();state.voiceController=null;
  $("#voice-audio").pause();$("#voice-audio").removeAttribute("src");$("#voice-audio").hidden=true;
  if(state.voiceObject){URL.revokeObjectURL(state.voiceObject);state.voiceObject=null;}
  $("#voice-preview").textContent="试听当前分镜";updateAudioControls();
}
function stopMusic() {
  $("#music-audio").pause();$("#music-preview").textContent="试听 8 秒";
}
$("#music-preview").addEventListener("click",async()=>{
  const audio=$("#music-audio");
  if(!audio.paused){stopMusic();return;}
  stopVoice();$("#final-video").pause();
  const url=`/api/music/${$("#music-style").value}.wav`;
  if(audio.getAttribute("src")!==url){audio.src=url;audio.load();}
  else audio.currentTime=0;
  try{await audio.play();$("#music-preview").textContent="暂停试听";}
  catch{toast("音乐试听未能开始，请重试。",true);}
});
$("#music-audio").addEventListener("ended",stopMusic);
$("#music-audio").addEventListener("error",()=>{if($("#music-audio").getAttribute("src")){stopMusic();toast("音乐暂时无法读取，请检查本地服务。",true);}});
function clearPreflight() {
  $("#preflight-result").innerHTML="<p>保存作品后，可检查照片、文字时长和导出环境。</p>";
}
function showPreflight(result) {
  $("#preflight-result").innerHTML=`<b>${result.ready ? "可以导出":"请先处理以下问题"}</b><p>${result.scenes} 幕 · ${result.photos} 张素材（${result.photo_scenes ?? result.photos} 幕有照片） · ${result.width} × ${result.height}</p>${result.blocking.length ? `<ul class="check-blocking">${result.blocking.map(item=>`<li>${esc(item)}</li>`).join("")}</ul>`:""}${result.warnings.length ? `<ul>${result.warnings.map(item=>`<li>${esc(item)}</li>`).join("")}</ul>`:"<p>照片和分镜时长检查通过。</p>"}`;
  if(!result.ready)$("#preflight-panel").open=true;
}
function resetExport() {
  $("#download-actions").hidden = true; $("#job-progress").hidden = true;
  $("#export-video").hidden = false; $("#export-video").disabled = !state.current;
  $("#export-video span").textContent = "导出视频";
  $("#export-note").textContent = state.current ? "在本机合成，通常需要几十秒" : "生成分镜，距离成片再近一步";
  if(state.current && !$("#final-video").hidden)showScene(state.scene);
}

function handleJob(job, historical=false) {
  if (state.current?.id !== job.project_id) return;
  state.job = job;
  const current = job.version === state.current.version && !state.dirty && settingsMatch(job);
  if (!current && !historical) { resetExport(); return; }
  if (["queued","rendering","cancelling"].includes(job.status)) {
    $("#job-progress").hidden = false; $("#download-actions").hidden = true;
    $("#job-message").textContent = job.message;
    $("#cancel-export").disabled=job.status==="cancelling";$("#cancel-export").textContent=job.status==="cancelling" ? "正在取消…":"取消本次导出";
    $("#job-percent").textContent = `${job.progress}%`; $("#progress").value = job.progress;
    $("#export-video").hidden = false; $("#export-video").disabled = true;
    $("#export-video span").textContent = "正在合成视频…";
    $("#export-note").textContent = "可继续浏览作品，重新打开会恢复任务进度";
    clearTimeout(state.poll); state.poll = setTimeout(()=>pollJob(job.id),1200);
  } else if (job.status === "completed") {
    clearTimeout(state.previewTimer);state.previewController?.abort();state.previewRevision++;
    clearTimeout(state.poll); stopPreview(); setStep(3);
    $("#job-progress").hidden = true; $("#export-video").hidden = true; $("#download-actions").hidden = false;
    $("#download-mp4").href = `/api/jobs/${job.id}/video.mp4?download=true`;
    $("#download-srt").href = `/api/jobs/${job.id}/subtitles.srt`;
    $("#download-json").href = job.materials ? `/api/jobs/${job.id}/materials/storyboard.json` : `/api/jobs/${job.id}/storyboard.json`;
    $("#download-bundle").hidden=!job.materials;$("#download-bundle").href=`/api/jobs/${job.id}/materials.zip`;
    for (const name of ["cover", "post"]) {
      $(`#download-${name}`).hidden = !job.materials;
      $(`#download-${name}`).href = `/api/jobs/${job.id}/materials/${name === "cover" ? "cover.png" : "post.txt"}`;
    }
    $("#export-note").textContent = `${historical && !current ? "历史成片 · ":""}已完成 · ${job.width && job.height ? job.width+" × "+job.height+" · ":""}${Number(Number(job.duration || 0).toFixed(1))} 秒 · ${(Number(job.bytes || 0)/1024/1024).toFixed(1)} MB${job.narration ? " · 中文配音" : ""}${job.music ? " · 氛围音轨" : job.narration ? "" : " · 无声"}`;
    updateStage(job.aspect || state.current.aspect);
    $("#scene-preview").hidden = true; $("#sample-poster").hidden = true; $("#final-video").hidden = false;
    $(".preview-transport").hidden = true; $("#timeline").hidden = true;
    const videoUrl = `/api/jobs/${job.id}/video.mp4`;
    $("#final-video").poster = job.materials ? `/api/jobs/${job.id}/materials/cover.png` : previewUrl(state.current,0);
    if ($("#final-video").getAttribute("src") !== videoUrl) { $("#final-video").src = videoUrl; $("#final-video").load(); }
    $("#preview-badge").textContent = historical && !current ? `历史版本 ${job.version}` : "成片就绪";
    $("#preview-hint").textContent = "使用播放器查看实际成片，支持全屏播放";
    showError("#export-error");
  } else if(job.status==="cancelled") {
    clearTimeout(state.poll);resetExport();showError("#export-error");
    $("#export-note").textContent="本次导出已取消，作品和照片已保留。";refreshHistory();
  } else {
    resetExport(); showError("#export-error",job.error || "导出失败，请重试。");
    $("#export-video span").textContent = "重新导出视频";
  }
}

async function pollJob(id) {
  try {
    const job = await api(`/api/jobs/${id}`);
    if (state.job?.id !== id) return;
    showError("#export-error"); handleJob(job);
    if (job.status === "completed") { toast("成片已就绪，可以播放和下载了。"); refreshHistory(); }
  } catch (error) {
    if (state.job?.id !== id) return;
    showError("#export-error",`${error.message} 正在重试连接。`);
    state.poll = setTimeout(()=>pollJob(id),5000);
  }
}

$("#brief-form").addEventListener("submit",async event=> {
  event.preventDefault();
  if(state.creating)return;
  const prompt = $("#prompt").value.trim();
  if (state.briefKind === "creative" && prompt.length<5) { showError("#form-error","请至少输入 5 个字的创意描述。"); return; }
  const serial = ++state.serial;
  state.creating=true;
  $$("[data-showcase]").forEach(el=>el.disabled=true);
  $("#generate").disabled = true; $("#generate").classList.add("loading");
  $("#generate span").textContent = $("#generation-mode").value === "ai" ? "AI 正在编写故事…" : "正在编排分镜…";
  showError("#form-error");
  try {
    const settings = {style:state.style, aspect:state.aspect, duration:Number($("#duration").value)};
    const merchant = {...readMerchantFields("merchant"),industry:state.industry || "coffee",scenario:$("#merchant-scenario").value || "visit"};
    if(state.briefKind==="merchant")E.validateMerchant(merchant);
    const body = state.briefKind === "merchant" ? {...settings, ...merchant, example:state.merchantExample} : {...settings, prompt, mode:$("#generation-mode").value};
    const project = await api(state.briefKind === "merchant" ? "/api/merchant-projects" : "/api/projects", {method:"POST",body:JSON.stringify(body)});
    await refreshProjects();
    if (serial !== state.serial) return;
    state.current = project; state.dirty = false; state.scene = 0; state.job = null;
    displayBoard(); renderRecent(); toast("分镜已生成并保存，可以开始打磨故事了。");
  } catch (error) { if (serial === state.serial) showError("#form-error",error.message); }
  finally { state.creating=false;$$("[data-showcase]").forEach(el=>el.disabled=false);if (serial === state.serial) { $("#generate").disabled = false; $("#generate").classList.remove("loading"); $("#generate span").textContent = "生成我的分镜"; } }
});

$("#prompt").addEventListener("input",()=> { $("#prompt-count").textContent = `${$("#prompt").value.length} / 800`; showError("#form-error"); });
$("#examples").addEventListener("click",event=> {
  const button = event.target.closest("[data-example]"); if (!button) return;
  const example = state.config.examples[Number(button.dataset.example)];
  $("#prompt").value = example.prompt; $("#prompt").dispatchEvent(new Event("input")); setStyle(example.style);
});
$(".style-options").addEventListener("click",event=> { const button=event.target.closest("[data-style]"); if(button)setStyle(button.dataset.style); });
$("#aspect-options").addEventListener("click",event=> { const button=event.target.closest("[data-aspect]"); if(button)setAspect(button.dataset.aspect); });
$("#duration").addEventListener("change",updateTime);
$("#generation-mode").addEventListener("change",()=> { $("#generation-note").textContent = $("#generation-mode").value === "ai" ? "创意将发送至 DeepSeek 编写分镜，可能产生 API 费用。" : "本地模板将创意匹配到预设文案，可在下一步自由修改。"; });
$("#scenes").addEventListener("input",event=> {
  const card=event.target.closest(".scene-card"); if(!card)return;
  const field=event.target.dataset.field; if(!field)return;
  const output=card.querySelector(`[data-output="${field}"]`);
  if(output)output.textContent=field==="zoom" ? `${Number(event.target.value).toFixed(1)}×` : `${Math.round(Number(event.target.value)*100)}%`;
  if(field==="caption")card.querySelector(".scene-counter").textContent=`${event.target.value.length} / 96`;
  if(field==="voiceover"){
    card.querySelector(".voice-counter").textContent=`${event.target.value.length} / 160`;
    card.querySelector(".scene-voice summary small").textContent=event.target.value.trim() ? "已自定义":"可选 · 默认朗读字幕";
  }
  markDirty(); updateBoardTotal();
});
[$("#project-title"),$("#board-style"),$("#board-aspect"),$("#custom-color"),$("#accent-color")].forEach(el=>el.addEventListener("input",markDirty));
document.addEventListener("click",event=> {
  const project=event.target.closest("[data-project]"); if(project)openProject(project.dataset.project);
  const preview=event.target.closest("[data-preview]"); if(preview){stopPreview();showScene(Number(preview.dataset.preview));if(matchMedia("(max-width:600px)").matches)$(".preview-panel").scrollIntoView({behavior:"smooth",block:"start"});}
});
$("#save-board").addEventListener("click",async()=> { if(await saveBoard())toast("分镜已保存，预览已更新。"); });
$("#save-top").addEventListener("click",async()=> { if(await saveBoard())toast("分镜已保存，预览已更新。"); });
$("#create-variants").addEventListener("click",()=>{
  if(!state.current || !canLeave())return;
  $("#variants-form").hidden=false;$("#variants-results").hidden=true;showError("#variants-error");
  $$('[name="variant-aspect"]').forEach(el=>el.checked=el.value!==$("#board-aspect").value);
  $("#variants-dialog").showModal();
});
$("#variants-close").addEventListener("click",()=>{if(!state.saving)$("#variants-dialog").close();});
$("#variants-dialog").addEventListener("cancel",event=>{if(state.saving)event.preventDefault();});
$("#variants-form").addEventListener("submit",async event=>{
  event.preventDefault();if(state.saving || !state.current)return;
  const aspects=$$('[name="variant-aspect"]:checked').map(el=>el.value);
  if(!aspects.length){showError("#variants-error","请至少选择一种画幅。");return;}
  try {
    const body={...readEdit(),aspects};state.saving=true;
    $("#variants-submit").disabled=true;$("#variants-submit").textContent="正在创建独立作品…";showError("#variants-error");
    const projects=await api(`/api/projects/${state.current.id}/variants`,{method:"POST",body:JSON.stringify(body)});
    $("#variants-form").hidden=true;$("#variants-results").hidden=false;
    $("#variants-results").innerHTML='<p>已创建 '+projects.length+' 个独立作品。打开后检查构图，原草稿仍保留。</p>'+projects.map(project=>`<button class="variant-result" data-open-variant="${project.id}"><img src="${previewUrl(project,project.cover_scene||0)}" alt="${esc(project.aspect)} 画幅预览"><span><b>${esc(project.title)}</b><small>打开作品，检查构图与字幕 →</small></span></button>`).join("");
    await refreshProjects();
  } catch(error){showError("#variants-error",error.message);}
  finally {state.saving=false;$("#variants-submit").disabled=false;$("#variants-submit").textContent="创建选定画幅";}
});
$("#variants-results").addEventListener("click",event=>{
  const button=event.target.closest("[data-open-variant]");if(!button || state.saving)return;
  $("#variants-dialog").close();openProject(button.dataset.openVariant);
});
$("#fork-draft").addEventListener("click",async()=>{
  if(!state.current || state.saving || state.uploading)return;
  try {
    const id=state.current.id,body=readEdit();state.saving=true;
    $$("#storyboard-panel input,#storyboard-panel textarea,#storyboard-panel select").forEach(el=>el.disabled=true);
    const copy=await api(`/api/projects/${id}/fork`,{method:"POST",body:JSON.stringify(body)});
    state.saving=false;
    // The draft is safe in the new project; keep the original's saved version.
    state.dirty=false;persistDraft();state.current=copy;state.scene=0;state.job=null;
    clearTimeout(state.poll);stopPreview();stopVoice();displayBoard();setPage("studio");
    state.assets=await api(`/api/projects/${copy.id}/assets`);
    await refreshProjects();
    toast("当前草稿已另存为独立副本。");
  } catch(error){showError("#save-error",error.message);}
  finally {state.saving=false;$$("#storyboard-panel input,#storyboard-panel textarea,#storyboard-panel select").forEach(el=>el.disabled=false);}
});
$("#export-video").addEventListener("click",async()=> {
  if(!state.current || state.exporting)return;
  stopVoice();
  state.exporting=true;
  $("#export-video").disabled=true; showError("#export-error");
  try {
    if(!(await saveBoard())) { $("#export-video").disabled=false; return; }
    const id=state.current.id;
    const settings=exportSettings(),body={version:state.current.version,...settings};
    $("#export-video").disabled=true;
    const check=await api(`/api/projects/${id}/preflight`,{method:"POST",body:JSON.stringify(body)});
    if(state.current?.id!==id)return;
    showPreflight(check);
    if(!check.ready)throw new Error(check.blocking.join(" "));
    if(state.dirty || state.current.version!==body.version || JSON.stringify(exportSettings())!==JSON.stringify(settings))throw new Error("内容或导出设置已改变，请重新导出。");
    const job=await api(`/api/projects/${id}/render`,{method:"POST",body:JSON.stringify(body)});
    refreshQueue();
    if(state.current?.id===id)handleJob(job);
  } catch(error){showError("#export-error",error.message);$("#export-video").disabled=false;}
  finally{state.exporting=false;}
});
for (const control of [$("#music"), $("#narration"),$("#quality"),$("#speech-rate"),$("#music-volume"),$("#music-style")]) control.addEventListener("change",async()=> {
  stopVoice();updateAudioControls();clearPreflight();
  clearTimeout(state.poll); state.job=null; resetExport();
  if(!state.current)return;
  showScene(state.scene);
  const id=state.current.id;
  try{
    const jobs=await api(`/api/projects/${id}/jobs`);
    if(state.current?.id!==id)return;
    const matching=jobs.find(j=>j.version===state.current.version&&settingsMatch(j));
    if(matching)handleJob(matching);
  }catch(error){toast(error.message,true);}
});
$("#return-board-preview").addEventListener("click",()=>{showScene(0);setStep(2);});
$("#music-volume").addEventListener("input",updateAudioControls);
$("#check-export").addEventListener("click",async()=>{
  if(!state.current)return;$("#check-export").disabled=true;
  try{
    if(!(await saveBoard()))return;
    const id=state.current.id,body={version:state.current.version,...exportSettings()};
    const result=await api(`/api/projects/${id}/preflight`,{method:"POST",body:JSON.stringify(body)});
    if(state.current?.id===id)showPreflight(result);
  }catch(error){showError("#export-error",error.message);}
  finally{updateAudioControls();}
});
$("#cancel-export").addEventListener("click",async()=>{
  if(!state.job)return;const id=state.job.id;$("#cancel-export").disabled=true;
  try{const job=await api(`/api/jobs/${id}/cancel`,{method:"POST",body:"{}"});if(state.job?.id===id)handleJob(job);}
  catch(error){showError("#export-error",error.message);$("#cancel-export").disabled=false;}
});
$("#voice-preview").addEventListener("click",async()=>{
  if(!state.current || !state.config?.narration_available)return;
  stopVoice();const revision=state.voiceRevision,scene=state.draft.scenes[state.scene],text=scene.voiceover || scene.caption;
  if(!text.trim()){toast("请先填写当前分镜的字幕。",true);return;}
  const controller=new AbortController();state.voiceController=controller;updateAudioControls();
  $("#voice-preview").textContent="正在准备试听…";
  const timeout=setTimeout(()=>controller.abort(),80000);
  try{
    const response=await fetch("/api/narration/preview",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text,speech_rate:Number($("#speech-rate").value)}),signal:controller.signal});
    if(!response.ok)throw await window.FrameHTTP.responseError(response,"试听失败，请重试。");
    const blob=await response.blob();if(revision!==state.voiceRevision)return;
    state.voiceObject=URL.createObjectURL(blob);$("#voice-audio").src=state.voiceObject;$("#voice-audio").hidden=false;
    try{await $("#voice-audio").play();}catch{toast("试听已准备好，请点击播放器播放。");}
  }catch(error){if(revision===state.voiceRevision)toast(error.name==="AbortError" ? "试听超时，请稍后重试。":window.FrameHTTP.friendlyError(error).message,true);}
  finally{clearTimeout(timeout);if(revision===state.voiceRevision){state.voiceController=null;$("#voice-preview").textContent="重新试听当前分镜";updateAudioControls();}}
});
$("#play-preview").addEventListener("click",togglePreview);
$("#next-preview").addEventListener("click",()=>{if(state.current){stopPreview();showScene((state.scene+1)%state.draft.scenes.length);}});
$("#new-project").addEventListener("click",newProject);$("#library-new").addEventListener("click",newProject);$("#back-brief").addEventListener("click",newProject);
$("#nav-studio").addEventListener("click",()=>setPage("studio"));
$("#nav-library").addEventListener("click",async()=>{setPage("library");try{await refreshProjects();}catch(error){toast(error.message,true);}});
$("#project-search").addEventListener("input",renderLibrary);
$("#step-idea").addEventListener("click",()=>{if(state.current)newProject();});
$("#step-board").addEventListener("click",()=>{if(state.current){setStep(2);showScene(0);$("#storyboard-panel").scrollIntoView({behavior:"smooth",block:"start"});}});
$("#step-export").addEventListener("click",()=>{if(state.current){setStep(3);$(".export-panel").scrollIntoView({behavior:"smooth",block:"center"});}});
for(const id of ["help-open","help-top"])$(`#${id}`).addEventListener("click",()=>$("#help-dialog").showModal());
for(const id of ["help-close","help-start"])$(`#${id}`).addEventListener("click",()=>$("#help-dialog").close());
$("#help-dialog").addEventListener("click",event=>{if(event.target===$("#help-dialog")){const r=event.target.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)event.target.close();}});
window.addEventListener("beforeunload",()=>{if(state.dirty)persistDraft();});
document.addEventListener("visibilitychange",()=>{if(document.hidden)stopPreview();});
$("#scene-preview").addEventListener("error",()=>{$("#preview-hint").textContent="预览暂时无法加载，请重新打开作品或检查服务。";});
$("#final-video").addEventListener("error",()=>{
  if(!$("#final-video").getAttribute("src")||!state.current)return;
  resetExport(); showError("#export-error","成片文件无法加载，请重新导出。也可检查浏览器是否支持 H.264 视频。");
});

async function init(){
  if(state.initializing)return;
  state.initializing=true;
  try{
    const [config,,health]=await Promise.all([api("/api/config"),refreshProjects(),api("/api/health")]);
    state.config=config;
    refreshQueue();
    setupMerchantCatalog();
    $("#showcase-section").hidden=!config.showcases?.length;
    $("#showcase-options").innerHTML=(config.showcases||[]).map(item=>`<button type="button" data-showcase="${item.id}" class="showcase-card"><img src="${item.image}" alt="${esc(item.title)} AI 演示照片" loading="lazy"><span>${esc(item.title)} <i>↗</i></span><small>${esc(item.description)}</small></button>`).join("");
    $("#narration").disabled = !config.narration_available;
    $("#narration").checked = config.narration_available;
    $("#narration-note").textContent = config.narration_note + "。开启后自动延长过短镜头，最长 120 秒。";
    updateAudioControls();
    $("#examples").innerHTML=config.examples.map((ex,i)=>`<button type="button" class="example-chip" data-example="${i}">${esc(ex.label)} ↗</button>`).join("");
    const ai=$("#generation-mode option[value=ai]");ai.disabled=!config.ai_available;ai.textContent=config.ai_available?"DeepSeek AI · 已连接":"DeepSeek AI · 尚未配置";
    if(health.status!=="ok")throw new Error("视频合成环境未就绪，请查看启动日志。");
    state.initialized=true;connectionStatus(true);showError("#form-error");
    await restoreRoute();
  }catch(error){connectionStatus(false);showError("#form-error",error.message);}
  finally{state.initializing=false;}
}
$("#retry-connection").addEventListener("click",async()=>{
  $("#retry-connection").disabled=true;
  try{
    if(!state.initialized){await init();return;}
    await api("/api/health");await refreshProjects();connectionStatus(true);
    toast("已重新连接，当前草稿仍然保留。");
  }catch(error){connectionStatus(false);toast(error.message,true);}
  finally{$("#retry-connection").disabled=false;}
});
function setBriefKind(kind) {
  state.briefKind = kind;
  $("#merchant-fields").hidden = kind !== "merchant";
  $("#creative-fields").hidden = kind !== "creative";
  $$("#merchant-fields input, #merchant-fields select, #merchant-fields button").forEach(el => el.disabled = kind !== "merchant");
  $("#prompt").disabled = kind !== "creative"; $("#prompt").required = kind === "creative";
  $(".generation-mode").hidden = kind !== "creative";
  $$("[data-brief]").forEach(el => { el.classList.toggle("selected", el.dataset.brief === kind); el.setAttribute("aria-pressed", el.dataset.brief === kind); });
  $("#generation-note").textContent = kind === "merchant" ? "门店模板 · 无需密钥 · 信息只保存在本机" : "本地模板可自由修改；选择 AI 时会将创意发送至 DeepSeek。";
}
$("#showcase-options").addEventListener("click",async event=>{
  const button=event.target.closest("[data-showcase]");
  if(!button || !canLeave())return;
  state.creating=true;
  $$("[data-showcase],#generate").forEach(el=>el.disabled=true);showError("#form-error");
  try {
    const project=await api(`/api/showcases/${button.dataset.showcase}`,{method:"POST",body:JSON.stringify({aspect:state.aspect})});
    state.creating=false;state.current=project;state.dirty=false;state.scene=0;state.job=null;
    clearTimeout(state.poll);stopPreview();displayBoard();setPage("studio");
    state.assets=await api(`/api/projects/${project.id}/assets`);
    await refreshProjects();
    toast("示例已就绪，可以直接预览、编辑或导出。");
    $("#storyboard-panel").scrollIntoView({behavior:"smooth",block:"start"});
  } catch(error){showError(state.current ? "#save-error":"#form-error",error.message);}
  finally {state.creating=false;$$("[data-showcase],#generate").forEach(el=>el.disabled=false);}
});
$(".brief-tabs").addEventListener("click", event => { const button = event.target.closest("[data-brief]"); if (button) setBriefKind(button.dataset.brief); });
$("#merchant-example").addEventListener("click", () => {
  const category=industry();if(!category)return;
  const example={...category.example};
  if($("#merchant-scenario").value==="offer")example.offer="演示活动：本周六到店体验（虚构活动）";
  fillMerchantFields("merchant",example);
  state.merchantExample = true; $("#merchant-example-note").hidden = false; setStyle(category.style);
});
const merchantKeys=["store_name","product","selling_point","offer","address","cta"];
function readMerchantFields(prefix) {
  return Object.fromEntries(merchantKeys.map(key=>[key,$(`#${prefix}-${key.replaceAll("_","-")}`).value.trim()]));
}
function fillMerchantFields(prefix, values) {
  for(const key of merchantKeys)$(`#${prefix}-${key.replaceAll("_","-")}`).value=values[key] || "";
}
function industry(id=state.industry || "coffee") { return state.config?.merchant_catalog?.industries.find(item=>item.id===id); }
function setupMerchantCatalog() {
  const catalog=state.config.merchant_catalog;
  $("#industry-options").innerHTML=catalog.industries.map(item=>`<button type="button" data-industry="${item.id}" aria-pressed="false"><span>${item.icon}</span>${esc(item.label)}</button>`).join("");
  $("#merchant-scenario").innerHTML=options(catalog.scenarios.map(item=>[item.id,item.label]),"visit");
  selectIndustry(state.industry || "coffee");renderMerchantReuse();setBriefKind(state.briefKind);
  if(state.current)renderMerchantSummary();
}
function selectIndustry(id) {
  const category=industry(id);if(!category)return;
  state.industry=id;
  $$("[data-industry]").forEach(button=>{button.classList.toggle("selected",button.dataset.industry===id);button.setAttribute("aria-pressed",button.dataset.industry===id);});
  $("#merchant-store-name").placeholder=`例如：${category.example.store_name.replace("（演示）","")}`;
  $("#merchant-product").placeholder=`例如：${category.example.product}`;
  $("#merchant-selling-point").placeholder=category.example.selling_point;
  $("#photo-suggestions").innerHTML=category.photos.map(text=>`<li>${esc(text)}</li>`).join("");
  if(!$("#merchant-cta").value || state.lastDefaultCta===$("#merchant-cta").value || $("#merchant-cta").value==="欢迎到店，喝一杯喜欢的咖啡。")$("#merchant-cta").value=category.example.cta;
  state.lastDefaultCta=category.example.cta;updateScenario();
}
function updateScenario() {
  const category=industry(), scenario=state.config?.merchant_catalog?.scenarios.find(item=>item.id===$("#merchant-scenario").value);
  if(!category || !scenario)return;
  $("#merchant-category-title").textContent=`${category.label} · ${scenario.label}`;
  $("#scenario-note").textContent=scenario.description;
  $("#merchant-offer").required=scenario.id==="offer";
  $("#offer-requirement").textContent=scenario.id==="offer" ? "活动宣传必填" : "可选";
}
function renderMerchantReuse() {
  const select=$("#merchant-reuse"),selected=select.value,seen=new Set();
  const projects=state.projects.filter(p=>{const key=p.merchant?.store_name;if(!key || seen.has(key) || p.archived)return false;seen.add(key);return true;});
  select.innerHTML='<option value="">从已有作品选择…</option>'+projects.map(p=>`<option value="${p.id}">${esc(p.merchant.store_name)}${p.example ? " · 示例":""}</option>`).join("");
  if(projects.some(p=>p.id===selected))select.value=selected;
}
function reuseMerchant(profile, example=false) {
  selectIndustry(profile.industry || "coffee");
  $("#merchant-scenario").value=profile.scenario || "visit";
  fillMerchantFields("merchant",profile);updateScenario();
  state.merchantExample=Boolean(example);$("#merchant-example-note").hidden=!example;
}
function renderMerchantSummary() {
  const merchant=state.draft?.merchant;$("#merchant-summary").hidden=!merchant;if(!merchant)return;
  $("#merchant-summary-name").textContent=merchant.store_name;
  $("#merchant-summary-detail").textContent=`${industry(merchant.industry)?.label || "门店宣传"} · ${merchant.product}`;
}
$("#industry-options").addEventListener("click",event=>{const button=event.target.closest("[data-industry]");if(button)selectIndustry(button.dataset.industry);});
$("#merchant-scenario").addEventListener("change",updateScenario);
$("#merchant-reuse").addEventListener("change",event=>{const project=state.projects.find(p=>p.id===event.target.value);if(project?.merchant){reuseMerchant(project.merchant,project.example);toast("门店资料已填入，可以调整产品和活动后生成新作品。");}});
$("#edit-merchant").addEventListener("click",()=>{if(state.saving || state.uploading)return;fillMerchantFields("edit",state.draft.merchant);showError("#merchant-edit-error");$("#merchant-dialog").showModal();});
$("#merchant-edit-close").addEventListener("click",()=>$("#merchant-dialog").close());
$("#merchant-edit-form").addEventListener("submit",event=>{
  event.preventDefault();
  try{const merchant=E.validateMerchant({...state.draft.merchant,...readMerchantFields("edit")});const edit=collectEdit();edit.merchant=merchant;applyDraft(edit);$("#merchant-dialog").close();toast("资料已应用到草稿，请核对分镜字幕后保存。");}
  catch(error){showError("#merchant-edit-error",error.message);}
});
$("#reuse-merchant").addEventListener("click",()=>{
  if(!canLeave() || !state.draft?.merchant)return;
  const merchant=E.clone(state.draft.merchant),example=state.current.example,style=state.draft.style,aspect=state.draft.aspect;
  newProject();setBriefKind("merchant");reuseMerchant(merchant,example);setStyle(style);setAspect(aspect);toast("已带入门店资料，修改本次宣传内容即可。");
});

async function uploadFiles(files, target=null) {
  if (!state.current || state.uploading || state.saving) return;
  const id=state.current.id;state.uploading++;let assigned=0,uploaded=0;
  $("#editing-note").textContent="正在上传照片，请稍候…";
  try {
    for (const file of files) {
      if(file.size>8*1024*1024)throw new Error(`${file.name} 超过 8 MB，请缩小后上传。`);
      const photo=await api(`/api/projects/${id}/assets`,{method:"POST",body:file,headers:{"Content-Type":file.type || "application/octet-stream","X-File-Name":encodeURIComponent(file.name)}});
      uploaded++;state.draft=collectEdit();
      let index=target;
      if(index===null)index=state.draft.scenes.findIndex(item=>!item.asset_id);
      if(index===-1 && state.draft.scenes.length<8 && total()<=58) {
        state.draft=E.transform(state.draft,"add",state.draft.scenes.length-1);index=state.draft.scenes.length-1;
      }
      if(index!==null && index>=0 && index<state.draft.scenes.length) {
        state.draft.scenes[index].asset_id=photo.asset_id;state.draft.scenes[index].crop_x=.5;state.draft.scenes[index].crop_y=.5;state.draft.scenes[index].zoom=1;assigned++;
      }
      renderScenes();markDirty({force:true});
      $("#editing-note").textContent=`已上传 ${uploaded} / ${files.length} 张照片`;
    }
    toast(`已上传 ${uploaded} 张照片，已分配 ${assigned} 个分镜。`);
  } catch(error) { showError("#save-error",`${error.message} 已完成的 ${uploaded} 张照片已保留。`); }
  finally {
    state.uploading--;$("#batch-photos").value="";
    $("#editing-note").textContent="1–8 个分镜 · 总时长不超过 60 秒 · 修改自动暂存为本机草稿";
    try { state.assets=await api(`/api/projects/${id}/assets`); } catch(error){toast(error.message,true);}
  }
}
$("#scenes").addEventListener("change", event=>{
  const input=event.target.closest("[data-upload]");if(input?.files[0])uploadFiles([...input.files],Number(input.dataset.upload));
});
$("#batch-photos").addEventListener("change",event=>uploadFiles([...event.target.files]));
$("#scenes").addEventListener("click",async event=>{
  if(state.saving || state.uploading)return;
  const card=event.target.closest(".scene-card");if(!card)return;
  const index=Number(card.dataset.index);
  const action=event.target.closest("[data-scene-action]");
  if(action) {
    try {
      const name=action.dataset.sceneAction;state.draft=collectEdit();
      const next=E.transform(state.draft,name,index);
      state.scene=name==="up" ? Math.max(0,index-1) : name==="down" || name==="duplicate" ? Math.min(index+1,next.scenes.length-1) : Math.min(index,next.scenes.length-1);
      applyDraft(next);
    } catch(error){toast(error.message,true);}
  }
  if(event.target.closest(".remove-photo")) {state.draft=collectEdit();state.draft.scenes[index].asset_id=null;applyDraft(state.draft);}
  if(event.target.closest("[data-media]")) {
    state.mediaTarget=index;$("#media-grid").innerHTML="<p>正在读取照片…</p>";$("#media-dialog").showModal();
    const id=state.current.id;
    try {
      const assets=await api(`/api/projects/${id}/assets`);if(state.current?.id!==id)return;state.assets=assets;
      $("#media-grid").innerHTML=assets.length ? assets.map(asset=>`<button class="media-item" data-asset="${asset.asset_id}"><img src="${assetUrl(asset.asset_id)}" alt="${esc(asset.name)}" loading="lazy"><span>${esc(asset.name)}</span><small>${asset.width} × ${asset.height}</small></button>`).join("") : "<p>还没有照片。先上传照片，再在其他分镜重复使用。</p>";
    }catch(error){$("#media-grid").textContent=error.message;}
  }
});
$("#media-close").addEventListener("click",()=>$("#media-dialog").close());
$("#media-grid").addEventListener("click",event=>{
  const button=event.target.closest("[data-asset]");if(!button)return;
  state.draft=collectEdit();const scene=state.draft.scenes[state.mediaTarget];if(!scene)return;
  scene.asset_id=button.dataset.asset;scene.crop_x=.5;scene.crop_y=.5;scene.zoom=1;
  state.scene=state.mediaTarget;applyDraft(state.draft);$("#media-dialog").close();
});
$("#add-scene").addEventListener("click",()=>{
  if(state.uploading || state.saving)return;
  try {const next=E.transform(collectEdit(),"add",state.draft.scenes.length-1);state.scene=next.scenes.length-1;applyDraft(next);}
  catch(error){toast(error.message,true);}
});
function undoDraft(){if(state.history.length<2 || state.uploading || state.saving)return;state.future.push(state.history.pop());applyDraft(state.history[state.history.length-1],false);}
function redoDraft(){if(!state.future.length || state.uploading || state.saving)return;const edit=state.future.pop();state.history.push(E.clone(edit));applyDraft(edit,false);}
$("#undo-edit").addEventListener("click",undoDraft);$("#redo-edit").addEventListener("click",redoDraft);
$("#restore-draft").addEventListener("click",()=>{if(state.pendingDraft){applyDraft(state.pendingDraft.edit);state.pendingDraft=null;toast("草稿已恢复，请检查后保存。");}});
$("#discard-draft").addEventListener("click",()=>{state.pendingDraft=null;$("#draft-banner").hidden=true;persistDraft();});
document.addEventListener("keydown",event=>{
  if(!(event.metaKey || event.ctrlKey) || !state.current || $("#storyboard-panel").hidden)return;
  if(event.key.toLowerCase()==="s"){event.preventDefault();saveBoard().then(ok=>{if(ok)toast("分镜已保存。");});}
  const typing=event.target.matches("input,textarea,select");
  if(!typing && event.key.toLowerCase()==="z"){event.preventDefault();event.shiftKey ? redoDraft():undoDraft();}
});
$("#library-filter").addEventListener("change",renderLibrary);
$("#library-grid").addEventListener("click",async event=>{
  const button=event.target.closest("[data-project-action]");if(!button || !canLeave())return;
  const id=button.dataset.id,action=button.dataset.projectAction;button.disabled=true;
  try {
    if(state.current?.id===id && !(await saveBoard()))return;
    const project=state.projects.find(p=>p.id===id);
    if(action==="duplicate"){
      const copy=await api(`/api/projects/${id}/duplicate`,{method:"POST",body:JSON.stringify({version:project.version})});
      await refreshProjects();await openProject(copy.id);toast("作品已复制，照片和文案可独立修改。");
    } else {
      await api(`/api/projects/${id}/archive`,{method:"POST",body:JSON.stringify({version:project.version,archived:action==="archive"})});
      if(state.current?.id===id){state.dirty=false;newProject();setPage("library");}
      await refreshProjects();toast(action==="archive" ? "作品已归档，可在已归档列表恢复。":"作品已恢复。");
    }
  }catch(error){toast(error.message,true);await refreshProjects();}
  finally{button.disabled=false;}
});
function renderHistory(jobs) {
  $("#history-count").textContent=jobs.length;$("#history-panel").hidden=!jobs.length;
  $("#history-list").innerHTML=jobs.slice(0,12).map(job=>`<div class="history-item"><div><b>版本 ${job.version} · ${Number(Number(job.duration || 0).toFixed(1))} 秒</b><small>${new Date(job.created_at).toLocaleString("zh-CN",{month:"numeric",day:"numeric",hour:"2-digit",minute:"2-digit"})} · ${job.quality || "720p"} · ${job.narration ? "中文配音":"无配音"}${job.music ? " · 音乐":""}</small></div>${job.status==="completed" ? `<button data-history-job="${job.id}">查看</button>` : `<span>${esc(({failed:"失败",queued:"等待中",rendering:"合成中",cancelling:"取消中",cancelled:"已取消"})[job.status] || job.status)}</span>`}</div>`).join("");
}
async function refreshHistory(){
  if(!state.current)return;const id=state.current.id;
  try{const jobs=await api(`/api/projects/${id}/jobs`);if(state.current?.id===id)renderHistory(jobs);}catch(error){toast(error.message,true);}
}
$("#history-list").addEventListener("click",async event=>{
  const button=event.target.closest("[data-history-job]");if(!button)return;
  try{handleJob(await api(`/api/jobs/${button.dataset.historyJob}`),true);}catch(error){toast(error.message,true);}
});

function updateDock() {
  $("#mobile-dock").hidden=!state.current || $("#studio-view").hidden;
  document.body.classList.toggle("has-mobile-dock",!$("#mobile-dock").hidden);
}

async function refreshQueue() {
  clearTimeout(state.queueTimer);
  if(state.queueLoading || state.queueBusy){state.queueTimer=setTimeout(refreshQueue,3000);return;}
  state.queueLoading=true;
  try {
    const result=await api("/api/jobs?limit=20");state.queueJobs=result.jobs;
    $("#queue-count").textContent=result.active;$("#queue-count").hidden=!result.active;
    $("#queue-open").classList.toggle("has-active",result.active>0);
    $("#queue-summary").textContent=result.active ? `${result.active} 个任务正在处理或等待。可继续编辑作品；保持本地服务运行即可。` : "最近 20 次导出记录。成片完成后可从这里打开或下载。";
    const status={queued:"等待中",rendering:"合成中",cancelling:"取消中",cancelled:"已取消",completed:"已完成",failed:"失败"};
    $("#queue-list").innerHTML=result.jobs.length ? result.jobs.map(job=>{
      const active=["queued","rendering","cancelling"].includes(job.status);
      const title=job.title || "历史作品";
      return `<article class="queue-item"><div class="queue-item-title"><b>${esc(title)}</b><span class="${job.status}">${status[job.status] || esc(job.status)}</span></div><small>${esc(job.aspect || "")} · ${job.quality || "720p"} · 版本 ${job.version} · ${new Date(job.created_at).toLocaleString("zh-CN",{month:"numeric",day:"numeric",hour:"2-digit",minute:"2-digit"})}</small>${active ? `<progress max="100" value="${job.progress || 0}" aria-label="${esc(title)}导出进度"></progress><p>${esc(job.queue_position ? "排队第 "+job.queue_position+" 位" : job.message || "处理中")} · ${job.progress || 0}%</p>` : job.status==="failed" ? `<p class="queue-failure">${esc(job.error || "导出失败，请打开作品后重试。")}</p>` : ""}<div class="queue-item-actions"><button data-queue-action="open" data-job="${job.id}">${job.status==="completed" ? "查看成片":"打开作品"}</button>${active ? `<button data-queue-action="cancel" data-job="${job.id}" ${job.status==="cancelling" ? "disabled":""}>取消导出</button>` : job.status==="completed" ? `<a href="/api/jobs/${job.id}/video.mp4?download=true" download>下载 MP4</a>` : ""}</div></article>`;
    }).join("") : '<p class="empty-queue">还没有导出记录，完成分镜后试试「导出视频」。</p>';
    showError("#queue-error");
  } catch(error){if($("#queue-dialog").open)showError("#queue-error",error.message);}
  finally {state.queueLoading=false;state.queueTimer=setTimeout(refreshQueue,document.hidden ? 30000 : (state.queueJobs?.some(job=>["queued","rendering","cancelling"].includes(job.status)) ? 4000 : 15000));}
}
$("#queue-open").addEventListener("click",()=>{$("#queue-dialog").showModal();refreshQueue();});
$("#queue-close").addEventListener("click",()=>$("#queue-dialog").close());
$("#queue-refresh").addEventListener("click",refreshQueue);
$("#queue-list").addEventListener("click",async event=>{
  const button=event.target.closest("[data-queue-action]");if(!button || state.queueBusy)return;
  const job=state.queueJobs?.find(item=>item.id===button.dataset.job);if(!job)return;
  if(button.dataset.queueAction==="open"){
    if(!canLeave())return;
    $("#queue-dialog").close();await openProject(job.project_id);
    if(state.current?.id===job.project_id && job.status==="completed")handleJob(job,true);
    return;
  }
  state.queueBusy=true;button.disabled=true;
  try {
    const updated=await api(`/api/jobs/${job.id}/cancel`,{method:"POST",body:"{}"});
    if(state.job?.id===job.id)handleJob(updated,true);
    toast("已请求取消，作品与照片会保留。");
  }catch(error){showError("#queue-error",error.message);}
  finally{state.queueBusy=false;refreshQueue();}
});
document.addEventListener("visibilitychange",()=>{if(!document.hidden)refreshQueue();});
$("#mobile-dock").addEventListener("click",async event=>{
  const button=event.target.closest("[data-mobile]");if(!button || !state.current)return;
  if(button.dataset.mobile==="save"){if(await saveBoard())toast("分镜已保存。");return;}
  const target=button.dataset.mobile==="edit" ? "#storyboard-panel" : button.dataset.mobile==="preview" ? ".preview-panel" : ".export-panel";
  $(target).scrollIntoView({behavior:"smooth",block:"start"});
});

$("#backup-project").addEventListener("click",async()=>{
  if(!state.current || state.backingUp)return;
  state.backingUp=true;$("#backup-project").disabled=true;
  try{
    if(!(await saveBoard()))return;
    const id=state.current.id;
    toast("正在打包分镜和照片…");
    const response=await fetch(`/api/projects/${id}/package.zip`);
    if(!response.ok)throw await window.FrameHTTP.responseError(response,"作品备份失败。");
    const url=URL.createObjectURL(await response.blob()),link=document.createElement("a");
    link.href=url;link.download="frame-project.zip";document.body.append(link);link.click();link.remove();
    setTimeout(()=>URL.revokeObjectURL(url),60000);toast("作品包已准备好，包含分镜和照片，可通过作品库导入。");
  }catch(error){toast(window.FrameHTTP.friendlyError(error).message,true);}
  finally{state.backingUp=false;$("#backup-project").disabled=false;}
});
$("#import-project").addEventListener("change",async event=>{
  const input=event.target,file=input.files[0];if(!file || !canLeave())return;
  if(file.size>350*1024*1024){toast("作品包不能超过 350 MB。",true);input.value="";return;}
  state.importing=true;input.disabled=true;
  try{
    toast("正在验证并导入作品包…");
    const project=await api("/api/projects/import",{method:"POST",body:file,headers:{"Content-Type":"application/zip"}});
    state.importing=false;await refreshProjects();await openProject(project.id);
    toast("已导入为独立作品，原来的作品保持不变。");
  }catch(error){toast(error.message,true);}
  finally{state.importing=false;input.disabled=false;input.value="";}
});

setBriefKind("merchant");
window.addEventListener("hashchange",()=>restoreRoute());
init();

"use strict";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const icon = (name) => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
const esc = (value) => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const state = {projects: [], current: null, style: "cinema", aspect: "9:16", scene: 0,
  dirty: false, playing: false, job: null, poll: null, playTimer: null, saving: false, serial: 0, config: null, briefKind: "merchant", merchantExample: false, uploading: 0};
let toastTimer;

function toast(message, error = false) {
  clearTimeout(toastTimer);
  $("#toast").textContent = message;
  $("#toast").classList.toggle("error", error);
  $("#toast").hidden = false;
  toastTimer = setTimeout(() => { $("#toast").hidden = true; }, error ? 6000 : 3200);
}

async function api(url, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 80000);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal,
      headers: options.body ? {"Content-Type": "application/json", ...options.headers} : {} });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "操作失败，请稍后重试。");
    return body;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("请求超时，请稍后重试。");
    if (error instanceof TypeError) throw new Error("无法连接本地服务，请确认启动窗口仍在运行。");
    throw error;
  } finally { clearTimeout(timeout); }
}

function showError(selector, message = "") {
  $(selector).hidden = !message;
  $(selector).textContent = message;
}

function seconds(value) { return `${String(Math.floor(value/60)).padStart(2,"0")}:${String(value%60).padStart(2,"0")}`; }
function total() { return state.current ? state.current.scenes.reduce((sum,s) => sum + Number(s.duration),0) : Number($("#duration").value); }
function previewUrl(project, index) { return `/api/projects/${project.id}/scenes/${index}.png?v=${project.version}`; }

function setPage(page) {
  $("#studio-view").hidden = page !== "studio";
  $("#library-view").hidden = page !== "library";
  $("#nav-studio").classList.toggle("active", page === "studio");
  $("#nav-library").classList.toggle("active", page === "library");
  $("#breadcrumb").textContent = page === "studio" ? "创作工作台" : "我的作品";
  if (page === "library") { stopPreview(); renderLibrary(); }
}

function setStep(step) {
  $("#step-idea").classList.toggle("active", step === 1);
  $("#step-board").classList.toggle("active", step === 2);
  $("#step-export").classList.toggle("active", step === 3);
  $("#step-board").disabled = !state.current;
  $("#step-export").disabled = !state.current;
}

function canLeave() { if (state.uploading) { toast("照片正在上传，请稍候。", true); return false; } return !state.dirty || window.confirm("分镜有未保存的修改，确定离开并放弃这些修改吗？"); }

function newProject() {
  if (!canLeave()) return;
  state.serial++;
  clearTimeout(state.poll);
  stopPreview();
  state.current = null; state.job = null; state.dirty = false;
  $("#brief-form").reset(); state.merchantExample = false; $("#merchant-example-note").hidden = true;
  $("#narration").checked = Boolean(state.config?.narration_available);
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
}

function updateStage(aspect) {
  $("#preview-stage").dataset.aspect = aspect;
  $("#preview-stage").style.aspectRatio = aspect.replace(":", "/");
  $("#preview-stage").style.maxWidth = aspect === "9:16" ? "282px" : "100%";
}

function renderRecent() {
  $("#project-count").textContent = state.projects.length;
  $("#recent-projects").innerHTML = state.projects.slice(0,6).map(project =>
    `<button class="recent-item ${state.current?.id===project.id ? "selected" : ""}" data-project="${project.id}" data-style="${project.style}" title="${esc(project.title)}"><i></i><span>${esc(project.title)}</span></button>`).join("");
}

function renderLibrary() {
  const query = $("#project-search").value.trim().toLowerCase();
  const projects = state.projects.filter(p => `${p.title} ${p.prompt}`.toLowerCase().includes(query));
  $("#library-count").textContent = state.projects.length;
  $("#library-grid").innerHTML = projects.length ? projects.map(p =>
    `<button class="project-card" data-project="${p.id}"><div class="project-cover"><img src="${previewUrl(p,0)}" alt="${esc(p.title)}封面" loading="lazy"><span>${p.example ? "示例作品" : p.source === "deepseek" ? "AI 分镜" : "本地模板"}</span></div><h3>${esc(p.title)}</h3><p>${p.aspect} · ${p.duration} 秒 · ${p.scenes.length} 个分镜</p><div><span>${new Date(p.updated_at).toLocaleDateString("zh-CN")}</span><span>继续创作 ↗</span></div></button>`).join("") : `<div class="empty-library">${query ? "没有找到匹配的作品，试试其他关键词。" : "你的第一个故事，从一个想法开始。"}</div>`;
}

async function refreshProjects() {
  state.projects = await api("/api/projects"); renderRecent();
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
    displayBoard(); setPage("studio"); renderRecent();
    window.scrollTo({top:0, behavior:"smooth"});
    const jobs = await api(`/api/projects/${id}/jobs`);
    if (serial !== state.serial) return;
    const matching = jobs.find(j => j.version === project.version);
    if (matching) { $("#music").checked = matching.music; $("#narration").checked = Boolean(matching.narration); handleJob(matching); }
  } catch (error) { toast(error.message, true); }
}

function displayBoard() {
  const p = state.current;
  $("#brief-panel").hidden = true; $("#storyboard-panel").hidden = false;
  $("#project-title").value = p.title; $("#board-style").value = p.style; $("#board-aspect").value = p.aspect;
  $("#board-source").textContent = p.source === "merchant_template" ? (p.example ? "◈ 虚构门店示例" : "◈ 门店信息模板") : p.source === "deepseek" ? "✳ DeepSeek AI 分镜" : "◈ 本地模板 · 可自由编辑";
  $("#save-status").textContent = "已保存至本地";
  showError("#save-error"); showError("#export-error");
  renderScenes(); updateBoardTotal(); showScene(0); setStep(2); resetExport();
}

function renderScenes() {
  const p = state.current;
  $("#scenes").innerHTML = p.scenes.map((scene,i) =>
    `<article class="scene-card ${i===state.scene ? "active":""}" data-index="${i}" data-asset-id="${esc(scene.asset_id || "")}"><div class="scene-card-head"><span class="scene-number">${String(i+1).padStart(2,"0")}</span><span>${i===0 ? "开场 · 留住注意" : i===p.scenes.length-1 ? "收束 · 留下余韵" : "展开 · 讲述故事"}</span><label>时长 <input type="number" min="2" max="20" step="1" value="${scene.duration}" data-field="duration" aria-label="分镜 ${i+1} 时长">秒</label></div><div class="scene-content"><button class="scene-thumb" data-preview="${i}" aria-label="预览分镜 ${i+1}"><img src="${previewUrl(p,i)}" alt="分镜 ${i+1}" loading="lazy"></button><div><label for="heading-${i}">画面标题</label><input id="heading-${i}" data-field="heading" maxlength="32" value="${esc(scene.heading)}" required><label for="caption-${i}">画面字幕</label><textarea id="caption-${i}" data-field="caption" maxlength="96" required>${esc(scene.caption)}</textarea><div class="scene-counter">${scene.caption.length} / 96</div></div></div><div class="scene-photo"><label class="photo-upload">${icon("plus")} ${scene.asset_id ? "更换照片" : "上传门店照片"}<input type="file" accept="image/jpeg,image/png,image/webp" data-upload="${i}" aria-label="分镜 ${i+1} 照片"></label><span class="photo-status">${scene.asset_id ? "已使用照片" : "尚未上传 · 使用图形背景"}</span><button type="button" class="remove-photo" ${scene.asset_id ? "" : "hidden"}>移除照片</button></div></article>`).join("");
}

function updateBoardTotal() {
  $("#board-total").textContent = `${state.current.scenes.length} 个分镜 · 共 ${total()} 秒`;
  if (total() > 60) showError("#save-error", "总时长超过 60 秒，请缩短部分分镜。");
  else showError("#save-error");
}

function markDirty() {
  state.dirty = true; stopPreview();
  if (!$("#final-video").hidden) showScene(state.scene);
  $("#save-status").textContent = "有未保存的修改";
  $("#preview-hint").textContent = "当前显示已保存版本，保存分镜后更新";
  $("#download-actions").hidden = true; $("#export-video").hidden = false;
  $("#export-video").disabled = false;
  $("#export-video span").textContent = "保存并导出视频";
  $("#export-note").textContent = "导出将使用你最新保存的分镜";
}

function readEdit() {
  const scenes = $$(".scene-card").map(card => ({
    heading:card.querySelector('[data-field="heading"]').value.trim(),
    caption:card.querySelector('[data-field="caption"]').value.trim(),
    duration:Number(card.querySelector('[data-field="duration"]').value),
    asset_id: card.dataset.assetId || null,
  }));
  const title = $("#project-title").value.trim();
  if (!title) throw new Error("请填写作品名称。");
  if (scenes.some(s => !s.heading || !s.caption)) throw new Error("每个分镜都需要标题和字幕。");
  if (scenes.some(s => !Number.isInteger(s.duration) || s.duration < 2 || s.duration > 20)) throw new Error("每个分镜的时长需要是 2–20 秒的整数。");
  if (scenes.reduce((n,s)=>n+s.duration,0) > 60) throw new Error("总时长不能超过 60 秒。");
  return {title, style:$("#board-style").value, aspect:$("#board-aspect").value, scenes, version:state.current.version};
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
    state.current = project; state.dirty = false; state.job = null; clearTimeout(state.poll);
    $("#save-status").textContent = "已保存至本地";
    renderScenes(); updateBoardTotal(); showScene(Math.min(state.scene,project.scenes.length-1)); resetExport();
    showError("#save-error"); await refreshProjects();
    return true;
  } catch(error) { showError("#save-error",error.message); return false; }
  finally {
    state.saving = false;
    $$("#storyboard-panel input, #storyboard-panel textarea, #storyboard-panel select, #save-board").forEach(el => el.disabled = false);
  }
}

function updateTime() {
  const elapsed = state.current ? state.current.scenes.slice(0,state.scene).reduce((n,s)=>n+s.duration,0) : 0;
  $("#preview-time").innerHTML = `${seconds(elapsed)} <small>/ ${seconds(total())}</small>`;
}

function showScene(index) {
  const p = state.current; if (!p) return;
  state.scene = index;
  $(".preview-transport").hidden = false; $("#timeline").hidden = false;
  $("#final-video").pause(); $("#final-video").hidden = true;
  $("#sample-poster").hidden = true; $("#scene-preview").hidden = false;
  $("#scene-preview").src = previewUrl(p,index);
  $("#scene-preview").alt = `分镜 ${index+1}：${p.scenes[index].heading}`;
  $("#preview-badge").textContent = `分镜 ${index+1} / ${p.scenes.length}`;
  $("#preview-spec").textContent = p.aspect;
  $("#preview-hint").textContent = state.dirty ? "当前显示已保存版本，保存分镜后更新" : "分镜静帧预览 · 导出时加入镜头运动和淡入淡出";
  $("#play-preview").disabled = false; $("#next-preview").disabled = false;
  $("#timeline").innerHTML = p.scenes.map((s,i)=>`<button data-preview="${i}" class="${i===index ? "active":""}" style="flex:${s.duration}" aria-label="跳转到分镜 ${i+1}" title="${esc(s.heading)} · ${s.duration}秒"></button>`).join("");
  $$(".scene-card").forEach((card,i)=>card.classList.toggle("active",i===index));
  updateStage(p.aspect); updateTime();
}

function stopPreview() {
  clearTimeout(state.playTimer); state.playing = false;
  $("#preview-stage").classList.remove("playing");
  $("#play-preview").innerHTML = icon("play");
  $("#play-preview").setAttribute("aria-label", "播放分镜预览");
}

function nextDuringPlayback() {
  if (!state.playing || !state.current) return;
  if (state.scene === state.current.scenes.length-1) { stopPreview(); return; }
  showScene(state.scene+1);
  state.playTimer = setTimeout(nextDuringPlayback,state.current.scenes[state.scene].duration*1000);
}

function togglePreview() {
  if (!state.current) return;
  if (state.playing) { stopPreview(); return; }
  if (state.scene === state.current.scenes.length-1 || !$("#final-video").hidden) showScene(0);
  state.playing = true;
  $("#preview-stage").classList.add("playing");
  $("#play-preview").textContent = "Ⅱ";
  $("#play-preview").setAttribute("aria-label", "暂停分镜预览");
  state.playTimer = setTimeout(nextDuringPlayback,state.current.scenes[state.scene].duration*1000);
}

function resetExport() {
  $("#download-actions").hidden = true; $("#job-progress").hidden = true;
  $("#export-video").hidden = false; $("#export-video").disabled = !state.current;
  $("#export-video span").textContent = "导出视频";
  $("#export-note").textContent = state.current ? "在本机合成，通常需要几十秒" : "生成分镜，距离成片再近一步";
}

function handleJob(job) {
  if (state.current?.id !== job.project_id) return;
  state.job = job;
  const current = job.version === state.current.version && !state.dirty && job.music === $("#music").checked && Boolean(job.narration) === $("#narration").checked;
  if (!current) { resetExport(); return; }
  if (["queued","rendering"].includes(job.status)) {
    $("#job-progress").hidden = false; $("#download-actions").hidden = true;
    $("#job-message").textContent = job.message;
    $("#job-percent").textContent = `${job.progress}%`; $("#progress").value = job.progress;
    $("#export-video").hidden = false; $("#export-video").disabled = true;
    $("#export-video span").textContent = "正在合成视频…";
    $("#export-note").textContent = "可继续浏览作品，重新打开会恢复任务进度";
    clearTimeout(state.poll); state.poll = setTimeout(()=>pollJob(job.id),1200);
  } else if (job.status === "completed") {
    clearTimeout(state.poll); stopPreview(); setStep(3);
    $("#job-progress").hidden = true; $("#export-video").hidden = true; $("#download-actions").hidden = false;
    $("#download-mp4").href = `/api/jobs/${job.id}/video.mp4?download=true`;
    $("#download-srt").href = `/api/jobs/${job.id}/subtitles.srt`;
    $("#download-json").href = job.materials ? `/api/jobs/${job.id}/materials/storyboard.json` : `/api/projects/${job.project_id}/storyboard.json`;
    for (const name of ["cover", "post"]) {
      $(`#download-${name}`).hidden = !job.materials;
      $(`#download-${name}`).href = `/api/jobs/${job.id}/materials/${name === "cover" ? "cover.png" : "post.txt"}`;
    }
    $("#export-note").textContent = `已完成 · ${Number(job.duration.toFixed(1))} 秒 · ${(job.bytes/1024/1024).toFixed(1)} MB${job.narration ? " · 中文配音" : ""}${job.music ? " · 氛围音轨" : job.narration ? "" : " · 无声"}`;
    $("#scene-preview").hidden = true; $("#sample-poster").hidden = true; $("#final-video").hidden = false;
    $(".preview-transport").hidden = true; $("#timeline").hidden = true;
    const videoUrl = `/api/jobs/${job.id}/video.mp4`;
    $("#final-video").poster = job.materials ? `/api/jobs/${job.id}/materials/cover.png` : previewUrl(state.current,0);
    if ($("#final-video").getAttribute("src") !== videoUrl) { $("#final-video").src = videoUrl; $("#final-video").load(); }
    $("#preview-badge").textContent = "成片就绪";
    $("#preview-hint").textContent = "使用播放器查看实际成片，支持全屏播放";
    showError("#export-error");
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
    if (job.status === "completed") toast("成片已就绪，可以播放和下载了。");
  } catch (error) {
    if (state.job?.id !== id) return;
    showError("#export-error",`${error.message} 正在重试连接。`);
    state.poll = setTimeout(()=>pollJob(id),5000);
  }
}

$("#brief-form").addEventListener("submit",async event=> {
  event.preventDefault();
  const prompt = $("#prompt").value.trim();
  if (state.briefKind === "creative" && prompt.length<5) { showError("#form-error","请至少输入 5 个字的创意描述。"); return; }
  const serial = ++state.serial;
  $("#generate").disabled = true; $("#generate").classList.add("loading");
  $("#generate span").textContent = $("#generation-mode").value === "ai" ? "AI 正在编写故事…" : "正在编排分镜…";
  showError("#form-error");
  try {
    const settings = {style:state.style, aspect:state.aspect, duration:Number($("#duration").value)};
    const merchant = Object.fromEntries(["store_name", "product", "selling_point", "offer", "address", "cta"].map(key => [key, $(`#merchant-${key.replaceAll("_", "-")}`).value.trim()]));
    const body = state.briefKind === "merchant" ? {...settings, ...merchant, example:state.merchantExample} : {...settings, prompt, mode:$("#generation-mode").value};
    const project = await api(state.briefKind === "merchant" ? "/api/merchant-projects" : "/api/projects", {method:"POST",body:JSON.stringify(body)});
    await refreshProjects();
    if (serial !== state.serial) return;
    state.current = project; state.dirty = false; state.scene = 0; state.job = null;
    displayBoard(); renderRecent(); toast("分镜已生成并保存，可以开始打磨故事了。");
  } catch (error) { if (serial === state.serial) showError("#form-error",error.message); }
  finally { if (serial === state.serial) { $("#generate").disabled = false; $("#generate").classList.remove("loading"); $("#generate span").textContent = "生成我的分镜"; } }
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
  if(field==="duration")state.current.scenes[Number(card.dataset.index)].duration=Number(event.target.value);
  if(field==="caption")card.querySelector(".scene-counter").textContent=`${event.target.value.length} / 96`;
  markDirty(); updateBoardTotal();
});
[$("#project-title"),$("#board-style"),$("#board-aspect")].forEach(el=>el.addEventListener("input",markDirty));
document.addEventListener("click",event=> {
  const project=event.target.closest("[data-project]"); if(project)openProject(project.dataset.project);
  const preview=event.target.closest("[data-preview]"); if(preview){stopPreview();showScene(Number(preview.dataset.preview));}
});
$("#save-board").addEventListener("click",async()=> { if(await saveBoard())toast("分镜已保存，预览已更新。"); });
$("#export-video").addEventListener("click",async()=> {
  if(!state.current)return;
  $("#export-video").disabled=true; showError("#export-error");
  try {
    if(!(await saveBoard())) { $("#export-video").disabled=false; return; }
    const id=state.current.id;
    $("#export-video").disabled=true;
    const job=await api(`/api/projects/${id}/render`,{method:"POST",body:JSON.stringify({version:state.current.version,music:$("#music").checked,narration:$("#narration").checked})});
    if(state.current?.id===id)handleJob(job);
  } catch(error){showError("#export-error",error.message);$("#export-video").disabled=false;}
});
for (const control of [$("#music"), $("#narration")]) control.addEventListener("change",async()=> {
  clearTimeout(state.poll); state.job=null; resetExport();
  if(!state.current)return;
  showScene(state.scene);
  const id=state.current.id;
  try{
    const jobs=await api(`/api/projects/${id}/jobs`);
    if(state.current?.id!==id)return;
    const matching=jobs.find(j=>j.version===state.current.version&&j.music===$("#music").checked&&Boolean(j.narration)===$("#narration").checked);
    if(matching)handleJob(matching);
  }catch(error){toast(error.message,true);}
});
$("#return-board-preview").addEventListener("click",()=>{showScene(0);setStep(2);});
$("#play-preview").addEventListener("click",togglePreview);
$("#next-preview").addEventListener("click",()=>{if(state.current){stopPreview();showScene((state.scene+1)%state.current.scenes.length);}});
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
window.addEventListener("beforeunload",event=>{if(state.dirty){event.preventDefault();event.returnValue="";}});
document.addEventListener("visibilitychange",()=>{if(document.hidden)stopPreview();});
$("#scene-preview").addEventListener("error",()=>{$("#preview-hint").textContent="预览暂时无法加载，请重新打开作品或检查服务。";});
$("#final-video").addEventListener("error",()=>{
  if(!$("#final-video").getAttribute("src")||!state.current)return;
  resetExport(); showError("#export-error","成片文件无法加载，请重新导出。也可检查浏览器是否支持 H.264 视频。");
});

async function init(){
  try{
    const [config,,health]=await Promise.all([api("/api/config"),refreshProjects(),api("/api/health")]);
    state.config=config;
    $("#narration").disabled = !config.narration_available;
    $("#narration").checked = config.narration_available;
    $("#narration-note").textContent = config.narration_note + "。开启后自动延长过短镜头，最长 120 秒。";
    $("#examples").innerHTML=config.examples.map((ex,i)=>`<button type="button" class="example-chip" data-example="${i}">${esc(ex.label)} ↗</button>`).join("");
    const ai=$("#generation-mode option[value=ai]");ai.disabled=!config.ai_available;ai.textContent=config.ai_available?"DeepSeek AI · 已连接":"DeepSeek AI · 尚未配置";
    if(health.status!=="ok")throw new Error("视频合成环境未就绪，请查看启动日志。");
  }catch(error){$("#connection").classList.add("offline");$("#connection").innerHTML='<span class="status-dot"></span>服务连接异常';showError("#form-error",error.message);}
}
function setBriefKind(kind) {
  state.briefKind = kind;
  $("#merchant-fields").hidden = kind !== "merchant";
  $("#creative-fields").hidden = kind !== "creative";
  $$("#merchant-fields input").forEach(el => el.disabled = kind !== "merchant");
  $("#prompt").disabled = kind !== "creative"; $("#prompt").required = kind === "creative";
  $(".generation-mode").hidden = kind !== "creative";
  $$("[data-brief]").forEach(el => { el.classList.toggle("selected", el.dataset.brief === kind); el.setAttribute("aria-pressed", el.dataset.brief === kind); });
  $("#generation-note").textContent = kind === "merchant" ? "门店模板 · 无需密钥 · 信息只保存在本机" : "本地模板可自由修改；选择 AI 时会将创意发送至 DeepSeek。";
}
$(".brief-tabs").addEventListener("click", event => { const button = event.target.closest("[data-brief]"); if (button) setBriefKind(button.dataset.brief); });
$("#merchant-example").addEventListener("click", () => {
  const example = {store_name:"拾光咖啡（演示）", product:"桂花拿铁", selling_point:"桂花香气，搭配柔和奶香。临窗坐坐，给午后留一点空闲。", offer:"", address:"示例城市 · 春日路 18 号（虚构地址）", cta:"欢迎到店，喝一杯喜欢的咖啡。"};
  for (const [key, value] of Object.entries(example)) $(`#merchant-${key.replaceAll("_", "-")}`).value = value;
  state.merchantExample = true; $("#merchant-example-note").hidden = false; setStyle("editorial");
});
$("#scenes").addEventListener("change", async event => {
  const input = event.target.closest("[data-upload]"); if (!input || !input.files[0]) return;
  const file = input.files[0], card = input.closest(".scene-card"), id = state.current.id;
  if (file.size > 8*1024*1024) { toast("照片不能超过 8 MB。", true); input.value = ""; return; }
  state.uploading++; input.disabled = true; card.querySelector(".remove-photo").disabled = true;
  card.querySelector(".photo-status").textContent = "正在上传…";
  try {
    const photo = await api(`/api/projects/${id}/assets`, {method:"POST", body:file, headers:{"Content-Type":file.type || "application/octet-stream"}});
    card.dataset.assetId = photo.asset_id;
    card.querySelector(".photo-status").textContent = "照片已上传 · 保存后更新预览";
    card.querySelector(".remove-photo").hidden = false;
    markDirty();
  } catch (error) {
    card.querySelector(".photo-status").textContent = card.dataset.assetId ? "保留原照片" : "尚未上传 · 使用图形背景";
    showError("#save-error", error.message);
  } finally { state.uploading--; input.disabled = false; input.value = ""; card.querySelector(".remove-photo").disabled = false; }
});
$("#scenes").addEventListener("click", event => {
  const button = event.target.closest(".remove-photo"); if (!button || state.saving || state.uploading) return;
  const card = button.closest(".scene-card"); card.dataset.assetId = ""; button.hidden = true;
  card.querySelector(".photo-status").textContent = "使用图形背景 · 保存后更新"; markDirty();
});
setBriefKind("merchant");
init();

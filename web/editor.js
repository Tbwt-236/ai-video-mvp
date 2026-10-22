/* Shared, dependency-free editing rules used by the studio and its tests. */
(function (root) {
  "use strict";
  const clone = value => JSON.parse(JSON.stringify(value));
  function scene(value = {}) {
    return {heading:"新的画面", caption:"在这里写下你想传递的话。", duration:5, asset_id:null,
      crop_x:.5, crop_y:.5, zoom:1, photo_fit:"cover", motion:"zoom_in", text_position:"bottom", ...clone(value)};
  }
  function editable(project) {
    return {title:project.title, style:project.style, aspect:project.aspect,
      scenes:project.scenes.map(scene), accent_color:project.accent_color || null,
      cover_scene:project.cover_scene || 0};
  }
  function validate(edit) {
    if (!edit.title.trim()) throw new Error("请填写作品名称。");
    if (edit.scenes.length < 1 || edit.scenes.length > 8) throw new Error("每个作品需要 1–8 个分镜。");
    for (const item of edit.scenes) {
      if (!item.heading.trim() || !item.caption.trim()) throw new Error("每个分镜都需要标题和字幕。");
      if (item.heading.length > 32 || item.caption.length > 96) throw new Error("标题不超过 32 字，字幕不超过 96 字。");
      if (!Number.isInteger(item.duration) || item.duration < 2 || item.duration > 20) throw new Error("每幕时长需要是 2–20 秒的整数。");
    }
    if (edit.scenes.reduce((sum,item) => sum + item.duration, 0) > 60) throw new Error("分镜总时长不能超过 60 秒。开启配音后可自动延长。");
    return edit;
  }
  function transform(edit, action, index = 0) {
    const next = clone(edit), count = next.scenes.length;
    if (!Number.isInteger(index) || index < 0 || index >= count) throw new Error("找不到这个分镜。");
    if (action === "add" || action === "duplicate") {
      if (count >= 8) throw new Error("最多保留 8 个分镜。");
      const remaining = 60 - next.scenes.reduce((sum,item) => sum + Number(item.duration),0);
      const item = action === "duplicate" ? clone(next.scenes[index]) : scene({duration:Math.min(5,remaining)});
      if (remaining < item.duration || item.duration < 2) throw new Error("剩余时长不足，请先缩短其他分镜。");
      next.scenes.splice(index+1,0,item);
      if (next.cover_scene > index) next.cover_scene++;
    } else if (action === "remove") {
      if (count <= 1) throw new Error("至少保留一个分镜。");
      next.scenes.splice(index,1);
      if (next.cover_scene > index) next.cover_scene--;
      else if (next.cover_scene === index) next.cover_scene = Math.min(index, count-2);
    } else if (action === "up" || action === "down") {
      const target = index + (action === "up" ? -1 : 1);
      if (target < 0 || target >= count) return next;
      [next.scenes[index],next.scenes[target]] = [next.scenes[target],next.scenes[index]];
      if (next.cover_scene === index) next.cover_scene = target;
      else if (next.cover_scene === target) next.cover_scene = index;
    } else if (action === "cover") next.cover_scene = index;
    else throw new Error("不支持的分镜操作。");
    return next;
  }
  const api = {clone, scene, editable, validate, transform};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.FrameEditor = api;
})(typeof window !== "undefined" ? window : this);

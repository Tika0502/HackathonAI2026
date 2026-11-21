// Small helpers used by every page.
async function api(path, body) {
  const opts = body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  };
  const res = await fetch(path, opts);
  if (res.status === 401) { location.href = "/static/login.html"; return; }
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Error");
  return data;
}

async function logout() {
  await api("/api/logout", {});
  location.href = "/static/login.html";
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function showMsg(text) {
  const el = document.getElementById("msg");
  if (!el) return alert(text);
  el.textContent = text; el.style.display = "block";
  setTimeout(() => (el.style.display = "none"), 4000);
}

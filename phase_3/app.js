/**
 * Phase 3 — INDmoney Fund Chat frontend.
 * Sends messages to Phase 2 backend and displays replies with source link and timestamp.
 */

(function () {
  const API_BASE = window.API_BASE || "";
  const CHAT_URL = API_BASE + "/chat";
  const LAST_UPDATE_URL = API_BASE + "/last-update";
  const FUNDS_URL = API_BASE + "/funds";

  const welcomeEl = document.getElementById("welcome");
  const lastUpdateEl = document.getElementById("last-update");
  const chatEl = document.getElementById("chat");
  const messagesEl = document.getElementById("messages");
  const inputEl = document.getElementById("input");
  const sendBtn = document.getElementById("send");
  const btnReset = document.getElementById("btn-reset");
  const fundListEl = document.getElementById("fund-list");

  let selectedFundId = null;
  let selectedFundName = null;

  function showChat() {
    welcomeEl.hidden = true;
    chatEl.hidden = false;
    if (btnReset) btnReset.hidden = false;
  }

  function resetChat() {
    welcomeEl.hidden = false;
    chatEl.hidden = true;
    messagesEl.innerHTML = "";
    if (btnReset) btnReset.hidden = true;
    inputEl.focus();
  }

  function appendMessage(role, content, meta) {
    showChat();
    const div = document.createElement("div");
    div.className = "msg " + role;
    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";
    bubble.textContent = content;
    div.appendChild(bubble);
    if (role === "assistant" && meta && (meta.source_url || meta.last_data_update)) {
      const metaEl = document.createElement("div");
      metaEl.className = "msg-meta";
      if (meta.source_url) {
        const a = document.createElement("a");
        a.href = meta.source_url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.textContent = "View source on INDmoney";
        metaEl.appendChild(a);
      }
      if (meta.last_data_update) {
        const ts = document.createElement("div");
        ts.className = "ts";
        ts.textContent = "Data as of " + meta.last_data_update;
        metaEl.appendChild(ts);
      }
      div.appendChild(metaEl);
    }
    messagesEl.appendChild(div);
    var scrollEl = document.querySelector(".main-scroll");
    if (scrollEl) scrollEl.scrollTop = scrollEl.scrollHeight;
  }

  function appendLoading() {
    showChat();
    const div = document.createElement("div");
    div.className = "msg assistant msg-loading";
    div.id = "msg-loading";
    div.innerHTML =
      '<div class="msg-bubble"><div class="msg-loading-dots"><span></span><span></span><span></span></div></div>';
    messagesEl.appendChild(div);
    var scrollEl = document.querySelector(".main-scroll");
    if (scrollEl) scrollEl.scrollTop = scrollEl.scrollHeight;
  }

  function removeLoading() {
    const el = document.getElementById("msg-loading");
    if (el) el.remove();
  }

  function setError(message) {
    removeLoading();
    appendMessage("assistant", message || "Something went wrong. Please try again.", null);
    const last = messagesEl.querySelector(".msg.assistant:last-child");
    if (last) last.classList.add("msg-error");
  }

  function setFundSelection(fundId, fundName) {
    selectedFundId = fundId || null;
    selectedFundName = fundName || null;
    if (fundListEl) {
      fundListEl.querySelectorAll(".fund-item").forEach(function (el) {
        el.classList.toggle("selected", el.getAttribute("data-fund-id") === fundId);
      });
    }
    if (inputEl) {
      inputEl.placeholder = selectedFundName
        ? "Ask about " + selectedFundName + "…"
        : "Ask a question about the selected fund…";
    }
  }

  async function sendMessage(text) {
    const message = (text || inputEl.value || "").trim();
    if (!message) return;

    inputEl.value = "";
    sendBtn.disabled = true;
    appendMessage("user", message);
    appendLoading();

    var body = { message: message };
    if (selectedFundId) body.fund_id = selectedFundId;

    try {
      const res = await fetch(CHAT_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      removeLoading();

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || "Request failed. Please try again.");
        return;
      }

      const data = await res.json();
      appendMessage("assistant", data.message || "", {
        source_url: data.source_url || "",
        last_data_update: data.last_data_update || "",
      });
    } catch (e) {
      setError("Cannot reach the server. Is the backend running?");
    } finally {
      sendBtn.disabled = false;
      inputEl.focus();
    }
  }

  sendBtn.addEventListener("click", function () {
    sendMessage();
  });

  inputEl.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  document.querySelectorAll(".card[data-prompt]").forEach(function (card) {
    card.addEventListener("click", function () {
      sendMessage(card.getAttribute("data-prompt"));
    });
  });

  if (btnReset) {
    btnReset.addEventListener("click", resetChat);
  }

  function loadLastUpdate() {
    if (!lastUpdateEl) return;
    fetch(LAST_UPDATE_URL)
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (data) {
        if (data && data.last_data_update) {
          lastUpdateEl.textContent = "Data last updated: " + data.last_data_update;
          lastUpdateEl.classList.add("last-update-visible");
        }
      })
      .catch(function () {});
  }
  loadLastUpdate();

  function loadFunds() {
    if (!fundListEl) return;
    fetch(FUNDS_URL)
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (funds) {
        if (!Array.isArray(funds) || funds.length === 0) return;
        fundListEl.innerHTML = "";
        funds.forEach(function (f) {
          var li = document.createElement("li");
          var btn = document.createElement("button");
          btn.type = "button";
          btn.className = "fund-item";
          btn.setAttribute("data-fund-id", f.fund_id);
          btn.textContent = f.fund_name || f.fund_id;
          btn.addEventListener("click", function () {
            setFundSelection(f.fund_id, f.fund_name);
          });
          li.appendChild(btn);
          fundListEl.appendChild(li);
        });
      })
      .catch(function () {});
  }
  loadFunds();

  inputEl.focus();
})();

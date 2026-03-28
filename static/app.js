const form = document.getElementById("query-form");
const input = document.getElementById("query");
const submitBtn = document.getElementById("submit-btn");
const result = document.getElementById("result");
const answer = document.getElementById("answer");
const intent = document.getElementById("intent");
const entity = document.getElementById("entity");
const confidence = document.getElementById("confidence");
const llmUsed = document.getElementById("llm-used");
const routing = document.getElementById("routing");
const sources = document.getElementById("sources");

async function runQuery(query) {
  if (!query.trim()) return;

  submitBtn.disabled = true;
  submitBtn.textContent = "Thinking...";

  try {
    const response = await fetch("/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });

    if (!response.ok) {
      throw new Error("Request failed");
    }

    const data = await response.json();
    renderResult(data);
  } catch (error) {
    renderResult({
      answer: "The agent could not complete this request right now.",
      intent: "error",
      entity: "N/A",
      confidence: "low",
      routing_reason: "Frontend request failed.",
      sources: [],
    });
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Ask";
  }
}

function renderResult(data) {
  answer.textContent = data.answer;
  intent.textContent = data.intent || "unknown";
  entity.textContent = data.entity || "N/A";
  confidence.textContent = data.confidence || "unknown";
  if (data.llm_used) {
    llmUsed.textContent = "Gemini";
    llmUsed.classList.remove("hidden");
  } else {
    llmUsed.textContent = "";
    llmUsed.classList.add("hidden");
  }
  routing.textContent = data.routing_reason || "";
  sources.innerHTML = "";

  for (const url of data.sources || []) {
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = url;
    link.textContent = url;
    link.target = "_blank";
    link.rel = "noreferrer";
    item.appendChild(link);
    sources.appendChild(item);
  }

  result.classList.remove("hidden");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  await runQuery(input.value);
});

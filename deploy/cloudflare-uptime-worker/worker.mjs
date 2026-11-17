const SITE_HEALTH = "https://seqandchem.com/health";
const API_HEALTH = "https://api.seqandchem.com/health";
const API_CONVERT = "https://api.seqandchem.com/api/v1/convert";
const ALERT_INTERVAL_MS = 6 * 60 * 60 * 1000;
const STATUS_KEY = "status";

async function fetchJson(url, options = {}, timeoutMs = 15000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      ...options,
      signal: controller.signal,
      cf: { cacheTtl: 0 },
    });
    const text = await res.text();
    let data = null;
    try {
      data = JSON.parse(text);
    } catch (_) {
      // Keep data null; callers report an invalid payload.
    }
    return { res, data, text };
  } finally {
    clearTimeout(timer);
  }
}

function timeoutMessage(error) {
  return error && error.name === "AbortError" ? "timeout" : String(error && error.message ? error.message : error);
}

async function runChecks() {
  const errors = [];
  const checks = [];

  try {
    const { res, data } = await fetchJson(SITE_HEALTH);
    checks.push(`main /health ${res.status}`);
    if (!res.ok) errors.push(`main /health HTTP ${res.status}`);
    else if (!data || data.ok !== true || !(Number(data.formats) > 0)) {
      errors.push("main /health payload invalid");
    }
  } catch (error) {
    errors.push(`main /health: ${timeoutMessage(error)}`);
  }

  try {
    const { res, data } = await fetchJson(API_HEALTH);
    checks.push(`api /health ${res.status}`);
    if (!res.ok) errors.push(`api /health HTTP ${res.status}`);
    else if (!data || data.ok !== true || !(Number(data.formats) > 0)) {
      errors.push("api /health payload invalid");
    }
  } catch (error) {
    errors.push(`api /health: ${timeoutMessage(error)}`);
  }

  try {
    const { res, data } = await fetchJson(
      API_CONVERT,
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ from: "smi", to: "inchi", data: "CCO" }),
      },
      30000,
    );
    checks.push(`api convert ${res.status}`);
    if (!res.ok) errors.push(`api convert HTTP ${res.status}`);
    else if (!data || data.ok !== true) errors.push("api convert payload invalid");
  } catch (error) {
    errors.push(`api convert: ${timeoutMessage(error)}`);
  }

  return { errors, checks };
}

async function sendFeishu(env, text) {
  const tokenResult = await fetchJson(
    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ app_id: env.FEISHU_APP_ID, app_secret: env.FEISHU_APP_SECRET }),
    },
    10000,
  );
  const tokenJson = tokenResult.data;
  if (!tokenJson || !tokenJson.tenant_access_token) {
    throw new Error("feishu tenant_access_token failed");
  }

  const result = await fetchJson(
    "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
    {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${tokenJson.tenant_access_token}`,
      },
      body: JSON.stringify({
        receive_id: env.FEISHU_OPEN_ID,
        msg_type: "text",
        content: JSON.stringify({ text }),
      }),
    },
    10000,
  );
  const json = result.data;
  if (!json || json.code !== 0) {
    throw new Error(`feishu send failed code=${json ? json.code : "invalid response"}`);
  }
}

function nowIso() {
  return new Date().toISOString();
}

async function readStatus(env) {
  const raw = await env.UPTIME_KV.get(STATUS_KEY);
  if (!raw) return { state: null, last_alert: 0, last_check: null, last_result: null };
  try {
    return { state: null, last_alert: 0, last_check: null, last_result: null, ...JSON.parse(raw) };
  } catch (_) {
    return { state: null, last_alert: 0, last_check: null, last_result: null };
  }
}

export default {
  async scheduled(_event, env, _ctx) {
    const { errors, checks } = await runChecks();
    const down = errors.length > 0;
    const status = await readStatus(env);
    const previous = status.state;
    let notified = false;
    let notifyError = null;
    let stateAfter = down ? "down" : "up";

    try {
      if (down) {
        const lastAlert = Number(status.last_alert || 0);
        if (previous !== "down" || Date.now() - lastAlert > ALERT_INTERVAL_MS) {
          await sendFeishu(
            env,
            [
              "SeqChem external uptime check FAILED",
              `time: ${nowIso()}`,
              ...errors.map((e) => `- ${e}`),
              `checks: ${checks.join(", ")}`,
              "site: https://seqandchem.com",
            ].join("\n"),
          );
          status.last_alert = Date.now();
          notified = true;
        }
      } else if (previous === "down") {
        await sendFeishu(
          env,
          [
            "SeqChem external uptime RECOVERED",
            `time: ${nowIso()}`,
            `checks: ${checks.join(", ")}`,
            "site: https://seqandchem.com",
          ].join("\n"),
        );
        notified = true;
      }
    } catch (error) {
      notifyError = timeoutMessage(error);
      if (!down) stateAfter = "down";
    }

    status.state = stateAfter;
    status.last_check = nowIso();
    status.last_result = { ok: !down, errors, checks, notified, notifyError };
    await env.UPTIME_KV.put(STATUS_KEY, JSON.stringify(status));
  },
};

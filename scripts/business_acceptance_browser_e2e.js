#!/usr/bin/env node
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

function parseArgs(argv) {
  const args = {
    ledger: "tmp/trial_sample_eval/sample_question_ledger.json",
    output: "tmp/business_acceptance_full/browser_results.json",
    frontendUrl: "http://127.0.0.1:5173/smart-chat",
    maxCases: null,
    resume: false,
    headless: true,
    batchSize: 25,
    answerTimeoutMs: 45000,
    pageTimeoutMs: 30000,
    progressEveryCase: false,
  };
  for (let index = 2; index < argv.length; index += 1) {
    const key = argv[index];
    const next = argv[index + 1];
    if (key === "--ledger") {
      args.ledger = next;
      index += 1;
    } else if (key === "--output") {
      args.output = next;
      index += 1;
    } else if (key === "--frontend-url") {
      args.frontendUrl = next;
      index += 1;
    } else if (key === "--max-cases") {
      args.maxCases = Number(next);
      index += 1;
    } else if (key === "--batch-size") {
      args.batchSize = Number(next);
      index += 1;
    } else if (key === "--answer-timeout-ms") {
      args.answerTimeoutMs = Number(next);
      index += 1;
    } else if (key === "--page-timeout-ms") {
      args.pageTimeoutMs = Number(next);
      index += 1;
    } else if (key === "--resume") {
      args.resume = true;
    } else if (key === "--headed") {
      args.headless = false;
    } else if (key === "--progress-every-case") {
      args.progressEveryCase = true;
    }
  }
  return args;
}

function readJson(filePath, fallback = null) {
  if (!fs.existsSync(filePath)) {
    return fallback;
  }
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function writeJson(filePath, payload) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(payload, null, 2), "utf8");
}

function nowIso() {
  return new Date().toISOString();
}

function isFatalBrowserError(errorText) {
  return [
    "Target page, context or browser has been closed",
    "Browser has been closed",
    "browserType.launch",
  ].some((fragment) => errorText.includes(fragment));
}

function buildCases(ledger) {
  return (ledger.items || []).map((item) => ({
    case_id: `${item.id}:original`,
    question_id: item.id,
    variant_index: 0,
    question: item.question,
    domain: item.domain,
    question_type: item.question_type,
    is_variant: false,
  }));
}

async function fillQuestion(page, question) {
  const selectors = [
    '[data-testid="question-input"] textarea',
    'textarea[data-testid="question-input"]',
    '[data-testid="question-input"] input',
    'input[data-testid="question-input"]',
    'textarea[placeholder="输入业务问题"]',
  ];
  for (const selector of selectors) {
    const locator = page.locator(selector).first();
    if ((await locator.count()) > 0) {
      await locator.fill(question, { timeout: 5000 });
      return;
    }
  }
  throw new Error("未找到可输入的问题文本框");
}

async function innerTextOrEmpty(locator, timeout = 1000) {
  if ((await locator.count()) === 0) {
    return "";
  }
  try {
    return await locator.last().innerText({ timeout });
  } catch {
    return "";
  }
}

async function allTexts(locator) {
  if ((await locator.count()) === 0) {
    return [];
  }
  return locator.allInnerTexts();
}

async function extractTableRows(page) {
  const table = page.locator('[data-testid="result-table"]').last();
  if ((await table.count()) === 0) {
    return [];
  }
  const headers = (await table.locator(".el-table__header-wrapper th .cell").allInnerTexts()).map((value) => value.trim());
  const bodyRows = table.locator(".el-table__body-wrapper tbody tr");
  const rows = [];
  const rowCount = await bodyRows.count();
  for (let index = 0; index < rowCount; index += 1) {
    const cells = (await bodyRows.nth(index).locator("td .cell").allInnerTexts()).map((value) => value.trim());
    if (cells.length) {
      const row = {};
      cells.forEach((value, cellIndex) => {
        row[headers[cellIndex] || `列${cellIndex + 1}`] = value;
      });
      rows.push(row);
    }
  }
  return rows;
}

async function extractChartType(assistant) {
  const chart = assistant.locator('[data-testid="result-chart"]').last();
  if ((await chart.count()) === 0) {
    return "";
  }
  if ((await chart.locator("polyline").count()) > 0) {
    return "line";
  }
  if ((await chart.locator("rect.presentation-chart__bar").count()) > 0) {
    return "bar";
  }
  if ((await chart.locator("path").count()) > 0) {
    return "pie";
  }
  return "chart";
}

function resultPayload(args, ledger, results, status, extra = {}) {
  const selectedCaseIds = new Set(buildCases(ledger).map((item) => item.case_id));
  const selectedDone = results.filter((item) => selectedCaseIds.has(item.case_id)).length;
  const distribution = {};
  for (const item of results) {
    distribution[item.status] = (distribution[item.status] || 0) + 1;
  }
  return {
    generated_at: nowIso(),
    status,
    frontend_url: args.frontendUrl,
    total_cases: ledger.total_questions || (ledger.items || []).length,
    selected_case_count: selectedCaseIds.size,
    is_limited_run: Boolean(args.maxCases),
    max_cases: args.maxCases,
    executed: results.length,
    selected_pending: Math.max(selectedCaseIds.size - selectedDone, 0),
    result_status_distribution: distribution,
    results,
    ...extra,
  };
}

async function main() {
  const args = parseArgs(process.argv);
  const ledger = readJson(args.ledger);
  if (!ledger) {
    throw new Error(`缺少问题台账：${args.ledger}`);
  }
  const existing = args.resume ? readJson(args.output, { results: [] }) : { results: [] };
  const existingById = new Map((existing.results || []).map((item) => [item.case_id, item]));
  let cases = buildCases(ledger).filter((item) => !args.resume || !existingById.has(item.case_id));
  if (args.maxCases) {
    cases = cases.slice(0, args.maxCases);
  }
  const results = args.resume ? [...(existing.results || [])] : [];
  const consoleMessages = [];
  const networkFailures = [];

  const browser = await chromium.launch({ headless: args.headless });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      consoleMessages.push({ type: message.type(), text: message.text(), at: nowIso() });
    }
  });
  page.on("requestfailed", (request) => {
    networkFailures.push({ url: request.url(), method: request.method(), failure: request.failure()?.errorText || "", at: nowIso() });
  });

  try {
    await page.goto(args.frontendUrl, { waitUntil: "domcontentloaded", timeout: args.pageTimeoutMs });
    await page.locator('[data-testid="business-chat-page"]').waitFor({ timeout: args.pageTimeoutMs });
    for (let index = 0; index < cases.length; index += 1) {
      const item = cases[index];
      const startedAt = Date.now();
      const beforeConsoleCount = consoleMessages.length;
      const beforeNetworkCount = networkFailures.length;
      let result = {
        ...item,
        status: "pass",
        error: "",
        title: "",
        answer: "",
        dom_text: "",
        table_rows: [],
        follow_ups: [],
        suggestions: [],
        chart_type: "",
        has_chart: false,
        has_table: false,
        has_cards: false,
        console_errors: [],
        network_failures: [],
        elapsed_ms: 0,
        executed_at: nowIso(),
      };
      try {
        const newChatButton = page.locator('[data-testid="nav-new-chat"]').first();
        if ((await newChatButton.count()) > 0) {
          await newChatButton.click({ timeout: 5000 });
        }
        await fillQuestion(page, item.question);
        await page.locator('[data-testid="send-button"]').click({ timeout: 5000 });
        const assistant = page.locator('[data-testid="chat-message-assistant"]').last();
        await assistant.waitFor({ timeout: args.answerTimeoutMs });
        try {
          await assistant.locator('[data-testid="message-loading"]').waitFor({ state: "detached", timeout: args.answerTimeoutMs });
        } catch {
          // 页面可能没有单独渲染 loading 节点，继续读取最终内容。
        }
        try {
          await assistant.locator('[data-testid="assistant-result"]').waitFor({ timeout: 5000 });
        } catch {
          // 错误态没有 assistant-result 时仍需记录 DOM 文本。
        }
        result.dom_text = await assistant.innerText({ timeout: 5000 });
        result.title = await innerTextOrEmpty(assistant.locator('[data-testid="result-title"]'));
        result.answer = await innerTextOrEmpty(assistant.locator('[data-testid="result-answer"]'));
        result.table_rows = await extractTableRows(page);
        result.follow_ups = await allTexts(assistant.locator('[data-testid="result-follow-ups"] button'));
        result.suggestions = await allTexts(assistant.locator('[data-testid="result-suggestions"] span'));
        result.chart_type = await extractChartType(assistant);
        result.has_chart = Boolean(result.chart_type);
        result.has_table = result.table_rows.length > 0;
        result.has_cards = (await assistant.locator('[data-testid="result-cards"] .metric-card').count()) > 0;
        const errorNode = assistant.locator('[data-testid="message-error"]').last();
        if ((await errorNode.count()) > 0) {
          result.status = "error";
          result.error = await errorNode.innerText({ timeout: 1000 });
        }
      } catch (error) {
        const errorText = String(error && error.stack ? error.stack : error);
        if (isFatalBrowserError(errorText)) {
          writeJson(
            args.output,
            resultPayload(args, ledger, results, "interrupted", {
              fatal_case_id: result.case_id,
              fatal_error: errorText,
            })
          );
          throw error;
        }
        result.status = "failed";
        result.error = errorText;
      }
      result.elapsed_ms = Date.now() - startedAt;
      result.console_errors = consoleMessages.slice(beforeConsoleCount);
      result.network_failures = networkFailures.slice(beforeNetworkCount);
      results.push(result);
      writeJson(args.output, resultPayload(args, ledger, results, "running", { last_case_id: result.case_id, last_case_status: result.status }));
      if (args.progressEveryCase || result.status !== "pass" || ((index + 1) % args.batchSize === 0)) {
        console.log(`[browser-e2e] ${index + 1}/${cases.length} ${result.case_id} ${result.status} ${result.elapsed_ms}ms`);
      }
    }
  } finally {
    try {
      await browser.close();
    } catch {
      // 浏览器已经异常退出时，保留 interrupted 结果供断点续跑使用。
    }
  }
  writeJson(args.output, resultPayload(args, ledger, results, "completed", { console_message_count: consoleMessages.length, network_failure_count: networkFailures.length }));
  console.log(`browser_results written: ${args.output}`);
  console.log(`status=completed executed=${results.length} total=${ledger.total_questions || (ledger.items || []).length}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(2);
});

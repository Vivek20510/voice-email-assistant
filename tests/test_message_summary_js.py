import subprocess
import textwrap


def test_message_summary_loader_caches_cancels_and_handles_empty_fields():
    script = textwrap.dedent(r"""
        const fs = require("fs");
        const vm = require("vm");
        const assert = require("assert");

        const listeners = {};
        const warnings = [];
        const fetchCalls = [];
        const resolvers = [];
        let timerId = 0;
        const timers = new Map();

        const document = {
          addEventListener: (name, callback) => {
            listeners[name] = callback;
          },
          querySelectorAll: () => [],
        };

        const window = {
          setTimeout: (callback) => {
            timerId += 1;
            timers.set(timerId, callback);
            return timerId;
          },
          clearTimeout: (id) => {
            timers.delete(id);
          },
        };

        const context = {
          window,
          document,
          console: {
            warn: (...args) => warnings.push(args),
          },
          fetch: (url, options) => {
            fetchCalls.push({ url, options });
            return new Promise((resolve, reject) => {
              options.signal.addEventListener("abort", () => {
                const error = new Error("aborted");
                error.name = "AbortError";
                reject(error);
              });
              resolvers.push(resolve);
            });
          },
          AbortController,
          Error,
          JSON,
          Promise,
          String,
          setTimeout: window.setTimeout,
          clearTimeout: window.clearTimeout,
        };

        function makeSummaryElement(body) {
          return {
            dataset: {
              state: "loading",
              summaryUrl: "/nlp/summarize",
              subject: "Q3 report",
              sender: "Alice",
              body,
            },
            textContent: "",
          };
        }

        function responseWithSummary(summary) {
          return {
            ok: true,
            json: async () => ({ summary }),
          };
        }

        vm.createContext(context);
        vm.runInContext(
          fs.readFileSync("static/js/message_summary.js", "utf8"),
          context
        );

        (async () => {
          const summaryEl = makeSummaryElement("Please review this.");
          const firstLoad = context.window.EmailSummary.load(summaryEl);
          const duplicateLoad = context.window.EmailSummary.load(summaryEl);

          assert.equal(fetchCalls.length, 1);
          resolvers.shift()(responseWithSummary("Cached summary."));
          await Promise.all([firstLoad, duplicateLoad]);
          assert.equal(summaryEl.dataset.state, "ready");
          assert.equal(summaryEl.textContent, "Cached summary.");

          const cachedEl = makeSummaryElement("Please review this.");
          await context.window.EmailSummary.load(cachedEl);
          assert.equal(fetchCalls.length, 1);
          assert.equal(cachedEl.dataset.state, "ready");
          assert.equal(cachedEl.textContent, "Cached summary.");

          context.window.EmailSummary.clearCache();
          const changingEl = makeSummaryElement("First body");
          const cancelledLoad = context.window.EmailSummary.load(changingEl);
          changingEl.dataset.body = "Second body";
          const replacementLoad = context.window.EmailSummary.load(changingEl);

          assert.equal(fetchCalls.length, 3);
          assert.equal(fetchCalls[1].options.signal.aborted, true);
          resolvers.shift()(responseWithSummary("Ignored summary."));
          resolvers.shift()(responseWithSummary("Replacement summary."));
          await Promise.all([cancelledLoad, replacementLoad]);
          assert.equal(changingEl.dataset.state, "ready");
          assert.equal(changingEl.textContent, "Replacement summary.");

          const emptyEl = makeSummaryElement("   ");
          emptyEl.dataset.subject = "   ";
          await context.window.EmailSummary.load(emptyEl);
          assert.equal(fetchCalls.length, 3);
          assert.equal(emptyEl.dataset.state, "empty");
          assert.equal(
            emptyEl.textContent,
            "No message content is available to summarize."
          );

          const timeoutEl = makeSummaryElement("This request will hang.");
          const timeoutLoad = context.window.EmailSummary.load(timeoutEl);
          assert.equal(fetchCalls.length, 4);
          Array.from(timers.values()).at(-1)();
          await timeoutLoad;
          assert.equal(timeoutEl.dataset.state, "error");
          assert.equal(
            timeoutEl.textContent,
            "Summary is temporarily unavailable. Please review the message body below."
          );
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """)

    result = subprocess.run(
        ["node", "-e", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr

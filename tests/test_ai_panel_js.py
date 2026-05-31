import subprocess
import textwrap


def test_ai_panel_sends_context_and_renders_success_and_errors():
    script = textwrap.dedent(r"""
        const fs = require("fs");
        const vm = require("vm");
        const assert = require("assert");

        function makeElement(id) {
          return {
            id,
            dataset: {},
            value: "",
            textContent: "",
            innerHTML: "",
            className: "",
            children: [],
            focused: false,
            appendChild(child) {
              this.children.push(child);
              this.textContent += child.textContent || "";
            },
            focus() {
              this.focused = true;
            },
            querySelector() {
              return null;
            },
            querySelectorAll() {
              return [];
            },
          };
        }

        const elements = {
          "ai-input": makeElement("ai-input"),
          "ai-results": makeElement("ai-results"),
        };

        const fetchCalls = [];
        const navigateCalls = [];
        let fetchHandler = async () => ({
          ok: true,
          json: async () => ({ response: "Inbox summary ready." }),
        });

        const document = {
          getElementById: (id) => elements[id] || null,
          createElement: () => makeElement("created"),
        };

        const window = {
          currentEmails: [
            {
              id: "msg-1",
              sender: "Alice",
              subject: "Report",
              snippet: "Please review.",
              unread: true,
              has_attachments: true,
            },
          ],
          AICommandCenter: {
            getActiveView: () => "sb-inbox",
            getActiveMessageId: () => "",
            applyFilter: () => true,
            openMessage: () => true,
            navigate: (payload) => {
              navigateCalls.push(payload);
              return true;
            },
            prefillCompose: () => true,
            markReadLocal: () => true,
          },
        };

        const context = {
          window,
          document,
          console,
          fetch: async (url, options) => {
            fetchCalls.push({ url, options });
            return fetchHandler(url, options);
          },
          Boolean,
          AbortController,
          Error,
          JSON,
          Array,
          String,
          Promise,
        };

        vm.createContext(context);
        vm.runInContext(fs.readFileSync("static/js/ai_panel.js", "utf8"), context);

        (async () => {
          elements["ai-input"].value = "Summarize unread";
          await context.window.AIPanel.sendQuery();

          assert.equal(fetchCalls.length, 1);
          assert.equal(fetchCalls[0].url, "/api/ai-panel/query");
          const payload = JSON.parse(fetchCalls[0].options.body);
          assert.equal(payload.query, "Summarize unread");
          assert.equal(payload.emails.length, 1);
          assert.equal(payload.emails[0].sender, "Alice");
          assert.equal(payload.emails[0].has_attachments, true);
          assert.equal(payload.history.length, 0);
          assert.equal(payload.active_view, "sb-inbox");
          assert.equal(elements["ai-results"].children.at(-1).className, "ai-turn ai-turn-assistant");
          assert.ok(elements["ai-results"].children.at(-1).textContent.includes("Inbox summary ready."));

          window.currentEmails = [];
          fetchHandler = async () => ({
            ok: true,
            json: async () => ({
              response: "Open Settings > Channels to connect Gmail.",
              actions: [
                {
                  type: "open_settings",
                  label: "Open channels",
                  payload: { tab: "channels" },
                },
              ],
            }),
          });
          elements["ai-input"].value = "How do I connect Gmail?";
          await context.window.AIPanel.sendQuery();
          assert.equal(fetchCalls.length, 2);
          const helpPayload = JSON.parse(fetchCalls[1].options.body);
          assert.equal(helpPayload.query, "How do I connect Gmail?");
          assert.equal(helpPayload.emails.length, 0);
          assert.ok(elements["ai-results"].children.at(-1).textContent.includes("Open channels"));
          assert.equal(navigateCalls.length, 1);
          assert.equal(navigateCalls[0].target, "settings");
          assert.equal(navigateCalls[0].tab, "channels");

          window.currentEmails = [{ id: "msg-2", sender: "Bob", subject: "Plan" }];
          fetchHandler = async () => ({
            ok: false,
            status: 500,
            json: async () => ({ error: "Backend failed." }),
          });
          elements["ai-input"].value = "Try again";
          await context.window.AIPanel.sendQuery();
          assert.equal(elements["ai-results"].children.at(-1).className, "ai-turn ai-turn-assistant");
          assert.ok(elements["ai-results"].children.at(-1).textContent.includes("Backend failed."));

          fetchHandler = async () => {
            throw new Error("Network down.");
          };
          elements["ai-input"].value = "Try network";
          await context.window.AIPanel.sendQuery();
          assert.equal(elements["ai-results"].children.at(-1).className, "ai-turn ai-turn-assistant");
          assert.ok(elements["ai-results"].children.at(-1).textContent.includes("Network down."));
          assert.equal(context.window.AIPanel.history.length, 4);
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


def test_ai_panel_stop_aborts_generation_ignores_late_results_and_keeps_voice_stop():
    script = textwrap.dedent(r"""
        const fs = require("fs");
        const vm = require("vm");
        const assert = require("assert");

        function makeElement(id) {
          const attributes = {};
          const classes = new Set();
          const element = {
            id,
            dataset: {},
            style: {},
            value: "",
            textContent: "",
            innerHTML: "",
            className: "",
            children: [],
            disabled: false,
            focused: false,
            appendChild(child) {
              child.parentElement = this;
              child.remove = () => {
                this.children = this.children.filter((item) => item !== child);
              };
              child.closest = () => child;
              this.children.push(child);
              this.textContent += child.textContent || "";
            },
            focus() {
              this.focused = true;
            },
            setAttribute(name, value) {
              attributes[name] = String(value);
            },
            getAttribute(name) {
              return attributes[name];
            },
            querySelector(selector) {
              if (selector === ".ai-loading") {
                return this.children.find((child) =>
                  child.innerHTML.includes("ai-loading")
                ) || null;
              }
              return null;
            },
            querySelectorAll() {
              return [];
            },
            classList: {
              toggle(name, enabled) {
                if (enabled) classes.add(name);
                else classes.delete(name);
              },
              contains(name) {
                return classes.has(name);
              },
            },
          };
          return element;
        }

        const chips = [makeElement("chip-1"), makeElement("chip-2")];
        const elements = {
          "ai-input": makeElement("ai-input"),
          "ai-results": makeElement("ai-results"),
          "ai-send-btn": makeElement("ai-send-btn"),
          "ai-clear-btn": makeElement("ai-clear-btn"),
          "ai-ask-btn": makeElement("ai-ask-btn"),
        };

        const fetchCalls = [];
        const navigateCalls = [];
        let resolveFetch;
        let recognitionInstance;

        class SpeechRecognition {
          constructor() {
            recognitionInstance = this;
          }
          start() {
            this.onstart?.();
          }
          stop() {
            this.stopped = true;
            this.onend?.();
          }
        }

        const document = {
          getElementById: (id) => elements[id] || null,
          createElement: () => makeElement("created"),
          querySelectorAll: (selector) => selector === ".ai-chip" ? chips : [],
        };

        const window = {
          currentEmails: [],
          SpeechRecognition,
          AICommandCenter: {
            getActiveView: () => "sb-inbox",
            getActiveMessageId: () => "",
            navigate: (payload) => {
              navigateCalls.push(payload);
              return true;
            },
          },
        };

        const context = {
          window,
          document,
          console,
          navigator: {},
          fetch: async (url, options) => {
            fetchCalls.push({ url, options });
            return new Promise((resolve) => {
              resolveFetch = resolve;
            });
          },
          AbortController,
          Boolean,
          Error,
          JSON,
          Array,
          String,
          Promise,
          setTimeout,
          clearTimeout,
        };

        vm.createContext(context);
        vm.runInContext(fs.readFileSync("static/js/ai_panel.js", "utf8"), context);

        (async () => {
          elements["ai-input"].value = "How do I connect Gmail?";
          const pending = context.window.AIPanel.sendQuery();
          await Promise.resolve();

          assert.equal(fetchCalls.length, 1);
          assert.ok(fetchCalls[0].options.signal);
          assert.equal(elements["ai-send-btn"].textContent, "■");
          assert.equal(elements["ai-send-btn"].title, "Stop generating");
          assert.equal(elements["ai-send-btn"].getAttribute("aria-label"), "Stop generating");
          assert.equal(elements["ai-send-btn"].classList.contains("ai-stop-btn"), true);
          assert.equal(elements["ai-input"].disabled, true);
          assert.equal(elements["ai-clear-btn"].disabled, true);
          assert.equal(elements["ai-ask-btn"].disabled, true);
          assert.equal(chips.every((chip) => chip.disabled), true);
          assert.equal(elements["ai-results"].getAttribute("aria-busy"), "true");

          const enterEvent = {
            key: "Enter",
            preventDefault() {
              this.prevented = true;
            },
          };
          context.window.AIPanel.handleKey(enterEvent);
          assert.equal(enterEvent.prevented, true);
          assert.equal(fetchCalls.length, 1);

          context.window.AIPanel.handlePrimaryAction();
          assert.equal(fetchCalls[0].options.signal.aborted, true);
          assert.equal(elements["ai-send-btn"].textContent, "↑");
          assert.equal(elements["ai-send-btn"].title, "Send message");
          assert.equal(elements["ai-send-btn"].getAttribute("aria-label"), "Send message");
          assert.equal(elements["ai-send-btn"].classList.contains("ai-stop-btn"), false);
          assert.equal(elements["ai-input"].disabled, false);
          assert.equal(elements["ai-clear-btn"].disabled, false);
          assert.equal(elements["ai-ask-btn"].disabled, false);
          assert.equal(chips.every((chip) => !chip.disabled), true);
          assert.equal(elements["ai-results"].getAttribute("aria-busy"), "false");
          assert.equal(elements["ai-input"].focused, true);
          assert.ok(elements["ai-results"].children.at(-1).textContent.includes("Response stopped."));

          resolveFetch({
            ok: true,
            json: async () => ({
              response: "Late response should be ignored.",
              actions: [
                {
                  type: "open_settings",
                  payload: { tab: "channels" },
                },
              ],
            }),
          });
          await pending;
          assert.equal(context.window.AIPanel.history.length, 0);
          assert.equal(navigateCalls.length, 0);
          assert.equal(
            elements["ai-results"].children.some((child) =>
              child.textContent.includes("Late response should be ignored.")
            ),
            false,
          );

          elements["ai-input"].value = "Summarize unread";
          const waitingForEmails = context.window.AIPanel.sendQuery();
          await Promise.resolve();
          assert.equal(fetchCalls.length, 1);
          context.window.AIPanel.stopGeneration();
          await waitingForEmails;
          assert.equal(fetchCalls.length, 1);
          assert.ok(elements["ai-results"].children.at(-1).textContent.includes("Response stopped."));

          await context.window.AIPanel.askWithVoice();
          assert.ok(recognitionInstance);
          assert.equal(elements["ai-ask-btn"].textContent, "⏹ Stop");
          assert.equal(elements["ai-ask-btn"].getAttribute("aria-label"), "Stop recording");
          await context.window.AIPanel.askWithVoice();
          assert.equal(recognitionInstance.stopped, true);
          assert.equal(elements["ai-ask-btn"].textContent, "🎤 Ask");
          assert.equal(elements["ai-ask-btn"].getAttribute("aria-label"), "Ask with voice");
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

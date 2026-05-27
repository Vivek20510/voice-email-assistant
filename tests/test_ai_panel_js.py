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
            navigate: () => true,
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
          assert.equal(fetchCalls[0].url, "/nlp/ai-query");
          const payload = JSON.parse(fetchCalls[0].options.body);
          assert.equal(payload.query, "Summarize unread");
          assert.equal(payload.emails.length, 1);
          assert.equal(payload.emails[0].sender, "Alice");
          assert.equal(payload.emails[0].has_attachments, true);
          assert.equal(payload.history.length, 0);
          assert.equal(payload.active_view, "sb-inbox");
          assert.equal(elements["ai-results"].children.at(-1).className, "ai-turn ai-turn-assistant");
          assert.ok(elements["ai-results"].children.at(-1).textContent.includes("Inbox summary ready."));

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
          assert.equal(context.window.AIPanel.history.length, 2);
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

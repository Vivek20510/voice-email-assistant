import subprocess
import textwrap


def test_reply_suggestions_generate_render_prefill_and_restore_handoff():
    script = textwrap.dedent(r"""
        const fs = require("fs");
        const vm = require("vm");
        const assert = require("assert");

        const listeners = {};
        const fetchCalls = [];
        const storage = new Map();
        const commandPayloads = [];
        const buttons = [];

        function useButton(suggestion) {
          const button = {
            dataset: {},
            listeners: {},
            addEventListener(name, callback) { this.listeners[name] = callback; },
            closest() {
              return {
                querySelector() { return { textContent: suggestion }; },
              };
            },
          };
          buttons.push(button);
          return button;
        }

        const list = {
          dataset: {},
          innerHTML: "",
          querySelectorAll(selector) {
            if (selector !== ".use-btn") return [];
            return [
              useButton("Sure, I can help."),
              useButton("Thank you for your message."),
              useButton("I will review this."),
            ];
          },
        };
        const document = {
          addEventListener(name, callback) { listeners[name] = callback; },
          querySelector() { return null; },
          getElementById(id) {
            if (id === "suggestions-list") return list;
            return null;
          },
        };
        const window = {
          location: { href: "" },
          AICommandCenter: {
            prefillCompose(payload) { commandPayloads.push(payload); },
          },
        };
        const context = {
          window,
          document,
          Event: class Event {},
          fetch: async (url, options) => {
            fetchCalls.push({ url, options });
            return {
              ok: true,
              json: async () => ({
                suggestions: {
                  casual: "Sure, I can help.",
                  formal: "Thank you for your message.",
                  professional: "I will review this.",
                },
              }),
            };
          },
          localStorage: {
            getItem: (key) => storage.get(key) || null,
            setItem: (key, value) => storage.set(key, value),
            removeItem: (key) => storage.delete(key),
          },
          console, JSON, String, Promise, Error,
        };
        vm.createContext(context);
        vm.runInContext(
          fs.readFileSync("static/js/reply_suggestions.js", "utf8"),
          context,
        );

        (async () => {
          const trimmed = window.EmailReplySuggestions.originalEmail(
            "Please review this.\n\nOn Monday Alice wrote:\nOld thread",
          );
          assert.equal(trimmed, "Please review this.");

          await window.EmailReplySuggestions.generate({
            list,
            bodyText: "Please review this.\n\nOn Monday Alice wrote:\nOld thread",
          });
          assert.equal(fetchCalls.length, 1);
          assert.equal(fetchCalls[0].url, "/nlp/suggest");
          assert.deepEqual(
            JSON.parse(fetchCalls[0].options.body),
            { text: "Please review this." },
          );
          assert.equal(list.dataset.state, "ready");
          assert.match(list.innerHTML, /professional/);
          assert.match(list.innerHTML, /I will review this/);

          buttons[0].listeners.click();
          assert.deepEqual(commandPayloads, [{ body: "Sure, I can help." }]);

          delete window.AICommandCenter;
          window.EmailReplySuggestions.prefillCompose("Standalone reply");
          assert.equal(storage.get("replySuggestionDraft"), "Standalone reply");
          assert.equal(window.location.href, "/auth/compose");

          const compose = {
            value: "",
            dispatchEvent() {},
          };
          document.getElementById = (id) => id === "message" ? compose : null;
          window.EmailReplySuggestions.restoreComposeHandoff();
          assert.equal(compose.value, "Standalone reply");
          assert.equal(storage.has("replySuggestionDraft"), false);
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

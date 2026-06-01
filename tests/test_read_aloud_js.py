import subprocess
import textwrap


def test_read_aloud_selects_text_plays_cleans_up_and_stops_second_click():
    script = textwrap.dedent(r"""
        const fs = require("fs");
        const vm = require("vm");
        const assert = require("assert");

        const listeners = {};
        const payloads = [];
        const revoked = [];
        const toasts = [];
        const audios = [];
        let pendingFetch = null;

        const document = {
          addEventListener: (name, callback) => { listeners[name] = callback; },
          getElementById: () => null,
          querySelector: () => null,
        };
        const window = {
          showToast: (message, type) => toasts.push({ message, type }),
          alert: () => {},
        };
        const URL = {
          createObjectURL: () => "blob:audio",
          revokeObjectURL: (url) => revoked.push(url),
        };
        class Audio {
          constructor(src) {
            this.src = src;
            this.paused = false;
            audios.push(this);
          }
          play() { return Promise.resolve(); }
          pause() { this.paused = true; }
        }
        const fetch = (_url, options) => {
          payloads.push(JSON.parse(options.body));
          if (pendingFetch) return pendingFetch(options.signal);
          return Promise.resolve({
            ok: true,
            blob: async () => ({ size: 10 }),
          });
        };
        const context = {
          window, document, URL, Audio, fetch, AbortController, Blob,
          localStorage: { getItem: () => "Hindi" },
          console, Promise, String, Error, JSON,
        };
        vm.createContext(context);
        vm.runInContext(fs.readFileSync("static/js/read_aloud.js", "utf8"), context);

        function button() {
          return { dataset: {}, textContent: "▶ Read aloud" };
        }

        (async () => {
          const readySummary = { textContent: "यह तैयार सारांश है।" };
          assert.deepEqual(
            JSON.parse(JSON.stringify(window.EmailReadAloud.selectText({
              summaryElement: readySummary,
              bodyText: "Original body",
            }))),
            { text: "यह तैयार सारांश है।", translate: false }
          );
          assert.deepEqual(
            JSON.parse(JSON.stringify(window.EmailReadAloud.selectText({
              summaryElement: { textContent: 'Click "Summarize" to generate AI summary.' },
              bodyText: "Original body",
            }))),
            { text: "Original body", translate: true }
          );

          const first = button();
          await window.EmailReadAloud.play({
            button: first,
            summaryElement: readySummary,
            bodyText: "Original body",
          });
          assert.equal(payloads[0].language, "Hindi");
          assert.equal(payloads[0].translate, false);
          assert.equal(first.textContent, "■ Stop");
          audios[0].onended();
          assert.equal(first.textContent, "▶ Read aloud");
          assert.deepEqual(revoked, ["blob:audio"]);

          let aborted = false;
          pendingFetch = (signal) => new Promise((_resolve, reject) => {
            signal.addEventListener("abort", () => {
              aborted = true;
              const error = new Error("aborted");
              error.name = "AbortError";
              reject(error);
            });
          });
          const second = button();
          const pending = window.EmailReadAloud.play({
            button: second,
            summaryElement: { textContent: "" },
            bodyText: "Fallback body",
          });
          assert.equal(payloads[1].translate, true);
          await window.EmailReadAloud.play({
            button: second,
            summaryElement: { textContent: "" },
            bodyText: "Fallback body",
          });
          await pending;
          assert.equal(aborted, true);
          assert.equal(second.textContent, "▶ Read aloud");
          assert.deepEqual(toasts, []);
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

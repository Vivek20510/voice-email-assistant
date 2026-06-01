import subprocess
import textwrap


def test_outlook_notifications_poll_detect_acknowledge_and_open_messages():
    script = textwrap.dedent(r"""
        const fs = require("fs");
        const vm = require("vm");
        const assert = require("assert");

        function makeElement(id) {
          return {
            id,
            dataset: {},
            hidden: false,
            innerHTML: "",
            textContent: "",
            listeners: {},
            classList: { toggle() {}, remove() {} },
            addEventListener(type, handler) { this.listeners[type] = handler; },
            setAttribute(name, value) { this[name] = value; },
            closest(selector) {
              if (selector === ".notification-center") return this.inNotificationCenter ? this : null;
              if (selector === ".notification-item") return this.notificationItem || null;
              return null;
            },
            querySelectorAll() { return []; },
          };
        }

        const elements = {
          "notification-toggle": makeElement("notification-toggle"),
          "notification-count": makeElement("notification-count"),
          "notification-menu": makeElement("notification-menu"),
          "notification-list": makeElement("notification-list"),
          "inbox-unread-badge": makeElement("inbox-unread-badge"),
          "inbox-content": makeElement("inbox-content"),
        };
        elements["notification-menu"].hidden = true;

        const documentListeners = {};
        const document = {
          getElementById: (id) => elements[id] || null,
          addEventListener: (type, handler) => { documentListeners[type] = handler; },
          querySelectorAll: () => [],
          createElement: () => ({ innerHTML: "", value: "" }),
        };

        let intervalDelay = null;
        let fetchCalls = [];
        let messages = [];
        let resolveRefresh;
        let holdRefresh = false;
        const opened = [];

        const context = {
          window: {},
          document,
          console,
          Promise,
          Map,
          Set,
          Array,
          String,
          Boolean,
          Date,
          encodeURIComponent,
          setInterval: (handler, delay) => { intervalDelay = delay; return 1; },
          setTimeout: (handler) => handler(),
          showToast: () => {},
          loadMessageDetail: (id) => opened.push(id),
          fetch: async (url) => {
            fetchCalls.push(url);
            if (url === "/api/outlook/refresh") {
              if (holdRefresh) await new Promise((resolve) => { resolveRefresh = resolve; });
              return { ok: true, status: 202, json: async () => ({ status: "sync_started" }) };
            }
            return { ok: true, json: async () => ({ messages }) };
          },
        };

        vm.createContext(context);
        vm.runInContext(fs.readFileSync("static/js/dashboard.js", "utf8"), context);

        (async () => {
          context.window.OutlookNotifications.initialize();
          assert.equal(intervalDelay, 30000);

          context.window.OutlookNotifications.record([
            { id: "outlook:old", channel: "outlook", subject: "Existing" },
          ]);
          assert.equal(elements["notification-count"].hidden, true);

          messages = [
            { id: "outlook:new", channel: "outlook", sender: "Alice", subject: "New plan", unread: true },
            { id: "outlook:old", channel: "outlook", subject: "Existing", unread: false },
          ];
          assert.equal(await context.window.OutlookNotifications.refresh(), true);
          assert.equal(elements["notification-count"].textContent, "1");
          assert.equal(elements["notification-count"].hidden, false);
          assert.ok(elements["notification-list"].innerHTML.includes("New plan"));

          elements["notification-toggle"].listeners.click({ stopPropagation() {} });
          assert.equal(elements["notification-menu"].hidden, false);
          assert.equal(elements["notification-count"].hidden, true);
          assert.ok(elements["notification-list"].innerHTML.includes("New plan"));
          await new Promise((resolve) => setImmediate(resolve));

          const item = { dataset: { messageId: "outlook:new" } };
          elements["notification-list"].listeners.click({
            target: { closest: () => item },
          });
          assert.deepEqual(opened, ["outlook:new"]);

          holdRefresh = true;
          const first = context.window.OutlookNotifications.refresh();
          const second = await context.window.OutlookNotifications.refresh();
          assert.equal(second, false);
          resolveRefresh();
          assert.equal(await first, true);

          const cached = vm.runInContext(
            'inboxMessagesCacheByChannel["outlook_sb-outlook"]',
            context,
          );
          assert.equal(cached.length, 2);
          assert.ok(fetchCalls.includes("/api/outlook/refresh"));
          assert.ok(fetchCalls.includes("/api/messages?limit=25&channel=outlook"));
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
    """)

    result = subprocess.run(
        ["node", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr

const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { test } = require("node:test");
const { runInNewContext } = require("node:vm");
const { resolve } = require("node:path");

const scope = "https://carburantradar.fr/";
const data = { stationId: "75001001", lat: 48.8566, lon: 2.3522, carburant: "E10", country: "france" };
const script = process.argv[2] || resolve(__dirname, "../service-worker.js");

function setup(windows = []) {
  const handlers = {};
  const result = {};
  const clients = { matchAll: async () => windows, openWindow: async url => { result.opened = url; } };
  const self = {
    registration: {
      scope,
      showNotification: async (title, options) => { result.notice = { title, options }; },
    },
    addEventListener(name, callback) { handlers[name] = callback; },
  };
  runInNewContext(readFileSync(script, "utf8"), { self, clients, URL, URLSearchParams });

  function invoke(type, payload) {
    let task;
    handlers[type]({ ...payload, waitUntil(promise) { task = promise; } });
    return task;
  }
  return {
    result,
    push: payload => invoke("push", { data: { json: () => payload } }),
    click: payload => invoke("notificationclick", { notification: {
      data: payload,
      close() { result.closed = true; },
    } }),
  };
}

function checkDestination(url) {
  const target = new URL(url);
  assert.equal(target.origin, new URL(scope).origin);
  assert.equal(target.pathname, "/france/");
  assert.equal(target.searchParams.get("notif"), "1");
  assert.deepEqual(Object.fromEntries(new URLSearchParams(target.hash.slice(1))), {
    station: data.stationId, lat: String(data.lat), lon: String(data.lon), carburant: "E10",
  });
}

test("un vrai message push conserve les données nécessaires au clic à froid", async () => {
  const { push, click, result } = setup();
  await push({ ...data, title: "CarburantRadar", body: "Une station moins chère" });
  assert.equal(result.notice.title, "CarburantRadar");
  await click(result.notice.options.data);
  assert.equal(result.closed, true);
  checkDestination(result.opened);
});

test("un clic sur la notification française réutilise la fenêtre France", async () => {
  let destination;
  let focused = false;
  const espagne = { url: scope + "espagne/", focus() { assert.fail("Fenêtre incorrecte"); } };
  const france = {
    url: scope + "france/",
    async navigate(url) { destination = url; return this; },
    focus() { focused = true; },
  };
  const { click, result } = setup([espagne, france]);
  await click(data);
  checkDestination(destination);
  assert.equal(focused, true);
  assert.equal(result.opened, undefined);
});

test("si la navigation est refusée, la fenêtre de l’appli reçoit la station", async () => {
  let message;
  let focused = false;
  const france = {
    url: scope + "france/",
    async navigate() { return null; },
    postMessage(payload) { message = payload; },
    focus() { focused = true; },
  };
  const { click } = setup([france]);
  await click(data);
  assert.equal(message.type, "NOTIFICATION_CLICK");
  assert.equal(message.stationId, data.stationId);
  assert.equal(message.carburant, data.carburant);
  assert.equal(focused, true);
});

test("les alertes historiques restent lisibles avec un identifiant seul", async () => {
  const { click, result } = setup();
  await click({ stationId: data.stationId });
  assert.equal(result.opened, scope + "france/?notif=1#station=" + data.stationId);
});

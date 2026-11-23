import test from "node:test";
import assert from "node:assert/strict";
import worker from "../src/index.js";
import { contexte, envoyer, requeteApi, sha256, video, R2Fake } from "./harness.mjs";

test("publie une fois, archive et relève les deux plateformes à J+30 avec le même Worker", async () => {
  const c = contexte(worker, { VIDEO_STATS: new R2Fake() });
  const slot = "2026-11-07:matin";
  const octets = video("fiche de test");
  c.net.yt.id = "abcdefghijk";
  c.net.ig.id = "18000000001";
  await c.env.CONFIG_KV.put("instagram_token_carburant", JSON.stringify({
    access_token: "presque-expire", expires_at: Date.now() + 3600000,
  }));
  let renouvellements = 0;
  const reponse = (data) => Response.json(data);
  const reseau = c.net._traiter.bind(c.net);
  c.net._traiter = async (url, init) => {
    if (url.startsWith("https://graph.instagram.com/refresh_access_token?")) {
      assert.equal(new URL(url).searchParams.get("access_token"), "presque-expire");
      renouvellements++;
      return reponse({ access_token: "token-renouvele", expires_in: 60 * 86400 });
    }
    if (url === "https://graph.instagram.com/v21.0/ig-c/media") {
      assert.equal(JSON.parse(init.body).access_token, "token-renouvele");
    }
    if (url.startsWith("https://www.googleapis.com/youtube/v3/videos?")) {
      return reponse({ items: [{ id: c.net.yt.id, statistics: { viewCount: "0" },
        snippet: { title: "Test", description: "#Shorts #carburant" } }] });
    }
    if (url.includes("/insights?")) {
      return reponse({ data: [{ name: "views", values: [{ value: 24 }] }] });
    }
    if (url.includes("?fields=caption")) return reponse({ caption: "#carburant #reel" });
    return reseau(url, init);
  };
  const stats = (route, body, cle = c.env.API_KEY) => envoyer(worker, c.env,
    new Request(`https://video-automation.test/api/stats/${route}`, {
      method: body ? "POST" : "GET",
      headers: { Authorization: `Bearer ${cle}` },
      body: body && JSON.stringify(body),
    }));
  const soumettre = () => envoyer(worker, c.env, requeteApi({ octets, slot, sha: sha256(octets) }));
  const date = "2026-11-07T07:00:00Z";
  const horloge = Date.now;
  try {
    const premier = await soumettre();
    assert.equal(premier.corps.etat, "complet");
    const recus = ["youtube", "instagram"].map(plateforme => ({
      plateforme, video_id: premier.corps[plateforme].remote_id, id_video: slot,
      publie_le: date, categorie: "ville_du_jour", carburant: "e10", musique: 2, duree_s: 23, organique: true,
    }));
    for (const recu of recus) assert.equal((await stats("recu", recu)).statut, 200);
    assert.equal((await stats("mesures", undefined, "incorrecte")).statut, 401);
    assert.equal((await envoyer(worker, c.env, new Request(
      "https://video-automation.test/media/publications/youtube/abcdefghijk"))).statut, 404);
    Date.now = () => Date.parse(date) + 30 * 24 * 3600000;
    for (const recu of recus) {
      assert.equal((await stats("relever", recu)).corps.statut, "releve");
      assert.equal((await stats("relever", recu)).corps.statut, "deja_releve");
    }
    const exporte = (await stats("mesures")).corps.lignes;
    assert.deepEqual(exporte.map(m => [m.plateforme, m.vues, m.horizon_jours, m.duree_s, m.musique, m.hashtags]), [
      ["instagram", 24, 30, 23, 2, ["#carburant", "#reel"]],
      ["youtube", 0, 30, 23, 2, ["#shorts", "#carburant"]],
    ]);
    assert.equal((await soumettre()).corps.rejoue, true);
    assert.deepEqual([c.net.appels.youtube, c.net.appels.instagram_publish], [1, 1]);
    assert.equal(renouvellements, 1);
  } finally {
    Date.now = horloge;
    c.fin();
  }
});

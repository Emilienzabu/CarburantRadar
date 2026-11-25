"""Tests de non-régression : publication d'assetlinks.json et cohérence APK / TWA.

Lancer depuis la racine du dépôt :  python3 -m unittest tests/test_twa_assetlinks.py -v
Dépendances optionnelles (les tests concernés sont ignorés si absentes) :
  pip install cryptography androguard
"""
import json
import os
import re
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APK = os.path.join(ROOT, "CarburantRadar.apk")
ASSETLINKS = os.path.join(ROOT, ".well-known", "assetlinks.json")
FP_RE = re.compile(r"^([0-9A-F]{2}:){31}[0-9A-F]{2}$")


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


def domain():
    return read("CNAME").strip()


class AssetLinksPublication(unittest.TestCase):
    def test_dossier_bien_nomme(self):
        # Régression : le dossier s'appelait ". well-known" (avec un espace),
        # donc /.well-known/assetlinks.json renvoyait 404.
        self.assertTrue(os.path.isfile(ASSETLINKS), ".well-known/assetlinks.json absent")
        faux = [n for n in os.listdir(ROOT)
                if n != ".well-known" and re.fullmatch(r"\s*\.?\s*well[-_ ]?known\s*", n, re.I)]
        self.assertEqual(faux, [], "dossier mal nommé : %r" % faux)

    def test_json_valide_et_relation(self):
        data = json.loads(read(".well-known/assetlinks.json"))
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)
        for st in data:
            self.assertIn("delegate_permission/common.handle_all_urls", st["relation"])
            self.assertEqual(st["target"]["namespace"], "android_app")
            self.assertTrue(st["target"]["package_name"])
            fps = st["target"]["sha256_cert_fingerprints"]
            self.assertTrue(fps)
            for fp in fps:
                self.assertRegex(fp, FP_RE)

    def test_domaine_personnalise(self):
        self.assertEqual(domain(), "carburantradar.fr")


class ApkCoherence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.isfile(APK):
            raise unittest.SkipTest("CarburantRadar.apk absent")

    def _statements(self):
        return json.loads(read(".well-known/assetlinks.json"))

    def test_certificat_apk_dans_assetlinks(self):
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.serialization import pkcs7
        except ImportError:
            self.skipTest("module cryptography absent")
        with zipfile.ZipFile(APK) as z:
            rsa = [n for n in z.namelist() if n.startswith("META-INF/") and n.endswith((".RSA", ".DSA", ".EC"))]
            self.assertTrue(rsa, "aucune signature v1 dans l'APK")
            der = z.read(rsa[0])
        cert = pkcs7.load_der_pkcs7_certificates(der)[0]
        fp = ":".join("%02X" % b for b in cert.fingerprint(hashes.SHA256()))
        declared = [f for s in self._statements() for f in s["target"]["sha256_cert_fingerprints"]]
        self.assertIn(fp, declared)

    def _apk_resources(self):
        try:
            from loguru import logger
            logger.remove()
            from androguard.core.apk import APK as A
        except ImportError:
            self.skipTest("module androguard absent")
        a = A(APK)
        res = a.get_android_resources()
        pkg = a.get_package()
        vals = {}
        for name in ("hostName", "launchUrl", "fullScopeUrl", "webManifestUrl"):
            rid = res.get_res_id_by_key(pkg, "string", name)
            vals[name] = res.get_string(pkg, name)[1] if rid else None
        return pkg, vals

    def test_package_apk_dans_assetlinks(self):
        pkg, _ = self._apk_resources()
        declared = [s["target"]["package_name"] for s in self._statements()]
        self.assertIn(pkg, declared)

    def test_apk_cible_le_domaine_personnalise(self):
        _, v = self._apk_resources()
        d = domain()
        self.assertEqual(v["hostName"], d)
        self.assertTrue(v["launchUrl"].startswith("https://%s/" % d))
        self.assertTrue(v["fullScopeUrl"].startswith("https://%s/" % d))
        self.assertTrue(v["webManifestUrl"].startswith("https://%s/" % d))


class NonRegressionPWA(unittest.TestCase):
    def test_manifest_pwa(self):
        m = json.loads(read("manifest.json"))
        self.assertEqual(m["display"], "standalone")
        self.assertTrue(m["start_url"])
        self.assertTrue(m["scope"])
        sizes = {i["sizes"] for i in m["icons"]}
        self.assertTrue({"192x192", "512x512"} <= sizes)
        for i in m["icons"]:
            self.assertTrue(os.path.isfile(os.path.join(ROOT, i["src"])), i["src"])

    def test_service_worker_notifications_intacts(self):
        sw = read("service-worker.js")
        for needle in ("'push'", "notificationclick"):
            self.assertIn(needle, sw)

    def test_pages_pays_inchangees(self):
        for p in ("france", "espagne", "italie"):
            html = read("%s/index.html" % p)
            self.assertIn('rel="manifest" href="../manifest.json"', html)
            self.assertIn("rel=\"apple-touch-icon\"", html)
            self.assertIn("APK_URL='../CarburantRadar.apk'", html)


if __name__ == "__main__":
    unittest.main()

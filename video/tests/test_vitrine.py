"""Tests du format « vitrine » (captures de l'app, voix, sous-titres mot à mot). Aucun réseau, aucune publication.

Depuis la racine du dépôt :  python -m unittest discover -s video/tests -v
Les écrans de test sont synthétiques : les vraies captures ne sont pas nécessaires pour la CI.
"""
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

VIDEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIDEO))

import audio  # noqa: E402
import generate_video as gv  # noqa: E402
import vitrine  # noqa: E402


def ecrans_synthetiques(dossier):
    for i, nom in enumerate(vitrine.ECRANS):
        Image.new("RGB", (vitrine.EC_W, vitrine.EC_H), (20 + 30 * i, 30, 60)).save(os.path.join(dossier, f"ecran_{nom}.png"))


def scenes_planifiees():
    """Scènes planifiées avec une voix factice (silence) et des mots répartis régulièrement."""
    sd = vitrine.scenes_texte()
    clips = [np.zeros(int(3.0 * audio.SR), dtype=np.float32) if s["mots"] else np.zeros(0, dtype=np.float32) for s in sd]
    scenes = audio.planifier(sd, clips, vitrine.DEBUT_SCENE, vitrine.FIN_SCENE)
    mots = []
    for s in sd:
        n = len(s["mots"])
        mots.append([(a, 0.1 + i * 2.8 / n, 0.1 + (i + 1) * 2.8 / n) for i, (a, _) in enumerate(s["mots"])])
    vitrine.attacher_mots(scenes, sd, mots)
    return scenes


class TestPrononciation(unittest.TestCase):
    def test_plus_quantitatif_prononce(self):
        self.assertEqual(audio.prononcer_tokens("Et en plus, c'est gratuit.".split()), ["Et", "en", "plusse,", "c'est", "gratuit."])
        self.assertEqual(audio.prononcer_tokens("Pour plus de choix".split())[1], "plusse")
        self.assertEqual(audio.prononcer_tokens("Tu veux plus.".split())[-1], "plusse.")

    def test_plus_muet_comparatif_et_negation(self):
        self.assertEqual(audio.prononcer_tokens("Tu paies plus cher".split()), ["Tu", "paies", "plus", "cher"])
        self.assertEqual(audio.prononcer_tokens("les stations les plus avantageuses".split())[3], "plus")
        self.assertEqual(audio.prononcer_tokens("Il n'y en a plus.".split())[-1], "plus.")

    def test_affichage_inchange(self):
        """La prononciation ne touche que le texte dit : l'affiché garde « plus »."""
        toks = vitrine.analyser_script("Et en plus, c'est gratuit.")
        self.assertEqual([a for a, _ in toks][2], "plus,")
        self.assertEqual([p for _, p in toks][2], "plusse,")

    def test_crochets_affiche_prononce(self):
        toks = vitrine.analyser_script("Sur [carburantradar.fr|Carburant Radar point F R].")
        self.assertEqual(toks[-1], ("carburantradar.fr.", "Carburant Radar point F R."))
        self.assertEqual(vitrine.analyser_script("l’app")[0][1], "l'app")   # apostrophe typographique normalisée pour la voix


class TestHorodatage(unittest.TestCase):
    def test_mapper_limites_fusionne_les_mots_prononces(self):
        toks = [("Sur", "Sur"), ("carburantradar.fr.", "Carburant Radar point F R.")]
        lim = [("Sur", 0.0, 0.2)] + [(m, 0.2 + i * 0.2, 0.4 + i * 0.2) for i, m in enumerate("Carburant Radar point F R.".split())]
        res = audio.mapper_limites(toks, lim)
        self.assertEqual(res[0], ("Sur", 0.0, 0.2))
        self.assertEqual(res[1][0], "carburantradar.fr.")
        self.assertAlmostEqual(res[1][1], 0.2)
        self.assertAlmostEqual(res[1][2], 1.2)

    def test_mapper_limites_nombre_inattendu(self):
        self.assertIsNone(audio.mapper_limites([("a", "a"), ("b", "b")], [("a", 0, 1)]))

    def test_estimation_suit_les_pauses_de_l_audio(self):
        sr = audio.SR
        x = np.zeros(int(2.4 * sr), dtype=np.float32)
        t = np.arange(len(x)) / sr
        voix = np.sin(2 * np.pi * 200 * t).astype(np.float32)
        for a, b in ((0.2, 0.9), (1.5, 2.2)):      # deux propositions séparées par 0,6 s de silence
            x[int(a * sr):int(b * sr)] = voix[int(a * sr):int(b * sr)]
        res = audio.aligner_estime(["Un", "détour,", "tout", "change."], x)
        self.assertEqual(len(res), 4)
        self.assertAlmostEqual(res[0][0], 0.2, delta=0.03)
        self.assertAlmostEqual(res[1][1], 0.9, delta=0.03)       # fin de la 1re proposition = fin de la 1re plage
        self.assertAlmostEqual(res[2][0], 1.5, delta=0.03)       # début de la 2e = début de la 2e plage
        self.assertAlmostEqual(res[3][1], 2.2, delta=0.03)
        self.assertTrue(all(a <= b for a, b in res))

    def test_estimation_clip_muet_ne_plante_pas(self):
        res = audio.aligner_estime(["a", "b"], np.zeros(audio.SR, dtype=np.float32))
        self.assertEqual(len(res), 2)

    def _faux_edge(self, avec_boundary):
        class Com:
            def __init__(self, texte, voix, *, rate="+0%", **kw):
                if "boundary" in kw and not avec_boundary:
                    raise TypeError("boundary")
                self.kw, Com.dernier = kw, (texte, voix, rate, kw)

            async def stream(self):
                yield {"type": "audio", "data": b"x" * 2000}
                yield {"type": "WordBoundary", "offset": 3_000_000, "duration": 2_000_000, "text": "Un"}
                yield {"type": "WordBoundary", "offset": 5_500_000, "duration": 4_000_000, "text": "détour"}
                yield {"type": "SentenceBoundary", "offset": 0, "duration": 9_000_000, "text": "Un détour"}
        return types.SimpleNamespace(Communicate=Com)

    def test_edge_tts_demande_et_lit_les_limites_de_mots(self):
        faux = self._faux_edge(True)
        with mock.patch.dict(sys.modules, {"edge_tts": faux}), tempfile.TemporaryDirectory() as d:
            lim = audio._tts_edge_mots("Un détour", "fr-FR-RemyMultilingualNeural", os.path.join(d, "a.mp3"), "+10%")
        self.assertEqual(faux.Communicate.dernier[3].get("boundary"), "WordBoundary")
        self.assertEqual(faux.Communicate.dernier[2], "+10%")
        self.assertEqual(lim, [("Un", 0.3, 0.5), ("détour", 0.55, 0.95)])   # 100 ns -> s ; les phrases sont ignorées

    def test_edge_tts_ancienne_version_sans_boundary(self):
        faux = self._faux_edge(False)
        with mock.patch.dict(sys.modules, {"edge_tts": faux}), tempfile.TemporaryDirectory() as d:
            lim = audio._tts_edge_mots("Un détour", "v", os.path.join(d, "a.mp3"), "+4%")
        self.assertEqual(len(lim), 2)

    def test_planifier_valeurs_par_defaut_inchangees(self):
        """Les formats existants gardent leurs silences (0,35 s avant, 0,75 s après)."""
        sc = audio.planifier([{"id": "a", "min": 1.0, "texte": "x"}], [np.zeros(audio.SR * 2, dtype=np.float32)])
        self.assertAlmostEqual(sc[0]["dur"], 0.35 + 2.0 + 0.75)
        self.assertAlmostEqual(sc[0]["voix_debut"], 0.35)

    def test_sans_voix_les_mots_sont_repartis(self):
        sd = vitrine.scenes_texte()
        scenes = audio.planifier(sd, [None] * len(sd), vitrine.DEBUT_SCENE, vitrine.FIN_SCENE)
        vitrine.attacher_mots(scenes, sd, [None] * len(sd))
        for sc, d in zip(scenes, sd):
            self.assertEqual(len(sc["mots"]), len(d["mots"]))
            self.assertTrue(all(sc["start"] <= a <= b <= sc["start"] + sc["dur"] for _, a, b in sc["mots"]))


class TestScript(unittest.TestCase):
    def test_aucun_chiffre_dans_le_texte_dit(self):
        """Les valeurs affichées viennent des captures ; la voix n'énonce aucun chiffre."""
        for sc in vitrine.scenes_texte():
            self.assertFalse(any(c.isdigit() for c in sc["texte"]), sc["texte"])

    def test_valeurs_des_captures(self):
        v = vitrine.VALEURS
        self.assertEqual((v["prix_min"], v["prix_moy"], v["economie"], v["variation_pct"]), (2.035, 2.168, 4.97, -6.4))
        self.assertEqual(v["direct_min"] + v["detour_min"], v["total_min"])

    def test_derniere_scene_sans_voix(self):
        sd = vitrine.scenes_texte()
        self.assertEqual(sd[-1]["id"], "cta")
        self.assertEqual(sd[-1]["mots"], [])

    def test_ecrans_jamais_agrandis(self):
        self.assertLess(vitrine.S, 1.0)
        self.assertLess(vitrine.DISP_W, vitrine.EC_W)


class TestRendu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        ecrans_synthetiques(cls.tmp.name)
        cls.scenes = scenes_planifiees()
        icone = VIDEO.parent / "icons" / "icon-512.png"
        cls.rend = vitrine.RendererVitrine(vitrine.info_vitrine(), cls.scenes, str(VIDEO / "fonts"), str(icone), cls.tmp.name)
        total = cls.scenes[-1]["start"] + cls.scenes[-1]["dur"]
        cls.temps = [0.0, 0.5, 2.0, 3.5, 6.0, 8.0, 10.5, 12.5, 15.5, 18.0, total - 2.0, total - 0.05]
        cls.frames = {t: np.array(cls.rend.frame(t)) for t in cls.temps}
        cls.bg = np.array(cls.rend.bg)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_dimensions(self):
        for im in self.frames.values():
            self.assertEqual(im.shape, (1920, 1080, 3))

    def test_aucun_logo_barre_ni_halo_en_haut(self):
        """Haut de l'image (zone sûre supérieure) : strictement le fond, à tout instant (pas de logo fixe, de barre, de halo)."""
        for t, im in self.frames.items():
            self.assertTrue(np.array_equal(im[:190], self.bg[:190]), f"t={t}")

    def test_fond_sans_halo(self):
        """Le fond est un dégradé vertical pur : chaque ligne est uniforme (un halo la rendrait non uniforme)."""
        self.assertTrue(np.all(self.bg == self.bg[:, :1, :]))

    def test_zones_sures_bas_et_cotes(self):
        for t, im in self.frames.items():
            self.assertTrue(np.array_equal(im[1560:], self.bg[1560:]), f"bas t={t}")
            self.assertTrue(np.array_equal(im[:, :28], self.bg[:, :28]), f"gauche t={t}")
            self.assertTrue(np.array_equal(im[:, 1052:], self.bg[:, 1052:]), f"droite t={t}")

    def test_les_frames_changent_dans_le_temps(self):
        self.assertFalse(np.array_equal(self.frames[2.0], self.frames[3.5]))

    def test_sous_titres_presents_pendant_la_parole(self):
        sc = self.scenes[0]
        t = sc["mots"][1][1] + 0.02
        im = np.array(self.rend.frame(t))
        zone = im[1420:1520]
        self.assertFalse(np.array_equal(zone, self.bg[1420:1520]))

    def test_sous_titres_dans_la_zone_sure(self):
        """Chaque groupe de mots tient dans 940 px de large, quelle que soit la police disponible."""
        f = self.rend.F.get("bold", 62)
        for c in self.rend.chunks:
            fin = c["x"][-1] + f.getlength(c["mots"][-1][0])
            self.assertGreaterEqual(c["x"][0], 69)
            self.assertLessEqual(fin, 1011)

    def test_bulles_aux_bonnes_valeurs(self):
        """Les textes des bulles viennent de VALEURS (pas de chiffre codé en double dans le rendu)."""
        src = (VIDEO / "vitrine.py").read_text(encoding="utf-8")
        for interdit in ("2,035", "2,168", "4,97", "6,4"):
            self.assertNotIn(interdit, src.split("VALEURS = ")[1].split("}")[1])

    def test_ecrans_manquants(self):
        with tempfile.TemporaryDirectory() as vide:
            with self.assertRaises(FileNotFoundError) as e:
                vitrine.RendererVitrine(vitrine.info_vitrine(), self.scenes, str(VIDEO / "fonts"), None, vide)
            self.assertIn("ecran_radar.png", str(e.exception))

    def test_commande_ffmpeg_heritee(self):
        cmd = self.rend.commande_ffmpeg("a.wav", "o.mp4")
        self.assertIn("-use_editlist", cmd)
        self.assertEqual(cmd[cmd.index("-ar") + 1], "48000")


class TestPublicationRefusee(unittest.TestCase):
    def lancer(self, *argv):
        with mock.patch.object(sys, "argv", ["generate_video.py", *argv]), \
                mock.patch.object(gv.requests, "post", side_effect=AssertionError("aucun envoi attendu")):
            with self.assertRaises(SystemExit) as e:
                gv.main()
        return str(e.exception)

    def test_vitrine_jamais_publiee(self):
        msg = self.lancer("--format", "vitrine", "--publier")
        self.assertIn("jamais publiée", msg)

    def test_vitrine_refusee_meme_garde_desactivee(self):
        with mock.patch.dict(os.environ, {"VIDEO_GARDE_ASTUCE": "0"}):
            self.assertIn("jamais publiée", self.lancer("--format", "vitrine", "--publier"))

    def test_voix_locale_jamais_publiee(self):
        self.assertIn("voix de test", self.lancer("--voix-locale", "--publier"))

    def test_la_garde_astuce_reste_active_par_defaut(self):
        import garde
        self.assertTrue(garde.garde_astuce_active({}))

    def test_vitrine_absente_du_planning(self):
        import donnees
        self.assertNotIn("vitrine", donnees.FORMATS_POIDS)


if __name__ == "__main__":
    unittest.main()

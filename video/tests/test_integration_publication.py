"""main() complet : contrôle avant publication + gestion des envois incertains / partiels.

Aucun accès réseau, aucune publication réelle : le Worker est simulé. Les MP4 sont de VRAIS fichiers (ffmpeg) afin que le
contrôle réel (controle_publication) s'exécute, et non un contrôle simulé.
"""
import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import numpy as np
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "video"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import donnees  # noqa: E402
import generate_video as gv  # noqa: E402
import rendu  # noqa: E402
from test_controle_publication import fabriquer  # noqa: E402

FFMPEG = shutil.which("ffmpeg") and shutil.which("ffprobe")
CLES = {"VIDEO_API_KEY": "cle-de-test"}
COMMANDE_REELLE = rendu.Renderer.commande_ffmpeg   # capturée avant que les tests ne remplacent Renderer


def faux_clips(scenes_def, tmpdir, voix=None, journal=print):
    from musique import SR
    t = np.arange(int(0.8 * SR)) / SR
    return [(0.3 * np.sin(2 * np.pi * 180 * t)).astype(np.float32) for _ in scenes_def]


class Reponse:
    def __init__(self, corps, statut=200, json_ok=True):
        self._c, self.status_code, self.text, self._ok = corps, statut, str(corps), json_ok

    def json(self):
        if not self._ok:
            raise ValueError("pas du JSON")
        return self._c


_CACHE = {}


def _mp4_modele(conforme):
    """Un vrai MP4 par cas, fabriqué une seule fois pour toute la série de tests."""
    if conforme not in _CACHE:
        dossier = tempfile.mkdtemp(prefix="cr-tests-")
        _CACHE[conforme] = fabriquer(Path(dossier) / "modele.mp4", taille="1080x1920" if conforme else "480x854")
    return _CACHE[conforme]


def tearDownModule():
    for chemin in _CACHE.values():
        shutil.rmtree(Path(chemin).parent, ignore_errors=True)


def rendu_factice(*, conforme=True):
    """Renderer qui écrit un vrai MP4 (conforme ou en 480x854) et expose la commande réelle de rendu."""
    class R:
        def __init__(self, info, scenes, polices, icone):
            self.info, self.scenes, self.total = info, scenes, 13.0

        def encode(self, wav, sortie, journal):
            self.derniere_commande = COMMANDE_REELLE(self, wav, sortie)
            shutil.copyfile(_mp4_modele(conforme), sortie)

        def save_png(self, t, chemin):
            Path(chemin).write_bytes(b"png")
    return R


@unittest.skipUnless(FFMPEG, "ffmpeg/ffprobe absents")
class FluxDePublication(unittest.TestCase):
    def lancer(self, argv=("--publier",), *, post, conforme=True, env=None):
        appels = []

        def faux_post(url, **kw):
            appels.append(kw.get("data"))
            return post(url, **kw)

        with tempfile.TemporaryDirectory() as tmp:
            resume = os.path.join(tmp, "resume.md")
            e = {**CLES, "GITHUB_STEP_SUMMARY": resume, **(env or {})}
            with mock.patch.object(sys, "argv", ["g.py", *argv, "--sortie", os.path.join(tmp, "v.mp4")]), \
                    mock.patch.dict(os.environ, e), \
                    mock.patch.object(gv, "assurer_polices", lambda d: None), \
                    mock.patch.object(gv.audio, "synth_clips", faux_clips), \
                    mock.patch.object(gv.rendu, "Renderer", rendu_factice(conforme=conforme)), \
                    mock.patch.object(gv.requests, "post", faux_post), \
                    mock.patch.object(donnees, "recuperer_stations", side_effect=AssertionError("prix interdits")), \
                    redirect_stdout(io.StringIO()) as sortie:
                os.environ.pop("VIDEO_GARDE_ASTUCE", None)
                try:
                    gv.main()
                    code = 0
                except SystemExit as exc:
                    code = exc.code
            contenu = Path(resume).read_text(encoding="utf-8") if os.path.exists(resume) else ""
            manifeste = list(Path(tmp).glob("*.manifeste.json"))
        return code, appels, sortie.getvalue(), contenu, manifeste

    ok = staticmethod(lambda u, **k: Reponse({"youtube": {"success": True, "url": "https://youtu.be/x"},
                                              "instagram": {"success": True}}))

    def test_publication_complete(self):
        code, appels, log, resume, manifeste = self.lancer(post=self.ok)
        self.assertEqual(code, 0, log)
        self.assertEqual(len(appels), 1)
        self.assertIn("Contrôle avant publication : accepté", log)
        self.assertIn("**complet**", resume)
        self.assertEqual(len(manifeste), 1)

    def test_video_basse_resolution_bloque_toute_publication(self):
        code, appels, log, resume, _ = self.lancer(post=self.ok, conforme=False)
        self.assertIn("Vidéo non conforme", str(code))
        self.assertEqual(appels, [], "le Worker ne doit JAMAIS être appelé si le contrôle refuse")
        self.assertIn("resolution_incorrecte", log)

    def test_generation_sans_publication_est_aussi_controlee(self):
        code, appels, log, _, _ = self.lancer(("--demo", "--format", "ville"), post=self.ok, conforme=False)
        self.assertIn("Vidéo non conforme", str(code))
        self.assertEqual(appels, [])

    def test_delai_depasse_est_incertain_et_jamais_reessaye(self):
        def timeout(url, **kw):
            raise requests.exceptions.ReadTimeout("délai dépassé")
        code, appels, log, resume, _ = self.lancer(post=timeout)
        self.assertEqual(len(appels), 1, "un envoi incertain ne doit pas être réessayé")
        self.assertIn("INCERTAIN", str(code))
        self.assertIn("AVANT de relancer", str(code))
        self.assertIn("**incertain**", resume)
        self.assertIn("doublon", resume)

    def test_erreur_reseau_apres_envoi_est_incertaine(self):
        def coupure(url, **kw):
            raise requests.exceptions.ConnectionError("connexion coupée")
        code, appels, _, _, _ = self.lancer(post=coupure)
        self.assertEqual(len(appels), 1)
        self.assertIn("INCERTAIN", str(code))

    def test_reponse_illisible_est_incertaine(self):
        code, appels, _, _, _ = self.lancer(post=lambda u, **k: Reponse("<html>502</html>", 502, json_ok=False))
        self.assertEqual(len(appels), 1)
        self.assertIn("INCERTAIN", str(code))

    def test_reponse_json_non_objet_est_incertaine(self):
        code, appels, _, _, _ = self.lancer(post=lambda u, **k: Reponse(["oups"]))
        self.assertIn("INCERTAIN", str(code))

    def test_succes_partiel_est_signale_et_pas_relance(self):
        rep = Reponse({"youtube": {"success": True, "url": "https://youtu.be/x"}, "instagram": {"success": False}})
        code, appels, log, resume, _ = self.lancer(post=lambda u, **k: rep)
        self.assertEqual(code, 0)
        self.assertEqual(len(appels), 1)
        self.assertIn("::warning::Publication PARTIELLE", log)
        self.assertIn("**partiel**", resume)
        self.assertIn("doublon", resume)

    def test_succes_partiel_instagram_seul(self):
        rep = Reponse({"youtube": {"success": False}, "instagram": {"success": True}})
        code, _, log, _, _ = self.lancer(post=lambda u, **k: rep)
        self.assertEqual(code, 0)
        self.assertIn("YouTube=False, Instagram=True", log)

    def test_echec_clair_sur_les_deux_plateformes(self):
        rep = Reponse({"youtube": {"success": False}, "instagram": {"success": False}})
        code, appels, _, resume, _ = self.lancer(post=lambda u, **k: rep)
        self.assertIn("échoué sur les deux", str(code))
        self.assertEqual(len(appels), 1)
        self.assertIn("**echec**", resume)

    def test_demo_ne_peut_pas_etre_publie_meme_garde_desactivee(self):
        code, appels, _, _, _ = self.lancer(("--publier", "--demo", "--format", "ville"), post=self.ok,
                                            env={"VIDEO_GARDE_ASTUCE": "0"})
        # la ligne os.environ.pop de lancer() retire VIDEO_GARDE_ASTUCE : on vérifie donc l'interdiction elle-même
        self.assertIn("--demo", str(code))
        self.assertEqual(appels, [])

    def test_cle_absente(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            code, appels, _, _, _ = self.lancer(post=self.ok, env={"VIDEO_API_KEY": ""})
        self.assertIn("VIDEO_API_KEY manquante", str(code))
        self.assertEqual(appels, [])


if __name__ == "__main__":
    unittest.main()

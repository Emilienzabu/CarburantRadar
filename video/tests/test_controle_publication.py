"""Tests de video/controle_publication.py sur de VRAIS fichiers MP4 produits par ffmpeg (aucun réseau, aucune publication).

Depuis la racine du dépôt :  python -m unittest discover -s video/tests -v
Les tests sont ignorés (et non réussis) si ffmpeg/ffprobe sont absents ; le workflow les installe.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "video"))

import controle_publication as cp  # noqa: E402
import rendu  # noqa: E402

FFMPEG = shutil.which("ffmpeg") and shutil.which("ffprobe")


def fabriquer(chemin, *, taille="1080x1920", duree=13, hz=48000, audio="sine", editlist=False, faststart=True,
              extra=()):
    """Vidéo synthétique. Par défaut : conforme (1080x1920, H.264, AAC 48 kHz, -14 LUFS, sans edit list, faststart)."""
    src_audio = "sine=frequency=220:sample_rate=48000" if audio == "sine" else "anullsrc=r=48000:cl=stereo"
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "lavfi", "-i", f"testsrc2=size={taille}:rate=30:duration={duree}",
           "-f", "lavfi", "-i", f"{src_audio}:duration={duree}" if audio == "sine" else f"{src_audio}",
           "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k"]
    if audio == "sine":
        cmd += ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11"]
    cmd += ["-ar", str(hz), "-ac", "2", "-t", str(duree)]
    if not editlist:
        cmd += ["-use_editlist", "0"]
    if faststart:
        cmd += ["-movflags", "+faststart"]
    cmd += list(extra) + [str(chemin)]
    subprocess.run(cmd, check=True, capture_output=True)
    return chemin


def manifeste_pour(mp4, commande=None, nom=".manifeste.json", **kw):
    commande = commande or rendu.Renderer.commande_ffmpeg(_FauxRenderer(), "audio.wav", "sortie.mp4")
    m = cp.construire_manifeste(mp4, commande, **kw)
    chemin = Path(mp4).with_suffix(nom)
    cp.ecrire_manifeste(chemin, m)
    return chemin


class _FauxRenderer:
    total = 13.0


@unittest.skipUnless(FFMPEG, "ffmpeg/ffprobe absents")
class AvecDeVraisFichiers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        cls.bon = fabriquer(d / "bon.mp4")
        cls.basse_res = fabriquer(d / "480.mp4", taille="480x854")
        cls.hz96 = fabriquer(d / "96k.mp4", hz=96000)
        cls.editlist = fabriquer(d / "elst.mp4", editlist=True)
        cls.muet = fabriquer(d / "muet.mp4", audio="muet")
        cls.court = fabriquer(d / "court.mp4", duree=5)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def erreurs(self, mp4, **kw):
        return cp.valider_avant_publication(mp4, manifeste_pour(mp4), **kw).erreurs

    # --- cas acceptés / refusés sur de vrais fichiers ---
    def test_video_conforme_acceptee(self):
        r = cp.valider_avant_publication(self.bon, manifeste_pour(self.bon))
        self.assertTrue(r.accepte, r.erreurs)
        self.assertEqual(r.erreurs, ())

    def test_basse_resolution_refusee_meme_avec_un_manifeste_complaisant(self):
        # le manifeste (déclaratif) affirme 1080x1920 : la sonde réelle du fichier doit quand même refuser
        self.assertIn("sonde:resolution_incorrecte", self.erreurs(self.basse_res))

    def test_audio_96k_refuse(self):
        self.assertIn("sonde:audio_frequence_trop_elevee", self.erreurs(self.hz96))

    def test_edit_list_refusee(self):
        self.assertIn("conteneur:edit_list_presente", self.erreurs(self.editlist))

    def test_audio_muet_refuse(self):
        self.assertIn("audio:audio_muet", self.erreurs(self.muet))

    def test_duree_trop_courte_refusee(self):
        self.assertIn("sonde:duree_incorrecte", self.erreurs(self.court))

    def test_fichier_tronque_refuse(self):
        coupe = Path(self.tmp.name) / "coupe.mp4"
        coupe.write_bytes(self.bon.read_bytes()[:200_000])
        r = cp.valider_avant_publication(coupe, manifeste_pour(coupe))
        self.assertFalse(r.accepte)

    def test_fichier_modifie_apres_le_manifeste_refuse(self):
        copie = Path(self.tmp.name) / "copie.mp4"
        shutil.copy(self.bon, copie)
        m = manifeste_pour(copie)
        with copie.open("ab") as f:
            f.write(b"\0")          # un octet de plus : l'empreinte ne correspond plus
        r = cp.valider_avant_publication(copie, m)
        self.assertIn("manifeste:empreinte_differente", r.erreurs)

    def test_moov_apres_mdat_refuse(self):
        brut = Path(self.tmp.name) / "brut.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(self.bon), "-c", "copy",
                        "-use_editlist", "0", str(brut)], check=True)   # sans +faststart : moov en fin de fichier
        self.assertIn("moov_apres_mdat", cp.verifier_conteneur(brut))

    def test_rotation_refusee(self):
        pivote = Path(self.tmp.name) / "pivote.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-display_rotation", "90", "-i", str(self.bon),
                        "-c", "copy", "-use_editlist", "0", "-movflags", "+faststart", str(pivote)], check=True)
        self.assertIn("sonde:affichage_pivote", self.erreurs(pivote))


@unittest.skipUnless(FFMPEG, "ffmpeg/ffprobe absents")
class EchecFermeEtManifeste(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.mp4 = fabriquer(Path(cls.tmp.name) / "bon.mp4")
        cls.manifeste = manifeste_pour(cls.mp4, slot_id="2026-11-07:matin", format_video="astuce", titre="t")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_fichiers_absents(self):
        self.assertEqual(cp.valider_avant_publication("/nexiste/pas.mp4", self.manifeste).erreurs, ("mp4_absent",))
        r = cp.valider_avant_publication(self.mp4, "/nexiste/pas.json")
        self.assertIn("manifeste:manifeste_absent", r.erreurs)

    def test_panne_de_controle_refuse(self):
        def casse(_):
            raise OSError("ffprobe introuvable")
        r = cp.valider_avant_publication(self.mp4, self.manifeste, sonder_fn=casse)
        self.assertFalse(r.accepte)
        self.assertIn("sonde:exception_OSError", r.erreurs)

    def test_resultat_incoherent_d_une_etape_refuse(self):
        r = cp.valider_avant_publication(self.mp4, self.manifeste, decodage_fn=lambda _: True)
        self.assertIn("decodage:exception_TypeError", r.erreurs)

    def test_toutes_les_erreurs_sont_conservees(self):
        r = cp.valider_avant_publication(self.mp4, self.manifeste, decodage_fn=lambda _: ("a",),
                                         audio_fn=lambda _: ("b",), conteneur_fn=lambda _: ("c",))
        self.assertEqual(set(r.erreurs), {"decodage:a", "audio:b", "conteneur:c"})

    def test_manifeste_illisible(self):
        mauvais = Path(self.tmp.name) / "mauvais.json"
        mauvais.write_text("{pas du json", encoding="utf-8")
        self.assertIn("manifeste:manifeste_illisible", cp.valider_avant_publication(self.mp4, mauvais).erreurs)

    def test_exiger_slot(self):
        sans = manifeste_pour(self.mp4, nom=".sans-slot.json")   # slot_id = None
        self.assertIn("manifeste:slot_invalide", cp.valider_avant_publication(self.mp4, sans, exiger_slot=True).erreurs)
        self.assertTrue(cp.valider_avant_publication(self.mp4, self.manifeste, exiger_slot=True).accepte)

    def test_cli(self):
        ok = subprocess.run([sys.executable, str(ROOT / "video" / "controle_publication.py"),
                             "--mp4", str(self.mp4), "--manifest", str(self.manifeste)], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stdout)
        self.assertEqual(json.loads(ok.stdout), {"accepte": True, "erreurs": []})
        ko = subprocess.run([sys.executable, str(ROOT / "video" / "controle_publication.py"),
                             "--mp4", str(self.mp4), "--manifest", "/nexiste/pas.json"], capture_output=True, text=True)
        self.assertEqual(ko.returncode, 2)


class FonctionsPures(unittest.TestCase):
    def sonde(self, **sur):
        v = {"codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920, "pix_fmt": "yuv420p",
             "avg_frame_rate": "30/1"}
        a = {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 2}
        v.update(sur.get("v", {}))
        a.update(sur.get("a", {}))
        return {"streams": [v, a], "format": {"duration": sur.get("duree", "25.3")}}

    def test_sonde_conforme(self):
        self.assertEqual(cp.verifier_sonde(self.sonde()), ())

    def test_sondes_non_conformes(self):
        cas = {
            "resolution_incorrecte": {"v": {"width": 480, "height": 854}},
            "codec_video_incorrect": {"v": {"codec_name": "hevc"}},
            "format_pixel_incorrect": {"v": {"pix_fmt": "yuv444p"}},
            "fps_incorrect": {"v": {"avg_frame_rate": "10/1"}},
            "fps_illisible": {"v": {"avg_frame_rate": "0/0"}},
            "pixels_non_carres": {"v": {"sample_aspect_ratio": "4:3"}},
            "affichage_pivote": {"v": {"tags": {"rotate": "90"}}},
            "codec_audio_incorrect": {"a": {"codec_name": "mp3"}},
            "audio_frequence_trop_elevee": {"a": {"sample_rate": "96000"}},
            "audio_frequence_illisible": {"a": {"sample_rate": "x"}},
            "audio_canaux_incorrects": {"a": {"channels": 6}},
            "duree_incorrecte": {"duree": "90"},
            "duree_illisible": {"duree": "abc"},
        }
        for attendu, params in cas.items():
            with self.subTest(attendu):
                self.assertIn(attendu, cp.verifier_sonde(self.sonde(**params)))

    def test_sonde_invalide(self):
        for x in (None, [], {}, {"streams": "x"}):
            self.assertEqual(cp.verifier_sonde(x), ("sonde_invalide",))

    def test_flux_manquants(self):
        self.assertIn("un_seul_flux_audio_attendu", cp.verifier_sonde({"streams": [self.sonde()["streams"][0]],
                                                                       "format": {"duration": "20"}}))
        self.assertIn("un_seul_flux_video_attendu", cp.verifier_sonde({"streams": [self.sonde()["streams"][1]],
                                                                       "format": {"duration": "20"}}))

    def test_loudness(self):
        self.assertEqual(cp.verifier_audio("x", mesure=lambda _: (-14.0, -3.0)), ())
        self.assertEqual(cp.verifier_audio("x", mesure=lambda _: (-14.0, 0.0)), ("crete_audio_trop_haute",))
        self.assertEqual(cp.verifier_audio("x", mesure=lambda _: (-8.0, -3.0)), ("loudness_hors_plage",))
        self.assertEqual(cp.verifier_audio("x", mesure=lambda _: (float("-inf"), float("-inf"))), ("audio_muet",))
        self.assertEqual(cp.verifier_audio("x", mesure=lambda _: (-50.0, -40.0)), ("audio_muet",))

        def casse(_):
            raise ValueError
        self.assertEqual(cp.verifier_audio("x", mesure=casse), ("loudness_illisible",))

    def test_boites_mp4_invalides(self):
        for octets in (b"\0\0\0", b"\0\0\0\x04free", b"\0\0\0\x20ftyp"):
            with self.assertRaises(ValueError):
                cp.boites_mp4(octets)


class CommandeDeRenduReelle(unittest.TestCase):
    """La commande ffmpeg RÉELLEMENT utilisée par rendu.Renderer, sans rien rendre."""

    def commande(self):
        return rendu.Renderer.commande_ffmpeg(_FauxRenderer(), "audio.wav", "sortie.mp4")

    def test_pas_de_mise_a_l_echelle_et_canevas_natif(self):
        w, h, redim = cp.analyser_commande(self.commande())
        self.assertEqual((w, h, redim), (1080, 1920, False))

    def test_contraintes_meta(self):
        c = self.commande()
        self.assertEqual(c[c.index("-ar") + 1], "48000")                 # AAC 48 kHz maximum
        self.assertEqual(c[c.index("-use_editlist") + 1], "0")           # pas d'edit list
        self.assertIn("+faststart", c)                                   # moov au début
        self.assertEqual(c[c.index("-colorspace") + 1], "bt709")
        self.assertLessEqual(int(c[c.index("-ar") + 1]), cp.AUDIO_HZ_MAX)

    def test_detection_des_mises_a_l_echelle(self):
        base = self.commande()
        petit = list(base)
        petit[petit.index("-s") + 1] = "480x854"
        self.assertTrue(cp.analyser_commande(petit)[2])
        agrandi = list(base)
        agrandi[agrandi.index("-vf") + 1] = "scale=1080:1920"
        self.assertTrue(cp.analyser_commande(agrandi)[2])
        autre = list(base)
        autre[autre.index("-vf") + 1] = "scale=out_color_matrix=bt709,unsharp"
        self.assertTrue(cp.analyser_commande(autre)[2])
        for mauvais in (None, "x", ["ffmpeg", "-s"], ["ffmpeg", "-s", "abc"], ["ffmpeg"]):
            with self.assertRaises((ValueError, IndexError)):
                cp.analyser_commande(mauvais)

    def test_manifeste_refuse_si_mise_a_l_echelle(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "x.mp4"
            f.write_bytes(b"x" * 2048)
            petit = list(self.commande())
            petit[petit.index("-s") + 1] = "480x854"
            m = cp.construire_manifeste(f, petit)
            e = cp.verifier_manifeste(m, f)
            self.assertIn("mise_a_l_echelle_non_exclue", e)
            self.assertIn("source_basse_resolution", e)


if __name__ == "__main__":
    unittest.main()

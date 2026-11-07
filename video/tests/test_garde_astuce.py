"""Tests de la garde temporaire « publication = format astuce » (aucun accès réseau, aucune publication réelle).

Depuis la racine du dépôt :  python -m unittest discover -s video/tests -v
"""
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
VIDEO = ROOT / "video"
WORKFLOW = ROOT / ".github" / "workflows" / "video-du-jour.yml"
sys.path.insert(0, str(VIDEO))

import controle_publication as cp  # noqa: E402
import donnees  # noqa: E402
import garde  # noqa: E402
import generate_video as gv  # noqa: E402


def workflow_script():
    """Script bash de l'étape « Générer la vidéo » du workflow réel."""
    lignes = WORKFLOW.read_text(encoding="utf-8").splitlines()
    idx = [i for i, l in enumerate(lignes) if l.strip().startswith("- name: Générer la vidéo")]
    assert len(idx) == 1, "étape de génération introuvable"
    i = next(j for j in range(idx[0], len(lignes)) if lignes[j] == "        run: |")
    out = []
    for l in lignes[i + 1:]:
        if l and not l.startswith("          "):
            break
        out.append(l[10:] if l.startswith("          ") else "")
    return "\n".join(out)


def args_du_workflow(evenement, publier, fmt, creneau="", ville="", carburant=""):
    """Arguments réellement construits par le workflow (la dernière ligne python est remplacée par un affichage)."""
    script = workflow_script()
    aiguille = 'python video/generate_video.py "${ARGS[@]}"'
    assert script.count(aiguille) == 1
    script = script.replace(aiguille, 'if [ ${#ARGS[@]} -gt 0 ]; then printf "<%s>\\n" "${ARGS[@]}"; fi')
    env = {**os.environ, "EVENEMENT": evenement, "PUBLIER": publier, "FORMAT": fmt,
           "CRENEAU": creneau, "VILLE": ville, "CARBURANT": carburant}
    r = subprocess.run(["bash", "-e", "-c", script], env=env, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return [x[1:-1] for x in r.stdout.splitlines() if x.startswith("<") and x.endswith(">")]


class GardeUnitaire(unittest.TestCase):
    def test_activation_par_defaut_et_desactivation_explicite(self):
        self.assertTrue(gv.garde_astuce_active({}))
        self.assertTrue(gv.garde_astuce_active({"VIDEO_GARDE_ASTUCE": "1"}))
        self.assertTrue(gv.garde_astuce_active({"VIDEO_GARDE_ASTUCE": ""}), "valeur vide = garde active")
        for v in ("0", "false", "FALSE", "non", "off", " 0 "):
            self.assertFalse(gv.garde_astuce_active({"VIDEO_GARDE_ASTUCE": v}), v)

    def test_publication_force_astuce(self):
        cas = [
            ["--publier"],
            ["--publier", "--format", "ville", "--ville", "paris", "--carburant", "e10"],
            ["--publier", "--format", "classement"],
            ["--publier", "--format", "astuce"],
            ["--publier", "--ville", "marseille"],
            ["--publier", "--creneau", "soir", "--format", "ville"],
        ]
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VIDEO_GARDE_ASTUCE", None)
            for argv in cas:
                with self.subTest(argv=argv):
                    a = gv.construire_parser().parse_args(argv)
                    gv.appliquer_garde_astuce(a)
                    self.assertTrue(a.publier)
                    self.assertEqual((a.format, a.ville, a.carburant), ("astuce", None, None))

    def test_creneau_conserve(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VIDEO_GARDE_ASTUCE", None)
            a = gv.construire_parser().parse_args(["--publier", "--creneau", "soir", "--format", "ville"])
            gv.appliquer_garde_astuce(a)
            self.assertEqual(a.creneau, "soir")

    def test_sans_publication_rien_ne_change(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VIDEO_GARDE_ASTUCE", None)
            for argv, attendu in [(["--format", "ville", "--ville", "paris", "--carburant", "e10"], ("ville", "paris", "e10")),
                                  (["--format", "classement"], ("classement", None, None)),
                                  ([], (None, None, None)),
                                  (["--demo", "--format", "ville"], ("ville", None, None))]:
                with self.subTest(argv=argv):
                    a = gv.construire_parser().parse_args(argv)
                    self.assertFalse(gv.appliquer_garde_astuce(a))
                    self.assertEqual((a.format, a.ville, a.carburant), attendu)

    def test_garde_desactivee_laisse_les_arguments(self):
        with mock.patch.dict(os.environ, {"VIDEO_GARDE_ASTUCE": "0"}):
            a = gv.construire_parser().parse_args(["--publier", "--format", "ville", "--ville", "paris"])
            self.assertFalse(gv.appliquer_garde_astuce(a))
            self.assertEqual((a.format, a.ville), ("ville", "paris"))


class GardeAvecLeWorkflowReel(unittest.TestCase):
    """Les arguments construits par le vrai workflow, passés à l'analyseur réel puis à la garde."""

    def resultat(self, *params):
        argv = args_du_workflow(*params)
        a = gv.construire_parser().parse_args(argv)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VIDEO_GARDE_ASTUCE", None)
            gv.appliquer_garde_astuce(a)
        return a

    def test_planification_deux_fois_par_jour_intacte(self):
        wf = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('cron: "40 6 * * *"', wf)
        self.assertIn('cron: "40 16 * * *"', wf)
        self.assertEqual(wf.count("- cron:"), 2)

    def test_publications_programmees_et_manuelles(self):
        for params in [("schedule", "", "", ""), ("schedule", "", "planning", "auto"),
                       ("schedule", "", "ville", "", "marseille", "gazole"),
                       ("workflow_dispatch", "true", "ville", "", "paris", "e10"),
                       ("workflow_dispatch", "true", "classement"), ("workflow_dispatch", "true", "planning"),
                       ("workflow_dispatch", "true", "astuce", "soir")]:
            with self.subTest(params=params):
                a = self.resultat(*params)
                self.assertTrue(a.publier)
                self.assertEqual((a.format, a.ville, a.carburant), ("astuce", None, None))

    def test_generation_sans_publication_inchangee(self):
        for params, attendu in [(("workflow_dispatch", "false", "ville", "", "paris", "e10"), ("ville", "paris", "e10")),
                                (("workflow_dispatch", "false", "classement"), ("classement", None, None)),
                                (("workflow_dispatch", "false", "astuce"), ("astuce", None, None)),
                                (("workflow_dispatch", "false", "planning"), (None, None, None))]:
            with self.subTest(params=params):
                a = self.resultat(*params)
                self.assertFalse(a.publier)
                self.assertEqual((a.format, a.ville, a.carburant), attendu)


def faux_clips(scenes_def, tmpdir, voix=None, journal=print):
    from musique import SR
    t = np.arange(int(0.8 * SR)) / SR
    return [(0.3 * np.sin(2 * np.pi * 180 * t)).astype(np.float32) for _ in scenes_def]


class FauxRendu:
    def __init__(self, info, scenes, polices, icone):
        self.info, self.scenes = info, scenes

    def encode(self, wav, sortie, journal):
        assert os.path.getsize(wav) > 1000
        Path(sortie).write_bytes(b"mp4-simule")

    def save_png(self, t, chemin):
        Path(chemin).write_bytes(b"png-simule")


class ReponseWorker:
    def __init__(self, corps, statut=200):
        self._c, self.status_code, self.text = corps, statut, str(corps)

    def json(self):
        return self._c


class MainBoutEnBout(unittest.TestCase):
    """main() complet avec voix, rendu et Worker simulés : aucun accès réseau, aucune vidéo publiée."""

    def lancer(self, argv, reponse=None):
        appels = []

        def faux_post(url, **kw):
            appels.append({"url": url, "data": kw.get("data"), "headers": kw.get("headers")})
            return reponse or ReponseWorker({"youtube": {"success": True, "url": "https://youtu.be/x"},
                                             "instagram": {"success": True}})

        def interdit(*a, **k):
            raise AssertionError("accès aux prix interdit dans ce test")

        env = {"VIDEO_API_KEY": "cle-de-test"}
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(sys, "argv", ["generate_video.py", *argv, "--sortie", os.path.join(tmp, "v.mp4")]), \
                mock.patch.dict(os.environ, env), \
                mock.patch.object(gv, "assurer_polices", lambda d: None), \
                mock.patch.object(gv.audio, "synth_clips", faux_clips), \
                mock.patch.object(gv.rendu, "Renderer", FauxRendu), \
                mock.patch.object(gv.requests, "post", faux_post), \
                mock.patch.object(gv, "controler_video", lambda *a, **k: cp.Resultat(True, ())), \
                mock.patch.object(donnees, "recuperer_stations", interdit), \
                mock.patch.object(donnees, "recuperer_classement", interdit), \
                redirect_stdout(io.StringIO()) as sortie:
            os.environ.pop("VIDEO_GARDE_ASTUCE", None)
            try:
                gv.main()
                code = 0
            except SystemExit as e:
                code = e.code
        return code, appels, sortie.getvalue()

    def test_publication_ville_demandee_est_publiee_en_astuce_sans_toucher_aux_prix(self):
        code, appels, log = self.lancer(["--publier", "--format", "ville", "--ville", "paris", "--carburant", "e10"])
        self.assertEqual(code, 0, log)
        self.assertEqual(len(appels), 1)
        d = appels[0]["data"]
        texte = " ".join(str(v) for v in d.values()).lower()
        self.assertNotIn("€", texte)
        for v in donnees.VILLES:
            self.assertNotIn(v["nom"].lower(), texte)
        self.assertIn("GARDE ASTUCE", log)
        self.assertIn("format astuce", log)

    def test_publication_planning_reste_astuce(self):
        code, appels, log = self.lancer(["--publier"])
        self.assertEqual(code, 0, log)
        self.assertEqual(len(appels), 1)
        self.assertIn("format astuce", log)

    def test_generation_sans_publication_ne_contacte_pas_le_worker(self):
        code, appels, log = self.lancer(["--demo", "--format", "ville"])
        self.assertEqual(code, 0, log)
        self.assertEqual(appels, [])
        self.assertIn("format ville", log)
        self.assertNotIn("GARDE ASTUCE", log)

    def test_publication_echouee_sur_les_deux_plateformes_est_un_echec(self):
        rep = ReponseWorker({"youtube": {"success": False}, "instagram": {"success": False}})
        code, appels, log = self.lancer(["--publier"], reponse=rep)
        self.assertNotEqual(code, 0)
        self.assertEqual(len(appels), 1)

    def test_defense_en_profondeur_refuse_un_format_geographique(self):
        with mock.patch.object(gv, "appliquer_garde_astuce", lambda a, j=None: False), \
                mock.patch.object(gv, "construire", lambda plan, k, args: donnees.info_demo("ville")):
            code, appels, log = self.lancer(["--publier", "--format", "ville"])
        self.assertIn("Garde astuce", str(code))
        self.assertEqual(appels, [])

    def test_voix_indisponible_reste_un_echec_explicite(self):
        with mock.patch.object(gv.audio, "synth_clips", lambda s, t, v=None, j=print: [None] * len(s)):
            appels = []
            with tempfile.TemporaryDirectory() as tmp, \
                    mock.patch.object(sys, "argv", ["g.py", "--publier", "--sortie", os.path.join(tmp, "v.mp4")]), \
                    mock.patch.dict(os.environ, {"VIDEO_API_KEY": "x"}), \
                    mock.patch.object(gv, "assurer_polices", lambda d: None), \
                    mock.patch.object(gv.requests, "post", lambda *a, **k: appels.append(1)), \
                    redirect_stdout(io.StringIO()):
                os.environ.pop("VIDEO_GARDE_ASTUCE", None)
                with self.assertRaises(SystemExit) as cm:
                    gv.main()
        self.assertIn("Voix indisponible", str(cm.exception.code))
        self.assertEqual(appels, [])


class CatalogueEtPlan(unittest.TestCase):
    def test_plan_astuce_sans_donnees_geographiques(self):
        vus = []
        for k in range(1479850, 1479850 + 28):
            plan = garde.plan_astuce(k, donnees.ASTUCES)
            self.assertEqual(plan["format"], "astuce")
            self.assertNotIn("villes", plan)
            vus.append(plan["astuce"]["titre"])
        self.assertEqual(len(set(vus)), len(donnees.ASTUCES))
        for a, b in zip(vus, vus[1:]):
            self.assertNotEqual(a, b, "deux conseils identiques d'affilée")

    def test_rotation_identique_a_l_ancienne_sauf_collision_de_frontiere(self):
        n = len(donnees.ASTUCES)
        poids = {i: 1 for i in range(n)}
        differences = 0
        for k in range(0, 3000):
            nouveau = garde.indice_astuce(k, n)
            ancien = donnees.pioche("astuce", poids, k)
            if nouveau != ancien:
                differences += 1
                self.assertIn(k % n, (0, 1), "seules les deux premières places d'un cycle peuvent changer")
        self.assertLess(differences, 3000 // n, "au plus une correction par cycle")

    def test_jamais_deux_conseils_identiques_de_suite_ni_manque(self):
        n = len(donnees.ASTUCES)
        suite = [garde.indice_astuce(k, n) for k in range(0, 5000)]
        for a, b in zip(suite, suite[1:]):
            self.assertNotEqual(a, b)
        for c in range(0, 5000 // n):
            self.assertEqual(sorted(suite[c * n:(c + 1) * n]), list(range(n)), "chaque conseil une fois par cycle")

    def test_catalogue_sans_chiffre_geographique(self):
        self.assertGreaterEqual(len(donnees.ASTUCES), 7)
        self.assertEqual(len({a["titre"] for a in donnees.ASTUCES}), len(donnees.ASTUCES))
        for a in donnees.ASTUCES:
            self.assertEqual(len(a["points"]), 3)
            self.assertNotIn("€", " ".join([a["titre"], *a["points"]]))


if __name__ == "__main__":
    unittest.main(verbosity=2)

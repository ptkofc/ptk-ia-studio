import os, subprocess, tempfile, time, unittest
from pathlib import Path
from ptk_engine import tools, silence
from ptk_engine.ffmpeg_core import probe, find_binary, Runner, Cancelled, safe_output
from ptk_engine.db import DB
from ptk_engine.jobs import JobQueue

def make_sample(path, parts="tone-silence-tone"):
    """6s: 2s tom, 2s silencio, 2s tom, com video colorido."""
    fc = ("aevalsrc=sin(440*2*PI*t):d=2[a1];anullsrc=r=44100:cl=mono,atrim=duration=2[a2];"
          "aevalsrc=sin(660*2*PI*t):d=2[a3];[a1][a2][a3]concat=n=3:v=0:a=1[a]")
    subprocess.run([find_binary("ffmpeg"), "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "testsrc=size=640x360:rate=25:duration=6", "-filter_complex", fc,
                    "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-c:a", "aac", "-shortest", path],
                   check=True)

class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = tempfile.mkdtemp(); cls.src = os.path.join(cls.d, "a.mp4"); make_sample(cls.src)
    def out(self, n): return os.path.join(self.d, n)

    def test_probe(self):
        i = probe(self.src)
        self.assertAlmostEqual(i["duration"], 6, delta=0.3)
        self.assertEqual((i["width"], i["height"]), (640, 360)); self.assertTrue(i["has_audio"])

    def test_cut(self):
        o = tools.cut(self.src, self.out("cut.mp4"), 1, 3)
        self.assertAlmostEqual(probe(o)["duration"], 2, delta=0.3)

    def test_no_overwrite(self):
        with self.assertRaises(FileExistsError): safe_output(self.src)

    def test_extract_audio(self):
        o = tools.extract_audio(self.src, self.out("a.mp3")); i = probe(o)
        self.assertTrue(i["has_audio"] and not i["has_video"])

    def test_speed(self):
        o = tools.change_speed(self.src, self.out("fast.mp4"), 2.0)
        self.assertAlmostEqual(probe(o)["duration"], 3, delta=0.4)

    def test_resize_916(self):
        o = tools.resize(self.src, self.out("v.mp4"), "9:16", "720p"); i = probe(o)
        self.assertEqual((i["width"], i["height"]), (404, 720))

    def test_gif_thumb_frames(self):
        self.assertTrue(os.path.getsize(tools.to_gif(self.src, self.out("a.gif"), 0, 2)) > 0)
        self.assertTrue(os.path.getsize(tools.thumbnail(self.src, self.out("t.jpg"))) > 0)
        tools.extract_frames(self.src, self.out("fr/f_%04d.png"), fps=1)
        self.assertGreaterEqual(len(list(Path(self.out("fr")).glob("*.png"))), 5)

    def test_concat_and_compress(self):
        o = tools.concat([self.src, self.src], self.out("cc.mp4"))
        self.assertAlmostEqual(probe(o)["duration"], 12, delta=0.6)
        self.assertTrue(probe(tools.compress(self.src, self.out("small.mp4")))["has_video"])

    def test_silence(self):
        s = silence.detect_silences(self.src)
        self.assertEqual(len(s), 1); self.assertAlmostEqual(s[0][0], 2, delta=0.2)
        keep = silence.remove_silence(self.src, "", dry_run=True); self.assertEqual(len(keep), 2)
        o = silence.remove_silence(self.src, self.out("nosil.mp4"))
        self.assertAlmostEqual(probe(o)["duration"], 4.2, delta=0.5)

    def test_export_webm_with_fps(self):
        o = tools.export(self.src, self.out("e.webm"), "webm", "480p", fps=15)
        i = probe(o); self.assertEqual(i["height"], 480); self.assertAlmostEqual(i["fps"], 15, delta=1)

    def test_progress_and_cancel(self):
        seen = []; tools.compress(self.src, self.out("p.mp4"), on_progress=seen.append)
        self.assertTrue(seen and seen[-1] == 1.0)
        r = Runner(); target = self.out("c.mp4")
        import threading; threading.Timer(0.05, r.cancel).start()
        with self.assertRaises(Cancelled):
            tools.concat([self.src]*8, target, runner=r)
        self.assertFalse(os.path.exists(target))

    def test_queue_error_cancel_retry(self):
        q = JobQueue()
        bad = q.submit("cut", tools.cut, src="/nao/existe.mp4", dst=self.out("x.mp4"), start=0, end=1)
        ok = q.submit("cut", tools.cut, src=self.src, dst=self.out("q.mp4"), start=0, end=1)
        for _ in range(100):
            if q.jobs[ok].status in ("concluido", "erro"): break
            time.sleep(0.1)
        self.assertEqual(q.jobs[bad].status, "erro"); self.assertEqual(q.jobs[ok].status, "concluido")
        self.assertIsInstance(q.retry(bad), int)

    def test_db(self):
        db = DB(self.out("t.db")); pid = db.new_project("Meu video")
        db.add_media(pid, self.src, "video", probe(self.src))
        self.assertEqual(len(db.list_media(pid)), 1); self.assertEqual(len(db.history(pid)), 2)
        self.assertEqual(db.list_projects()[0]["name"], "Meu video")

if __name__ == "__main__": unittest.main(verbosity=2)

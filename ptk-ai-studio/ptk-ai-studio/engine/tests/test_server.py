import json, os, subprocess, sys, tempfile, time, unittest
from tests.test_engine import make_sample

class S(unittest.TestCase):
    def test_roundtrip(self):
        d = tempfile.mkdtemp(); src = os.path.join(d, "a.mp4"); make_sample(src)
        env = dict(os.environ, PTK_DATA_DIR=d)
        p = subprocess.Popen([sys.executable, "-m", "ptk_engine.server"], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, text=True, env=env)
        def send(i, cmd, **a):
            p.stdin.write(json.dumps({"id": i, "cmd": cmd, "args": a}) + "\n"); p.stdin.flush()
        def read_until(i):
            while True:
                m = json.loads(p.stdout.readline())
                if m.get("id") == i: return m
        send(1, "ping"); self.assertEqual(read_until(1)["result"], "pong")
        send(2, "probe", path=src); self.assertTrue(read_until(2)["result"]["has_video"])
        send(3, "nope"); self.assertFalse(read_until(3)["ok"])
        send(4, "new_project", name="P"); pid = read_until(4)["result"]
        send(5, "import_media", project=pid, path=src); self.assertTrue(read_until(5)["ok"])
        send(6, "job", tool="cut", params=dict(src=src, dst=os.path.join(d, "c.mp4"), start=0, end=1))
        read_until(6); done = False
        for _ in range(100):
            m = json.loads(p.stdout.readline())
            if m.get("event") == "job" and m["job"]["status"] == "concluido": done = True; break
        self.assertTrue(done); p.stdin.close(); p.wait(timeout=5)

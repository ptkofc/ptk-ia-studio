import { useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { call, onJob, Job } from "./engine";

type Project = { id: number; name: string; created: number; updated: number };
const NAV = ["Início", "Edição Automática", "Editor Manual", "Ferramentas", "Biblioteca", "Automações", "Configurações"];

export default function App() {
  const [page, setPage] = useState(NAV[0]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [jobs, setJobs] = useState<Record<number, Job>>({});
  const [msg, setMsg] = useState("");

  const refresh = () => call<Project[]>("projects").then(setProjects).catch(e => setMsg(String(e)));
  useEffect(() => { refresh(); const un = onJob(j => setJobs(p => ({ ...p, [j.id]: j }))); return () => { un.then(f => f()); }; }, []);

  async function newProject() {
    const name = `Projeto ${projects.length + 1}`;
    await call("new_project", { name }); refresh();
  }
  async function importVideo() {
    const f = await open({ multiple: false, filters: [{ name: "Mídia", extensions: ["mp4","mov","mkv","webm","mp3","wav"] }] });
    if (!f || projects.length === 0) { setMsg("Crie um projeto antes de importar."); return; }
    try { await call("import_media", { project: projects[0].id, path: f }); setMsg("Mídia importada."); }
    catch (e) { setMsg(String(e)); }
  }
  const active = Object.values(jobs).filter(j => j.status === "processando");

  return (
    <div className="app">
      <aside>
        <h1>PTK <span>AI STUDIO</span></h1>
        {NAV.map(n => <button key={n} className={n === page ? "on" : ""} onClick={() => setPage(n)}>{n}</button>)}
      </aside>
      <main>
        <header>
          <h2>{page}</h2>
          <div className="status">{active.length ? `Processando ${Math.round(active[0].progress * 100)}%` : "Ocioso"}</div>
        </header>
        {page === "Início" ? (
          <section>
            <div className="actions">
              <button onClick={newProject}>Novo Projeto</button>
              <button onClick={importVideo}>Importar Vídeo</button>
            </div>
            <h3>Projetos recentes</h3>
            {projects.length === 0 && <p className="muted">Nenhum projeto ainda.</p>}
            {projects.map(p => <div className="card" key={p.id}>{p.name}<small>{new Date(p.created * 1000).toLocaleString("pt-BR")}</small></div>)}
            {msg && <p className="muted">{msg}</p>}
          </section>
        ) : (
          <section><p className="muted">Em desenvolvimento: esta tela ainda não está implementada.</p></section>
        )}
      </main>
    </div>
  );
}

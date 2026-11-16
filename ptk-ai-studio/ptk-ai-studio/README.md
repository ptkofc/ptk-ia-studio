# PTK AI STUDIO

Editor de vídeo com IA para Windows (Tauri 2 + React + Python/FFmpeg). **Versão 0.1 — em construção.**

## Status real (não inflado)

| Área | Estado |
|---|---|
| Motor FFmpeg: probe, cortar, unir, converter/exportar (MP4/MOV/WebM, resolução, FPS, CRF, legenda embutida), extrair áudio, velocidade, redimensionar (9:16, 16:9, 1:1, 4:5), comprimir, GIF, miniatura, extrair quadros | **Implementado e testado** (Linux, FFmpeg 6.1) |
| Remoção de silêncio com prévia dos trechos (dry-run) | **Implementado e testado** |
| Progresso real, cancelamento seguro (remove só o arquivo parcial), nunca sobrescreve sem autorização | **Testado** |
| Fila de tarefas: progresso, cancelar, repetir, pausar fila, erro isolado | **Testado** (pausar não interrompe a tarefa em curso) |
| SQLite: projetos, mídias, histórico | **Testado** |
| Ponte JSON stdin/stdout motor ↔ interface | **Testado** |
| Interface Tauri/React (dashboard, projetos, importar) | **Escrita, NÃO compilada nem testada** |
| Atalho global Ctrl+Shift+P, autostart | **Escrito em Rust, NÃO testado** (bandeja e opção de autostart na UI ainda faltam) |
| Workflow que gera o instalador .exe (GitHub Actions) | **Escrito, NÃO executado** |
| Timeline/editor manual, prévia de vídeo, legendas, Faster-Whisper, PySceneDetect, edição automática, automações, assistente de redes, gerenciador de modelos, configurações | **NÃO implementado** (Fases 3–4) |

## Testes do motor
```
cd engine && python -m unittest discover -s tests -t . -v
```
Requer Python 3.12 e FFmpeg no PATH (ou `PTK_FFMPEG_DIR`).

## Gerar o instalador Windows
1. Suba esta pasta para um repositório no GitHub.
2. Aba **Actions → Build Windows installer → Run workflow**.
3. Baixe o artefato `PTK-AI-STUDIO-installer` (.exe NSIS).
Se o build falhar, envie o log: o código Rust/TS foi escrito sem poder compilar e deve precisar de ajustes.

## Próximos passos
Fase 2: timeline e prévia · Fase 3: Faster-Whisper (legendas SRT), PySceneDetect, edição automática com aprovação · Fase 4: automações, modelos, assistente de conteúdo.

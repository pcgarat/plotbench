---
name: cerrar-feature
description: >-
  Cierra una feature de extremo a extremo: commit, push, PR en GitHub, merge
  y actualiza main local con el remoto. Usar solo cuando el usuario invoque
  /cerrar-feature o pida explícitamente cerrar la feature.
disable-model-invocation: true
---

# Cerrar feature

Flujo completo de cierre. Ejecutar los pasos **en orden**. No omitir el merge ni el sync de `main` salvo bloqueo real (CI, permisos, conflictos).

## Convenciones de este repo

- Commits: **Conventional Commits**, explicaciones en **español**.
- **Prohibido** trailers tipo "Made with Cursor", "Made by Cursor", co-authored-by de herramientas, o firmas de IA en commit/PR.
- No usar `--no-verify` / `--no-gpg-sign` salvo que el usuario lo pida.
- No `push --force` a `main`/`master`.
- No `git commit --amend` salvo las condiciones habituales del protocolo de commits.
- Tests habituales: `make test` o `pytest tests/ -m "not e2e"` (no e2e salvo petición explícita).

## Precondiciones (parar si fallan)

1. Estar en un repo git con remoto `origin` y `gh` autenticado (`gh auth status`).
2. **No** estar en `main`/`master` con cambios para cerrar: si estás en la rama por defecto, crear/cambiar a una rama de feature antes de continuar (no commits directos a main).
3. Si el working tree tiene secretos (`.env`, credenciales), **no** incluirlos; avisar y excluirlos.
4. Si no hay cambios locales ni commits sin pushear respecto a la base, informar y parar (nada que cerrar).

## Paso 0 — Contexto (en paralelo)

Ejecutar por separado (sin encadenar con `&&` innecesario en PowerShell, pero en bash del proyecto está bien agrupar lecturas):

```bash
git status
git branch --show-current
git rev-parse --abbrev-ref origin/HEAD
git log --oneline -10
git diff HEAD
gh pr list --head "$(git branch --show-current)" --state open --json number,url,title,state
```

Resolver rama base: `origin/HEAD` → p.ej. `main`; si falla, `gh repo view --json defaultBranchRef -q .defaultBranchRef.name`; fallback `main`.

## Paso 1 — Commit (si hay cambios)

1. Revisar `git status` / `git diff` / estilo de `git log`.
2. Si hay cambios lógicos distintos y claros, hasta 2–3 commits; si no, uno solo.
3. Stage **explícito** de archivos (evitar `git add -A` / `git add .` a ciegas).
4. Commit con HEREDOC:

```bash
git commit -m "$(cat <<'EOF'
tipo(scope): resumen en español

EOF
)"
```

Tipos habituales: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `style`, `perf`. Preferir `fix` si es arreglo; `feat` solo si aporta capacidad nueva.

Si el hook de pre-commit falla: corregir, **nuevo** commit (no amend salvo protocolo).

## Paso 2 — Push

```bash
git push -u origin HEAD
```

Reconfirmar rama con `git branch --show-current` justo antes. Nunca push a la rama por defecto desde este flujo.

## Paso 3 — Pull Request

Si ya hay PR abierta para esta rama (`gh pr list --head …`): reutilizar esa URL; no crear duplicado. Actualizar título/cuerpo solo si aporta.

Si no hay PR:

```bash
gh pr create --title "tipo(scope): resumen" --body "$(cat <<'EOF'
## Summary
- …

## Test plan
- [ ] …

EOF
)"
```

Título alineado al commit principal / conventional commits. Body en español o bilingüe breve; sin branding de Cursor/IA.

Devolver la URL de la PR.

## Paso 4 — Merge

Estrategia por defecto: **squash** + borrar rama remota:

```bash
gh pr merge --squash --delete-branch
```

- Si GitHub exige checks y aún no están verdes: usar `gh pr merge --squash --delete-branch --auto` y reportar que queda en auto-merge; **no** forzar con `--admin` salvo petición explícita.
- Si el merge está bloqueado por reviews/CI: informar el bloqueo y parar (no inventar workarounds destructivos).
- No usar merge commit ni rebase merge salvo que el usuario lo pida.

## Paso 5 — Actualizar main local

```bash
git fetch origin
git checkout <base>   # normalmente main
git pull --ff-only origin <base>
```

Si la rama de feature sigue localmente:

```bash
git branch -d <feature-branch> 2>/dev/null || true
```

Si `-d` falla por commits no mergeados (raro tras squash), informar; no usar `-D` salvo petición.

Comprobar:

```bash
git status
git log --oneline -5
```

## Paso 6 — Informe final

Responder en español, conciso, con:

- Hash/mensaje del/los commit(s)
- URL de la PR y estado (merged / auto-merge pendiente)
- Rama actual local y si `main` está al día con `origin/main`
- Cualquier omisión (tests no ejecutados, CI pendiente, archivos excluidos)

## Criticidad / no hacer

- No cerrar features a medias (commit sin PR, PR sin merge, merge sin sync de main).
- No mergear en caliente si el diff incluye `.env` u otros secretos.
- No asumir que “pasar tests” es opcional si acabas de tocar lógica crítica: si el cambio es de código de app/tests y no se han pasado en la sesión, ejecutar `make test` (sin e2e) **antes** del push; si fallan, no mergear.
- Este skill **no** sustituye revisión humana en repos compartidos con required reviewers: si `gh pr merge` pide review, parar y decirlo.

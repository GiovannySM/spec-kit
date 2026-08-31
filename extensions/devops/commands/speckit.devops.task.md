---
name: speckit.devops.task
description: Create Task work items in Azure DevOps from the current feature's tasks.md, children of the spec's User Story.
compatibility: Requires spec-kit project structure with .specify/ directory
metadata:
  author: spec-kit-core
  source: extension:devops
---

# Devops Task Skill (por task de tasks.md)

Crea **Tasks en Azure DevOps a partir de `tasks.md`** de la feature actual, como
hijas de la **User Story** de esta spec (`ado_user_story_id` en feature.json).

> Jerarquía: **Feature raíz (proyecto) → User Story (por spec) → Task (por task de tasks.md)**.
> Cada task de tasks.md ⇒ UN Task work item; se ejecuta en el hook `after_tasks`.

## User Input

```text
$ARGUMENTS
```

- Vacío (flujo automático): usa `ado_user_story_id` de feature.json.
- Con ID numérico: úsalo como parent (overrides). Con múltiples IDs separados por
  coma, distribuye las tasks por fase/grupo en orden — aclara el mapeo si es ambiguo.

## Step 1 — Resolver feature.json y tasks.md

1. Lee `.specify/feature.json` → `FEATURE_DIR` (`feature_directory`),
   `ado_user_story_id`, `branch`.
2. `TASKS` = `{FEATURE_DIR}/tasks.md`. STOP si no existe: indicar ejecutar `/speckit-tasks` primero.
3. Captura `BRANCH`: `git rev-parse --abbrev-ref HEAD`.

## Step 2 — Validar remote ADO y User Story padre

1. `git config --get remote.origin.url` → solo ADO; extrae `{org}` y `{project}`.
2. Si no hay `ado_user_story_id` ni ID por argumento: STOP, instruye ejecutar antes
   `/speckit.specify` (hook after_specify crea la US) o pasar el ID explícito.

## Step 3 — Campos ADO (config primero)

Defaults de `.specify/extensions/devops/local-config.yml` (`value_area`, `tags`;
overrides por argumento). El tipo `Task` NO exige `AcceptanceCriteria`; sí exige
`Value Area` (usa `BackEnd` o el default de local-config).

## Step 4 — Leer tasks.md y mapear

Extrae cada task de `tasks.md` en orden:

- **Título**: línea del checkbox (sin `- [ ] T###`), recortada a ~80 chars.
- **Grupo/fase**: encabezado de sección padre (Phase X / User Story N).
- **Detalles**: sub-bullets y hints.
- **Dependencias**: referencias "Depends on"/"Blocked by".

## Step 5 — Crear cada Task (en orden, sin saltar)

Para CADA task de tasks.md, crea un work item con parent = `ado_user_story_id`:

### Método 1 — Helper de la extensión (preferido)

```python
python .specify/extensions/devops/scripts/python/ado.py create-wi '{"type":"Task","title":"<TITULO>","description":"<DESC_HTML>","value_area":"BackEnd","tags":["backend","identity","branch:feature/001-slug"],"parent_id":<US_ID>}' 
```

*(repite por task; el helper añade la relación padre automaticamente)*

### Método 2 — REST directo

```
POST https://dev.azure.com/{org}/{project}/_apis/wit/workitems/$Task?api-version=7.1
Content-Type: application/json-patch+json

[
  {"op":"add","path":"/fields/System.Title","value":"<TITULO>"},
  {"op":"add","path":"/fields/System.Description","value":"<DESC_HTML>"},
  {"op":"add","path":"/fields/Microsoft.VSTS.Common.ValueArea","value":"BackEnd"},
  {"op":"add","path":"/fields/System.Tags","value":"backend;identity;branch:feature/001-slug"},
  {"op":"add","path":"/relations/-","value":{"rel":"System.LinkTypes.Hierarchy-Reverse","url":"https://dev.azure.com/{org}/_apis/wit/workItems/{US_ID}"}}
]
```

Notas técnicas (errores conocidos):
- URL del tipo: `Task` sin conflicto de encoding (`$Task` → `%24Task`).
- NO enviar `System.AreaPath` custom (TF401347).
- `az devops invoke` con route `$type` falla (KeyError): no usar; helper o REST directo.
- El tipo Task del proceso puede requerir `Microsoft.VSTS.Scheduling.RemainingWork`
  u otros según reglas: si algún campo obligatorio falla (TF401320), consulta
  `GET /_apis/wit/workitemtypes/Task/fields?api-version=7.1` con `alwaysRequired=true`
  y popúlalo (0.5d default es razonable).

## Step 6 — Reportar

```
✅ {n} Tasks creadas en {org}/{project} — parent User Story #{us_id} (branch {BRANCH})

{fase | grupo}
  • #{id} — {título}
  • #{id} — {título}
  ...

Fallos (si los hay):
  ⚠️ {título} — {motivo}
```

Persistencia: guarda el listado de task IDs creados en
`.specify/feature.json` bajo `"ado_task_ids": [...]` (merge; no sobreescribe claves existentes).
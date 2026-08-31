---
name: speckit.devops.user-story
description: Create ONE User Story work item in Azure DevOps for the current spec, child of the root Feature, linked to its Git feature branch.
compatibility: Requires spec-kit project structure with .specify/ directory
metadata:
  author: spec-kit-core
  source: extension:devops
---

# Devops User Story Skill (por spec)

Crea **UNA User Story en Azure DevOps por cada especificación** (`spec.md` de la
feature actual), como hija de la **Feature raíz** del proyecto, y **vincula la
feature branch de Git** (tag + comentario) para trazabilidad completa.

> Jerarquía: **Feature raíz (proyecto) → User Story (ESTA spec) → Task (por task de tasks.md)**.
> Se ejecuta automáticamente en el hook `after_specify`, cuando la rama
> `feature/NNN-slug` ya existe (creada por el hook `before_specify` de git).

## User Input

```text
$ARGUMENTS
```

`$ARGUMENTS` puede ser vacío (flujo automático del hook) o contener el ID de una
User Story existente para adoptarla como la US de esta spec.

## Step 1 — Resolver feature.json y spec

1. Lee `.specify/feature.json`. Si ya existe `ado_user_story_id`, verifica en ADO
   (`GET /{project}/_apis/wit/workitems/{id}?api-version=7.1`) que exista y sea
   tipo `User Story`; si existe, reporta `✓ User Story #{id} ya existe (nada por hacer)` y TERMINA.
2. Deriva rutas: `FEATURE_DIR` = `feature_directory` de feature.json; `FEATURE_SPEC` =
   `{FEATURE_DIR}/spec.md`. STOP con error si no existe la spec.
3. Captura `BRANCH` actual: `git rev-parse --abbrev-ref HEAD`.
   Registra la branch aunque no siga el patrón (warning), pero NO bloquees si el
   flujo lo permite.

## Step 2 — Feature raíz obligatoria

Lee `.specify/feature.json` → `ado_feature_id`. Si no existe, ejecuta primero el
skill `speckit-devops-feature` y continúa con el ID obtenido. Verifica que el WI
exista y sea tipo `Feature`. Si el usuario pasó un ID como argumento, ese manda.

## Step 3 — Validar remote ADO

`git config --get remote.origin.url` → formatos HTTPS/legacy/SSH de `dev.azure.com`.
SOLO continuar si es ADO; extrae `{org}` y `{project}`. Bajo ninguna circunstancia
crear work items en org/proyecto distintos.

## Step 4 — Campos ADO (config primero)

Lee `.specify/extensions/devops/local-config.yml` para defaults (`value_area`,
`tags`, `version`, `company_id`); los argumentos nombrados tienen precedencia.

> [!IMPORTANT]
> El picklist `Value Area` NO acepta `Business`/`Architectural`. Válidos:
> `Architecture | BackEnd | DevOps | FrontEnd | Infrastructure`
> (descúbrelos con `GET /_apis/wit/workitemtypes/User+Story/fields/Microsoft.VSTS.Common.ValueArea?$expand=allowedValues`).

## Step 5 — Leer spec y construir contenido de la US

De `spec.md`:

- **Título US**: encabezado `# Feature Specification: ...` sin el prefijo (máx ~80 chars).
- **Descripción (HTML)**: 1 párrafo del objetivo + lista compacta de las user
  stories internas (P1/P2/P3) + back-reference.
- **Acceptance Criteria (HTML)**: los **Success Criteria** de la spec como lista
  (`<ul><li>SC-001: ...</li></ul>`) — el tipo `User Story` del proceso exige este
  campo (Required, InvalidEmpty).

Back-reference obligatorio:

```
🔗 Spec Kit Back-Reference
Branch: {BRANCH}
Source: specs/{NNN}-{slug}/spec.md
Parent Feature: #{ado_feature_id}
```

## Step 6 — Crear la User Story y vincular

> [!CAUTION]
> NUNCA crear work items fuera del org/proyecto del remote detectado.

### Método 1 — Helper del proyecto (preferido)

```python
python .tmp/ado.py create-wi '{"type":"User Story","title":"<TITULO>","description":"<DESC_HTML>","value_area":"BackEnd","tags":["backend","identity","branch:feature/001-slug"],"acceptance_criteria":"<AC_HTML>","priority":2,"parent_id":<FEATURE_ID>}'
```

El helper resuelve token az, JSON-Patch, añade la relación padre (Hierarchy-Reverse)
y valida el picklist Value Area.

### Método 2 — REST directo

```
POST https://dev.azure.com/{org}/{project}/_apis/wit/workitems/$User+Story?api-version=7.1
Content-Type: application/json-patch+json

[
  {"op":"add","path":"/fields/System.Title","value":"<TITULO>"},
  {"op":"add","path":"/fields/System.Description","value":"<DESC_HTML>"},
  {"op":"add","path":"/fields/Microsoft.VSTS.Common.AcceptanceCriteria","value":"<AC_HTML>"},
  {"op":"add","path":"/fields/Microsoft.VSTS.Common.ValueArea","value":"BackEnd"},
  {"op":"add","path":"/fields/System.Tags","value":"backend;identity;branch:feature/001-slug"},
  {"op":"add","path":"/fields/Microsoft.VSTS.Common.Priority","value":2},
  {"op":"add","path":"/relations/-","value":{"rel":"System.LinkTypes.Hierarchy-Reverse","url":"https://dev.azure.com/{org}/_apis/wit/workItems/{FEATURE_ID}"}}
]
```

Notas técnicas (errores conocidos):
- `$User Story` debe urlencodearse: `%24User+Story` (espacio +).
- NO enviar `System.AreaPath` custom (TF401347): área default del proyecto.
- Prioridad: P1→1, P2→2, P3→3, sin marca → 2.

## Step 7 — Comentario de trazabilidad en el work item

Añade comentario con la branch y referencias (el helper `.tmp/ado.py` lo hace
explícito solo si se implementa; si no, REST `POST /_apis/wit/workitems/{id}/comments?api-version=7.1-preview.3`):

```
🌿 Git branch: {BRANCH}
📄 Spec: specs/{NNN}-{slug}/spec.md
🌳 Parent: Feature #{feature_id}
```

## Step 8 — Persistir y reportar

1. `.specify/feature.json` (merge): `{ "ado_user_story_id": <id>, "branch": "<BRANCH>" }`
2. Reporta:

```
✅ User Story #{id} — {title}
   https://dev.azure.com/{org}/{project}/_workitems/edit/{id}

Parent: Feature #{feature_id} | Git branch: {BRANCH} (vinculada por tag + comentario)
Next: /speckit.tasks generará las Tasks hijas (hook after_tasks).
```
---
name: speckit.devops.feature
description: Ensure the project-level root Feature work item exists in Azure DevOps (one per project; not per spec).
compatibility: Requires spec-kit project structure with .specify/ directory
metadata:
  author: spec-kit-core
  source: extension:devops
---

# Devops Root Feature Skill (project-level)

Asegura la existencia del **Feature work item raíz del proyecto** en Azure DevOps
(uno por repo, no por spec). El ID se persiste en `.specify/feature.json`
(`ado_feature_id`) para que los hooks posteriores (`speckit-devops-user-story`,
`speckit-devops-task`) lo consuman.

> Jerarquía objetivo: **Feature raíz (proyecto) → User Story (por spec) → Task (por task)**.

## User Input

```text
$ARGUMENTS
```

Si el usuario pasa un ID numérico de Feature existente, ÚSALO como raíz (no crear nueva).

## Step 1 — Idempotencia: ¿ya existe la Feature raíz?

1. Lee `.specify/feature.json`. Si ya contiene `ado_feature_id`, **verifica** con
   `GET {org}/{project}/_apis/wit/workitems/{id}?api-version=7.1` que exista y sea
   de tipo `Feature`. Si existe: reporta `✓ Root Feature #{id} ya existe` y TERMINA.
2. Si el usuario pasó un ID numérico como argumento, adóptalo como raíz (verifica tipo Feature), persiste y termina.

## Step 2 — Validar remote ADO

```bash
git config --get remote.origin.url
```

Formatos soportados (HTTPS, legacy HTTPS, SSH `dev.azure.com:v3`). SOLO continúa si
el remote es ADO; extrae `{org}` y `{project}`. NUNCA crear work items fuera del
remote detectado.

## Step 3 — Campos ADO (config primero, prompt solo si falta)

Lee `.specify/extensions/devops/local-config.yml` para valores por defecto
(`value_area`, `company_id`, `tags`, `version`). Los argumentos nombrados
(`--value-area`, `--tags`, `--company-id`, `--version`) tienen precedencia.

> [!IMPORTANT]
> El picklist `Value Area` de este proceso NO acepta `Business`/`Architectural`.
> Valores válidos (proceso IngeoVisualServicesSASAgile): `Architecture`, `BackEnd`,
> `DevOps`, `FrontEnd`, `Infrastructure`. Lista real obtenible con:
> `GET /_apis/wit/workitemtypes/Feature/fields/Microsoft.VSTS.Common.ValueArea?$expand=allowedValues`
> (único endpoint que la expone; ni a nivel org ni de proceso).

Si falta algún valor sin config ni argumentos, muéstralo y espera respuesta.

## Step 4 — Título y descripción de la Feature raíz

- **Título**: derivado del repo/servicio (p. ej. `ivs.oryon.srv.identity` → `Ivs.Oryon.Identity`), o el que el usuario pase.
- **Descripción**: propósito del servicio (README o input del usuario) + back-reference:

```
---
🔗 Spec Kit Root Feature (project-level)
Repository: {repo}
Config: .specify/extensions/devops/local-config.yml
```

> [!CAUTION]
> UNDER NO CIRCUMSTANCES CREATE WORK ITEMS IN ORGANIZATIONS OR PROJECTS THAT DO NOT MATCH THE DETECTED REMOTE.

## Step 5 — Crear el work item (REST directo, MCP si está disponible)

> [!NOTE]
> `az boards work-item create` falla con `Value Area` en este proceso; usa REST
> JSON-Patch directo, o el helper `.tmp/ado.py` si existe.

### Método 1 — Helper del proyecto (preferido)

```python
python .tmp/ado.py create-wi '{"type":"Feature","title":"<TITULO>","description":"<DESC_HTML>","value_area":"<VA>","tags":["backend","identity"],"acceptance_criteria":"<AC opcional>"}'
```

### Method 2 — REST directo

```
POST https://dev.azure.com/{org}/{project}/_apis/wit/workitems/$Feature?api-version=7.1
Content-Type: application/json-patch+json
Authorization: Bearer {az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798}

[
  {"op":"add","path":"/fields/System.Title","value":"<TITULO>"},
  {"op":"add","path":"/fields/System.Description","value":"<DESC>"},
  {"op":"add","path":"/fields/Microsoft.VSTS.Common.AcceptanceCriteria","value":"<AC>"},
  {"op":"add","path":"/fields/Microsoft.VSTS.Common.ValueArea","value":"BackEnd"},
  {"op":"add","path":"/fields/System.Tags","value":"backend;identity"}
]
```

> [!NOTE]
> - El tipo Feature exige `System.AcceptanceCriteria` (Required): SIEMPRE popúlalo.
> - NO envíes `System.AreaPath` custom (error TF401347): usa el área default.
> - `az devops invoke` falla con route param `$type` (KeyError 'type'): no lo uses.

## Step 6 — Persistir ID y reportar

1. Actualiza `.specify/feature.json` (merge, no overwrite):
   ```json
   { "ado_feature_id": <id> }
   ```
2. Reporta:

```
✅ Root Feature #{id} — {title}
   https://dev.azure.com/{org}/{project}/_workitems/edit/{id}

Next: cada /speckit.specify creará (hook after_specify) una User Story hija enlazada a esta Feature y a su feature branch de Git.
```


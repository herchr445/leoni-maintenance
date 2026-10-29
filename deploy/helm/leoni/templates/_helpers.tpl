{{/*
_helpers.tpl — Fonctions réutilisables par tous les templates du chart.
Les fichiers commençant par "_" ne produisent aucun manifeste : ils ne
contiennent que des définitions ("define") appelées avec "include".
*/}}

{{/*
Nom de l'application (nom du chart, surchargeable par nameOverride).
Tronqué à 63 caractères : limite des noms et labels Kubernetes.
*/}}
{{- define "leoni.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Nom complet = préfixe de toutes les ressources (ex. "leoni" → leoni-backend).
Si le nom de la release contient déjà le nom du chart, on ne le répète pas.
*/}}
{{- define "leoni.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Label helm.sh/chart : nom et version du chart qui a créé la ressource.
*/}}
{{- define "leoni.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Labels de SÉLECTION (immuables après création d'un Deployment/StatefulSet) :
uniquement des valeurs stables. Paramètres : dict "context" (.) et "component".
*/}}
{{- define "leoni.selectorLabels" -}}
app.kubernetes.io/name: {{ include "leoni.name" .context }}
app.kubernetes.io/instance: {{ .context.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{/*
Labels STANDARD (recommandés par Kubernetes) posés sur chaque ressource.
Paramètres : dict "context" (.), "component" et, optionnellement, "version"
(tag d'image du composant = version réellement déployée).
*/}}
{{- define "leoni.labels" -}}
helm.sh/chart: {{ include "leoni.chart" .context }}
{{ include "leoni.selectorLabels" . }}
app.kubernetes.io/part-of: leoni-maintenance
app.kubernetes.io/managed-by: {{ .context.Release.Service }}
{{- with .version }}
app.kubernetes.io/version: {{ . | toString | quote }}
{{- end }}
{{- end -}}

{{/*
Référence d'image "dépôt:tag" avec garde-fous :
- tag obligatoire (échec explicite du rendu s'il est vide) ;
- "latest" interdit : Kubernetes doit déployer une version précise et immuable.
Paramètres : dict "image" (bloc image des values) et "component" (pour le message).
*/}}
{{- define "leoni.image" -}}
{{- $tag := required (printf "%s.image.tag is required (git short SHA of the image)" .component) .image.tag | toString -}}
{{- if eq $tag "latest" -}}
{{- fail (printf "%s.image.tag must not be 'latest' (use the git short SHA)" .component) -}}
{{- end -}}
{{- printf "%s:%s" .image.repository $tag -}}
{{- end -}}

{{/*
Garde-fou de l'arrêt propre : le délai preStop doit être STRICTEMENT inférieur
au délai de grâce, sinon Kubernetes tuerait le conteneur (SIGKILL) pendant
l'attente, avant même l'arrêt normal de l'application.
Paramètres : dict "values" (bloc backend ou frontend) et "component".
*/}}
{{- define "leoni.checkGracePeriod" -}}
{{- if ge (int .values.preStopSleepSeconds) (int .values.terminationGracePeriodSeconds) -}}
{{- fail (printf "%s.preStopSleepSeconds (%v) must be lower than %s.terminationGracePeriodSeconds (%v)" .component .values.preStopSleepSeconds .component .values.terminationGracePeriodSeconds) -}}
{{- end -}}
{{- end -}}

{{/* Noms des Services, réutilisés par l'Ingress, le backend et NOTES.txt */}}
{{- define "leoni.backend.fullname" -}}
{{- printf "%s-backend" (include "leoni.fullname" .) -}}
{{- end -}}

{{- define "leoni.frontend.fullname" -}}
{{- printf "%s-frontend" (include "leoni.fullname" .) -}}
{{- end -}}

{{- define "leoni.postgres.fullname" -}}
{{- printf "%s-postgres" (include "leoni.fullname" .) -}}
{{- end -}}

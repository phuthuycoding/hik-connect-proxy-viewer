{{/*
Expand the name of the chart.
*/}}
{{- define "hcpv.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "hcpv.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "hcpv.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "hcpv.labels" -}}
helm.sh/chart: {{ include "hcpv.chart" . }}
{{ include "hcpv.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels (a component label is added per Deployment/Service)
*/}}
{{- define "hcpv.selectorLabels" -}}
app.kubernetes.io/name: {{ include "hcpv.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Resource names of the two components
*/}}
{{- define "hcpv.streamName" -}}
{{- printf "%s-stream" (include "hcpv.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "hcpv.webName" -}}
{{- printf "%s-web" (include "hcpv.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "hcpv.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "hcpv.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

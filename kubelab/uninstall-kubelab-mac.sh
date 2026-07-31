#!/usr/bin/env bash
#
# uninstall-kubelab-mac.sh
#
# install-kubelab-mac.sh 로 구성한 kind 클러스터 + colima VM (+ brew 도구) 을 정리하는 스크립트.
# - kind 클러스터 삭제 (Istio, metrics-server 등 클러스터 내부 리소스는 클러스터 삭제로 함께 제거됨)
# - colima 는 기본적으로 정지(stop)만 하며, --purge 옵션을 주면 VM 자체를 삭제(delete)
# - --remove-tools 옵션을 주면 install-kubelab-mac.sh 가 brew 로 설치했던
#   colima/docker/kind/kubectl/kubectx/istioctl/k9s 까지 전부 삭제 (재설치 전제)
#
# Usage:
#   ./uninstall-kubelab-mac.sh [-n|--name <cluster-name>] [--purge] [--remove-tools] [-y|--yes]
#
set -euo pipefail

CLUSTER_NAME="kubelab"
COLIMA_PROFILE="${CLUSTER_NAME}"
PURGE=false
REMOVE_TOOLS=false
ASSUME_YES=false

# install-kubelab-mac.sh 에서 brew 로 설치하는 도구 목록과 동일.
# brew 에서 kubectl 은 실제로는 kubernetes-cli formula 의 별칭(alias)이라
# `brew list --formula` 에는 kubernetes-cli 로 나오므로 그 이름을 사용한다.
BREW_FORMULAS=(colima docker kind kubernetes-cli kubectx istioctl k9s)

log()  { printf '\033[1;32m[INFO]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[WARN]\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; }
die()  { err "$*"; exit 1; }

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

  -n, --name <name>   kind 클러스터 이름 (기본값: ${CLUSTER_NAME})
      --purge          colima VM 을 정지가 아닌 완전 삭제(colima delete)
      --remove-tools   brew 로 설치했던 CLI 도구까지 전부 삭제 (colima 는 자동으로 완전 삭제 처리)
                        대상: ${BREW_FORMULAS[*]} (kubernetes-cli = kubectl)
  -y, --yes            확인 프롬프트 없이 바로 진행
  -h, --help           도움말 출력

기본 동작: kind 클러스터 삭제 + colima VM 정지(재사용 가능하도록 VM 은 남겨둠)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--name)
      [[ $# -ge 2 ]] || die "$1 옵션에는 값이 필요합니다."
      CLUSTER_NAME="$2"; COLIMA_PROFILE="$2"; shift 2 ;;
    --purge)
      PURGE=true; shift ;;
    --remove-tools)
      REMOVE_TOOLS=true; shift ;;
    -y|--yes)
      ASSUME_YES=true; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      err "알 수 없는 옵션: $1"; usage; exit 1 ;;
  esac
done

[[ "$(uname -s)" == "Darwin" ]] || die "이 스크립트는 macOS 전용입니다."

# 도구까지 지울 거면 정지된 VM 을 남겨둘 이유가 없으므로 colima 는 완전 삭제로 강제한다.
if [[ "${REMOVE_TOOLS}" == true ]]; then
  PURGE=true
fi

log "다음 작업을 수행합니다:"
echo "  - kind 클러스터 삭제: ${CLUSTER_NAME}"
if [[ "${PURGE}" == true ]]; then
  echo "  - colima VM 완전 삭제(purge): ${COLIMA_PROFILE}"
else
  echo "  - colima VM 정지(stop, VM 은 유지): ${COLIMA_PROFILE}"
fi
if [[ "${REMOVE_TOOLS}" == true ]]; then
  echo "  - brew 도구 삭제: ${BREW_FORMULAS[*]}"
fi

if [[ "${ASSUME_YES}" != true ]]; then
  read -r -p "계속 진행하시겠습니까? [y/N] " reply
  case "${reply}" in
    y|Y|yes|YES) ;;
    *) log "취소되었습니다."; exit 0 ;;
  esac
fi

if command -v kind >/dev/null 2>&1 && kind get clusters 2>/dev/null | grep -qx "${CLUSTER_NAME}"; then
  log "kind 클러스터 '${CLUSTER_NAME}' 삭제 중..."
  kind delete cluster --name "${CLUSTER_NAME}"
else
  warn "kind 클러스터 '${CLUSTER_NAME}' 를 찾을 수 없어 건너뜁니다."
fi

if command -v colima >/dev/null 2>&1 && colima status "${COLIMA_PROFILE}" >/dev/null 2>&1; then
  if [[ "${PURGE}" == true ]]; then
    log "colima(profile=${COLIMA_PROFILE}) 완전 삭제 중..."
    colima delete "${COLIMA_PROFILE}" -f
  else
    log "colima(profile=${COLIMA_PROFILE}) 정지 중..."
    colima stop "${COLIMA_PROFILE}"
  fi
else
  warn "colima(profile=${COLIMA_PROFILE}) 가 실행 중이 아니거나 존재하지 않아 건너뜁니다."
fi

if [[ "${REMOVE_TOOLS}" == true ]]; then
  if ! command -v brew >/dev/null 2>&1; then
    warn "brew 가 없어 도구 삭제를 건너뜁니다."
  else
    log "brew 로 설치된 도구를 삭제합니다."
    for formula in "${BREW_FORMULAS[@]}"; do
      if brew list --formula 2>/dev/null | grep -qx "${formula}"; then
        log "brew uninstall ${formula}"
        brew uninstall "${formula}"
      else
        warn "'${formula}' 은(는) brew로 설치되어 있지 않아 건너뜁니다."
      fi
    done
  fi
fi

log "정리가 완료되었습니다."

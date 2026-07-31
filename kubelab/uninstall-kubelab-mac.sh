#!/usr/bin/env bash
#
# uninstall-kubelab-mac.sh
#
# install-kubelab-mac.sh 로 구성한 kind 클러스터 + colima VM (+ brew 도구) 을 정리하는 스크립트.
# - kind 클러스터 삭제 (Istio, metrics-server 등 클러스터 내부 리소스는 클러스터 삭제로 함께 제거됨)
# - colima 는 기본적으로 정지(stop)만 하며, --purge 옵션을 주면 VM 자체를 삭제(delete)
# - --remove-tools 옵션을 주면 install-kubelab-mac.sh 가 brew 로 설치했던
#   colima/docker/kind/kubectl/kubectx/istioctl/k9s/mkcert 까지 전부 삭제 (재설치 전제)
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
BREW_FORMULAS=(colima docker kind kubernetes-cli kubectx istioctl k9s mkcert)

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

# 정리 스크립트는 한 단계가 실패해도 나머지 단계를 계속 시도해야 하므로,
# 아래 명령들은 실패해도 set -e 로 스크립트 전체가 죽지 않도록 || 로 받아준다.

if command -v kind >/dev/null 2>&1 && kind get clusters 2>/dev/null | grep -qx "${CLUSTER_NAME}"; then
  log "kind 클러스터 '${CLUSTER_NAME}' 삭제 중..."
  kind delete cluster --name "${CLUSTER_NAME}" || warn "kind 클러스터 삭제 실패 (계속 진행합니다)"
else
  warn "kind 클러스터 '${CLUSTER_NAME}' 를 찾을 수 없어 건너뜁니다."
fi

if command -v colima >/dev/null 2>&1 && colima status "${COLIMA_PROFILE}" >/dev/null 2>&1; then
  if [[ "${PURGE}" == true ]]; then
    log "colima(profile=${COLIMA_PROFILE}) 완전 삭제 중..."
    colima delete "${COLIMA_PROFILE}" -f || warn "colima 삭제 실패 (계속 진행합니다)"
  else
    log "colima(profile=${COLIMA_PROFILE}) 정지 중..."
    colima stop "${COLIMA_PROFILE}" || warn "colima 정지 실패 (계속 진행합니다)"
  fi
else
  warn "colima(profile=${COLIMA_PROFILE}) 가 실행 중이 아니거나 존재하지 않아 건너뜁니다."
fi

if [[ "${REMOVE_TOOLS}" == true ]]; then
  if command -v mkcert >/dev/null 2>&1; then
    log "mkcert 로 등록했던 로컬 신뢰 루트 CA(맥 키체인)를 제거합니다."
    mkcert -uninstall || warn "mkcert -uninstall 실패 (계속 진행합니다)"
  fi

  if ! command -v brew >/dev/null 2>&1; then
    warn "brew 가 없어 도구 삭제를 건너뜁니다."
  else
    log "brew 로 설치된 도구를 삭제합니다."
    # `brew list --formula` 는 항목이 여러 개면 ls 처럼 한 줄에 여러 이름을
    # 컬럼으로 묶어서 출력하기도 한다. grep -qx(줄 전체 일치)가 그러면 못 찾으므로
    # tr 로 공백까지 개행으로 쪼개서 이름 하나당 한 줄이 되도록 정규화한다.
    for formula in "${BREW_FORMULAS[@]}"; do
      if brew list --formula 2>/dev/null | tr -s ' \t' '\n' | grep -qx "${formula}"; then
        log "brew uninstall ${formula}"
        brew uninstall "${formula}" || warn "'${formula}' 삭제 실패 (계속 진행합니다)"
      else
        warn "'${formula}' 은(는) brew로 설치되어 있지 않아 건너뜁니다."
      fi
    done
  fi
fi

log "정리가 완료되었습니다."

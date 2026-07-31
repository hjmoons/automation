#!/usr/bin/env bash
#
# install-kubelab-mac.sh
#
# Mac 에서 colima + kind 기반 kubernetes 학습/실습 환경(kubelab)을 처음부터 구성하는 자동화 스크립트.
# - colima / kind / kubectl / kubens(kubectx) / istioctl / k9s 이 없으면 brew 로 최신 버전 설치
# - colima VM 을 지정한 CPU/메모리로 기동
# - kind 클러스터를 아래 PINNED_K8S_VERSION 에 고정된 kubernetes 버전으로 생성하고
#   80, 443(+추가 옵션 포트)을 호스트에 매핑
#   (새 kubernetes/kind 버전이 나오면 이 스크립트 상단의 PINNED_K8S_VERSION /
#    PINNED_KIND_NODE_IMAGE 값만 사람이 직접 갱신해서 관리한다. 자동으로 매번
#    최신을 따라가지 않는 이유는 재현성 때문 — 몇 달 뒤 재실행해도 동일한 버전이
#    뜨도록 고정한다)
#   kubectl 은 kube-apiserver/kubelet 과 minor 버전 ±1 이내까지는 공식 지원 범위라,
#   brew 의 최신 kubectl 과 PINNED_K8S_VERSION 사이의 스큐는 그 범위 안에서는 문제없다.
#   PINNED_K8S_VERSION 을 너무 오래 방치하면 범위를 벗어날 수 있으니 가끔 갱신할 것.
# - kubectl 컨텍스트를 자동으로 kind 클러스터로 연결
# - nginx ingress controller 는 EOL 이므로 Istio ingress gateway(Envoy)를 설치하고
#   Gateway 리소스로 80/443(+추가 포트)를 노출
#
# Usage:
#   ./install-kubelab-mac.sh [-c|--cpu <num>] [-m|--memory <GB>] [-p|--port <port>]... [-n|--name <cluster-name>] [-k|--k8s-version <x.y.z>]
#
# Example:
#   ./install-kubelab-mac.sh --cpu 6 --memory 12 --port 8080 --port 9000
#
set -euo pipefail

# ---------------------------------------------------------------------------
# 고정 버전 (새 kind/kubernetes 릴리스가 나오면 여기만 갱신)
#
# 2026-07-31 기준 kind v0.32.0 의 기본/권장 노드 이미지.
# digest 까지 포함해야 해당 kind 릴리스에서 실제로 빌드한 이미지임이 보장된다.
# (kind 릴리스노트: https://github.com/kubernetes-sigs/kind/releases/tag/v0.32.0)
# ---------------------------------------------------------------------------
PINNED_K8S_VERSION="1.36.1"
PINNED_KIND_NODE_IMAGE="kindest/node:v1.36.1@sha256:3489c7674813ba5d8b1a9977baea8a6e553784dab7b84759d1014dbd78f7ebd5"

# ---------------------------------------------------------------------------
# 기본값
# ---------------------------------------------------------------------------
CLUSTER_NAME="kubelab"
COLIMA_PROFILE="${CLUSTER_NAME}"
COLIMA_CPU=4
COLIMA_MEMORY=8
EXTRA_PORTS=()
K8S_VERSION=""   # -k/--k8s-version 로 지정 안 하면 PINNED_K8S_VERSION 사용

# ---------------------------------------------------------------------------
# 로그 헬퍼
# ---------------------------------------------------------------------------
log()  { printf '\033[1;32m[INFO]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[WARN]\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; }
die()  { err "$*"; exit 1; }

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

  -c, --cpu <num>       colima VM 에 할당할 CPU 코어 수 (기본값: ${COLIMA_CPU})
  -m, --memory <num>    colima VM 에 할당할 메모리(GB) (기본값: ${COLIMA_MEMORY})
  -p, --port <port>     Istio Gateway 에 추가로 열어줄 포트 (여러 번 지정 가능)
  -n, --name <name>     kind 클러스터 이름 (기본값: ${CLUSTER_NAME})
  -k, --k8s-version <x.y.z>
                         kind 클러스터의 kubernetes 버전 직접 지정 (기본값: PINNED_K8S_VERSION=${PINNED_K8S_VERSION})
  -h, --help            도움말 출력

기본적으로 80, 443 포트는 항상 열립니다.
kind 클러스터는 스크립트 상단에 고정해 둔 PINNED_K8S_VERSION(v${PINNED_K8S_VERSION})으로 생성되며,
kubectl 은 다른 도구들과 동일하게 brew 로 설치됩니다 (kube-apiserver/kubelet 과
minor 버전 ±1 이내까지는 공식 지원 범위라 patch 버전까지 맞출 필요는 없음).
새 kubernetes/kind 버전이 나오면 스크립트 상단의 PINNED_K8S_VERSION /
PINNED_KIND_NODE_IMAGE 값을 직접 갱신해서 관리하세요.
EOF
}

# ---------------------------------------------------------------------------
# 옵션 파싱
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    -c|--cpu)
      [[ $# -ge 2 ]] || die "$1 옵션에는 값이 필요합니다."
      COLIMA_CPU="$2"; shift 2 ;;
    -m|--memory)
      [[ $# -ge 2 ]] || die "$1 옵션에는 값이 필요합니다."
      COLIMA_MEMORY="$2"; shift 2 ;;
    -p|--port)
      [[ $# -ge 2 ]] || die "$1 옵션에는 값이 필요합니다."
      EXTRA_PORTS+=("$2"); shift 2 ;;
    -n|--name)
      [[ $# -ge 2 ]] || die "$1 옵션에는 값이 필요합니다."
      CLUSTER_NAME="$2"; COLIMA_PROFILE="$2"; shift 2 ;;
    -k|--k8s-version)
      [[ $# -ge 2 ]] || die "$1 옵션에는 값이 필요합니다."
      K8S_VERSION="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      err "알 수 없는 옵션: $1"; usage; exit 1 ;;
  esac
done

[[ "$COLIMA_CPU" =~ ^[0-9]+$ ]] || die "--cpu 값은 숫자여야 합니다: ${COLIMA_CPU}"
[[ "$COLIMA_MEMORY" =~ ^[0-9]+$ ]] || die "--memory 값은 숫자여야 합니다: ${COLIMA_MEMORY}"
for p in "${EXTRA_PORTS[@]:-}"; do
  [[ -z "$p" ]] && continue
  [[ "$p" =~ ^[0-9]+$ ]] || die "--port 값은 숫자여야 합니다: ${p}"
done
if [[ -n "${K8S_VERSION}" ]]; then
  [[ "$K8S_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "--k8s-version 값은 x.y.z 형식이어야 합니다: ${K8S_VERSION}"
  KIND_NODE_IMAGE="kindest/node:v${K8S_VERSION}"
else
  K8S_VERSION="${PINNED_K8S_VERSION}"
  KIND_NODE_IMAGE="${PINNED_KIND_NODE_IMAGE}"
fi

# ---------------------------------------------------------------------------
# 사전 조건 확인
# ---------------------------------------------------------------------------
[[ "$(uname -s)" == "Darwin" ]] || die "이 스크립트는 macOS 전용입니다."

ensure_homebrew() {
  if ! command -v brew >/dev/null 2>&1; then
    log "Homebrew 가 설치되어 있지 않아 설치를 진행합니다."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    if [[ -x /opt/homebrew/bin/brew ]]; then
      eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [[ -x /usr/local/bin/brew ]]; then
      eval "$(/usr/local/bin/brew shellenv)"
    fi
  else
    log "Homebrew 확인됨: $(brew --version | head -n1)"
  fi
}

# command_name / brew formula 이름이 다른 경우가 있어 둘 다 받는다.
ensure_cli() {
  local cmd="$1" formula="$2"
  if command -v "$cmd" >/dev/null 2>&1; then
    log "'${cmd}' 이미 설치되어 있음: $(command -v "$cmd")"
  else
    log "'${cmd}' 명령어가 없어 최신 버전으로 설치합니다. (brew install ${formula})"
    brew install "${formula}"
  fi
}

# ---------------------------------------------------------------------------
# colima 기동
# ---------------------------------------------------------------------------
start_colima() {
  if colima status "${COLIMA_PROFILE}" >/dev/null 2>&1; then
    log "colima(profile=${COLIMA_PROFILE}) 이미 실행 중입니다. CPU/메모리 옵션을 바꾸려면 먼저 'colima stop ${COLIMA_PROFILE}' 후 다시 실행하세요."
  else
    log "colima 를 CPU=${COLIMA_CPU}, Memory=${COLIMA_MEMORY}GB 로 기동합니다."
    colima start "${COLIMA_PROFILE}" \
      --cpu "${COLIMA_CPU}" \
      --memory "${COLIMA_MEMORY}" \
      --runtime docker \
      --kubernetes=false
  fi
}

# ---------------------------------------------------------------------------
# kind 클러스터 생성 (80/443 + 추가 포트 매핑)
# ---------------------------------------------------------------------------
create_kind_cluster() {
  if kind get clusters 2>/dev/null | grep -qx "${CLUSTER_NAME}"; then
    log "kind 클러스터 '${CLUSTER_NAME}' 이미 존재합니다. 생성을 건너뜁니다."
    return
  fi

  log "kind 클러스터 '${CLUSTER_NAME}' 를 생성합니다. (포트: 80, 443${EXTRA_PORTS:+, ${EXTRA_PORTS[*]}}, image: ${KIND_NODE_IMAGE})"

  local kind_config
  kind_config="$(mktemp -t kind-config)"

  {
    cat <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  image: ${KIND_NODE_IMAGE}
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "ingress-ready=true"
  extraPortMappings:
  - containerPort: 80
    hostPort: 80
    protocol: TCP
  - containerPort: 443
    hostPort: 443
    protocol: TCP
EOF
    for p in "${EXTRA_PORTS[@]:-}"; do
      [[ -z "$p" ]] && continue
      cat <<EOF
  - containerPort: ${p}
    hostPort: ${p}
    protocol: TCP
EOF
    done
  } > "${kind_config}"

  kind create cluster --name "${CLUSTER_NAME}" --config "${kind_config}"
  rm -f "${kind_config}"
}

setup_kubeconfig() {
  log "kubectl 컨텍스트를 kind-${CLUSTER_NAME} 로 설정합니다."
  kind export kubeconfig --name "${CLUSTER_NAME}"
  kubectl config use-context "kind-${CLUSTER_NAME}"
  kubectl cluster-info --context "kind-${CLUSTER_NAME}"
}

# ---------------------------------------------------------------------------
# metrics-server 설치 (kubectl top, k9s 리소스 뷰 등에 필요)
# ---------------------------------------------------------------------------
install_metrics_server() {
  log "metrics-server 를 설치합니다."
  kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

  local current_args
  current_args="$(kubectl get deployment metrics-server -n kube-system -o jsonpath='{.spec.template.spec.containers[0].args}')"
  if [[ "${current_args}" != *"--kubelet-insecure-tls"* ]]; then
    log "kind 클러스터의 kubelet 인증서는 자체 서명이라 --kubelet-insecure-tls 옵션을 추가합니다."
    kubectl patch deployment metrics-server -n kube-system --type='json' \
      -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
  fi

  kubectl rollout status deployment/metrics-server -n kube-system --timeout=120s
}

# ---------------------------------------------------------------------------
# Istio 설치 (nginx ingress controller EOL 대응 -> Istio ingress gateway)
# ---------------------------------------------------------------------------
install_istio() {
  log "Istio(istiod + ingressgateway) 를 설치합니다."
  istioctl install --set profile=default -y

  log "istio-ingressgateway 가 kind 노드에서 80/443(+추가 포트)을 직접 사용할 수 있도록 hostNetwork 로 패치합니다."
  kubectl patch deployment istio-ingressgateway -n istio-system --type merge -p '{
    "spec": {
      "template": {
        "spec": {
          "hostNetwork": true,
          "dnsPolicy": "ClusterFirstWithHostNet",
          "nodeSelector": { "ingress-ready": "true" },
          "tolerations": [
            { "key": "node-role.kubernetes.io/control-plane", "operator": "Exists", "effect": "NoSchedule" }
          ]
        }
      }
    }
  }'

  kubectl rollout status deployment/istio-ingressgateway -n istio-system --timeout=180s
}

apply_gateway() {
  log "Istio Gateway 리소스를 생성합니다. (80, 443${EXTRA_PORTS:+, ${EXTRA_PORTS[*]}})"

  local gateway_yaml
  gateway_yaml="$(mktemp -t istio-gateway)"

  {
    cat <<'EOF'
apiVersion: networking.istio.io/v1
kind: Gateway
metadata:
  name: kubelab-gateway
  namespace: istio-system
spec:
  selector:
    istio: ingressgateway
  servers:
  - port:
      number: 80
      name: http
      protocol: HTTP
    hosts:
    - "*"
  - port:
      number: 443
      name: tls
      protocol: TLS
    tls:
      mode: PASSTHROUGH
    hosts:
    - "*"
EOF
    for p in "${EXTRA_PORTS[@]:-}"; do
      [[ -z "$p" ]] && continue
      cat <<EOF
  - port:
      number: ${p}
      name: tcp-${p}
      protocol: TCP
    hosts:
    - "*"
EOF
    done
  } > "${gateway_yaml}"

  kubectl apply -f "${gateway_yaml}"
  rm -f "${gateway_yaml}"
}

# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------
ensure_homebrew

ensure_cli colima colima
ensure_cli docker docker
ensure_cli kind kind
ensure_cli kubectl kubectl
ensure_cli kubens kubectx
ensure_cli istioctl istioctl
ensure_cli k9s k9s

start_colima
create_kind_cluster
setup_kubeconfig
install_metrics_server
install_istio
apply_gateway

cat <<EOF

--------------------------------------------------------------------
설치 완료

  클러스터 이름   : ${CLUSTER_NAME}
  kubectl 컨텍스트: kind-${CLUSTER_NAME}
  kubernetes 버전 : v${K8S_VERSION}
  colima 리소스   : CPU ${COLIMA_CPU} / Memory ${COLIMA_MEMORY}GB
  열린 포트       : 80, 443${EXTRA_PORTS:+, ${EXTRA_PORTS[*]}}

  확인 명령어:
    kubectl get nodes
    kubectl get pods -n istio-system
    kubectl get gateway -n istio-system
    kubectl top nodes
    kubectl top pods -A
    kubens
    k9s

  클러스터 삭제:
    kind delete cluster --name ${CLUSTER_NAME}
    colima stop ${COLIMA_PROFILE}
--------------------------------------------------------------------
EOF

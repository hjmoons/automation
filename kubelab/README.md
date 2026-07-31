# kubelab

Mac에 colima + kind 기반 kubernetes 학습/실습 환경을 설치/삭제하는 스크립트.

- `install-kubelab-mac.sh` — colima, kind, kubectl, kubens, istioctl, k9s 설치 → colima 기동 →
  kind 클러스터 생성 → kubectl 연결 → metrics-server 설치 → Istio(Gateway API 방식) 설치까지 한 번에 진행
- `uninstall-kubelab-mac.sh` — 위에서 만든 클러스터/VM/도구를 정리

둘 다 macOS 전용이며 [Homebrew](https://brew.sh)를 패키지 관리자로 사용합니다 (없으면 자동 설치).

## 설치: install-kubelab-mac.sh

```bash
./install-kubelab-mac.sh [options]
```

| 옵션 | 설명 | 기본값 |
|---|---|---|
| `-c, --cpu <num>` | colima VM에 할당할 CPU 코어 수 | 4 |
| `-m, --memory <num>` | colima VM에 할당할 메모리(GB) | 8 |
| `-p, --port <port>` | Gateway에 추가로 열어줄 포트 (여러 번 지정 가능) | - |
| `-n, --name <name>` | kind 클러스터 이름 | `kubelab` |
| `-k, --k8s-version <x.y.z>` | kind 클러스터의 kubernetes 버전 직접 지정 | 아래 "고정된 버전" 참고 |
| `-h, --help` | 도움말 출력 | - |

80, 443 포트는 옵션 없이도 항상 Gateway에 열립니다.

예시:
```bash
# 기본값(CPU 4, Memory 8GB)으로 설치
./install-kubelab-mac.sh

# 리소스와 추가 포트 지정
./install-kubelab-mac.sh --cpu 6 --memory 12 --port 8080 --port 9000

# 특정 kubernetes 버전으로 클러스터 생성
./install-kubelab-mac.sh --k8s-version 1.35.5
```

### 설치되는 것들

| 도구 | 용도 | 설치 방식 |
|---|---|---|
| colima | 컨테이너 런타임(VM) | brew (없을 때만) |
| docker | colima와 통신하는 CLI (Docker Desktop 아님) | brew (없을 때만) |
| kind | 로컬 kubernetes 클러스터 | brew (없을 때만) |
| kubectl | 클러스터 제어 CLI | brew (없을 때만) |
| kubens (kubectx) | 네임스페이스 전환 CLI | brew (없을 때만) |
| istioctl / Istio | 게이트웨이용 컨트롤플레인 (Envoy 프록시) | brew (없을 때만) |
| k9s | 클러스터 TUI 대시보드 | brew (없을 때만) |
| metrics-server | `kubectl top`, k9s 리소스 뷰용 메트릭 | 클러스터 내부에 매니페스트 적용 |

nginx ingress controller는 EOL이라 Istio를 대신 설치합니다. 다만 서비스 메시 전체(사이드카
자동 주입 등)가 필요한 게 아니라 게이트웨이 하나만 있으면 되므로 Kubernetes
[Gateway API](https://gateway-api.sigs.k8s.io/) 방식을 씁니다.

1. Gateway API CRD 설치 (experimental channel — 443 TLS passthrough, 임의 TCP 포트(`-p`)에
   필요한 TLSRoute/TCPRoute가 여기 포함됨)
2. Istio는 `profile=minimal`로 설치 — 컨트롤플레인(istiod)만 설치되고, 정적으로 떠 있는
   `istio-ingressgateway` 같은 건 없음
3. `istio-system` 네임스페이스에 `gatewayClassName: istio`인 Gateway 리소스
   (`kubelab-gateway`)를 적용하면, 그 즉시 Istio가 필요한 프록시 Deployment/Service를
   자동으로 만들어줌 → 이걸 hostNetwork로 패치해서 80/443(+추가 포트)을 kind 노드에 직접 노출

443은 게이트웨이가 인증서 없이 그냥 통과(Passthrough)시킵니다 — SNI(호스트명)만 보고
뒤로 흘려보낼 뿐, TLS 종료(=인증서)는 각 앱이 자기 파드 안에서 직접 처리합니다. 그래서
게이트웨이 쪽에는 인증서 관리가 전혀 없습니다.

즉 필요한 만큼만(게이트웨이 하나) 떠 있고, 별도 애드온이나 사이드카 주입, 중앙 인증서 관리
같은 것도 전혀 켜져 있지 않습니다.

### 앱 배포 시 사용법 (Gateway를 새로 만들지 마세요)

Gateway는 클러스터에 이미 하나(`kubelab-gateway`, `istio-system`) 떠 있고, 모든 네임스페이스의
Route가 거기 붙을 수 있도록 열려 있습니다(`allowedRoutes.namespaces.from: All`). 앱을 배포할 땐
Gateway를 새로 만들지 말고, **본인 네임스페이스에 Route만** 만들어서 기존 Gateway에 붙이면 됩니다.

- **HTTP(80)만 쓰는 앱** → `HTTPRoute` (호스트명/경로 기반 라우팅, 인증서 필요 없음)
- **HTTPS(443)를 쓰는 앱** → `TLSRoute` (SNI/호스트명 기반, 경로 라우팅은 불가. 인증서는
  게이트웨이가 아니라 앱 파드 자신이 직접 종료해야 함)

```yaml
# HTTP 예시
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: myapp-route
  namespace: myapp
spec:
  parentRefs:
  - name: kubelab-gateway
    namespace: istio-system
  hostnames:
  - "myapp.kubelab.local"
  rules:
  - backendRefs:
    - name: myapp-svc
      port: 80
```

```yaml
# HTTPS(TLS passthrough) 예시 — myapp-svc 는 자체 인증서로 TLS 를 직접 종료해야 함
apiVersion: gateway.networking.k8s.io/v1alpha2
kind: TLSRoute
metadata:
  name: myapp-tlsroute
  namespace: myapp
spec:
  parentRefs:
  - name: kubelab-gateway
    namespace: istio-system
    sectionName: https
  hostnames:
  - "myapp.kubelab.local"
  rules:
  - backendRefs:
    - name: myapp-svc
      port: 8443
```

### kubernetes 버전 고정

`install-kubelab-mac.sh` 상단에 다음 두 값이 고정되어 있습니다.

```bash
PINNED_K8S_VERSION="1.36.1"
PINNED_KIND_NODE_IMAGE="kindest/node:v1.36.1@sha256:3489c7674813ba5d8b1a9977baea8a6e553784dab7b84759d1014dbd78f7ebd5"
```

- 2026-07-31 기준 kind v0.32.0의 기본/권장 노드 이미지입니다.
- `-k/--k8s-version`을 주지 않으면 이 버전으로 kind 클러스터가 생성됩니다.
- kubectl은 다른 도구들과 동일하게 brew로 설치되는 최신 버전을 그대로 씁니다.
  kubectl은 kube-apiserver/kubelet과 minor 버전 ±1 이내까지는 공식 지원 범위라,
  patch 버전까지 정확히 맞출 필요는 없습니다. 다만 `PINNED_K8S_VERSION`을 너무 오래
  갱신하지 않고 방치하면 이 범위를 벗어날 수 있으니 가끔 최신 버전으로 올려주세요.

**새 버전으로 업데이트하는 방법**: [kind 릴리스 노트](https://github.com/kubernetes-sigs/kind/releases)에서
새 기본 노드 이미지의 `kindest/node:vX.Y.Z@sha256:...` 값을 확인해 `PINNED_K8S_VERSION`,
`PINNED_KIND_NODE_IMAGE`를 직접 갱신하세요. 자동으로 매번 최신을 따라가지 않는 이유는
재현성 때문입니다 — 몇 달 뒤 재실행해도 그때와 동일한 버전이 뜨도록 고정해 둡니다.

같은 이유로 Gateway API CRD 버전도 고정되어 있습니다 (`PINNED_GATEWAY_API_VERSION="1.6.1"`).
새 버전은 [gateway-api 릴리스](https://github.com/kubernetes-sigs/gateway-api/releases)에서 확인하세요.

## 삭제: uninstall-kubelab-mac.sh

```bash
./uninstall-kubelab-mac.sh [options]
```

| 옵션 | 설명 |
|---|---|
| `-n, --name <name>` | 삭제할 kind 클러스터 이름 (기본값: `kubelab`) |
| `--purge` | colima VM을 정지가 아닌 완전 삭제 |
| `--remove-tools` | install-kubelab-mac.sh가 설치했던 CLI 도구(colima, docker, kind, kubectx,
  istioctl, k9s, kubectl)까지 전부 삭제. `--purge`가 자동으로 함께 적용됨 |
| `-y, --yes` | 확인 프롬프트 없이 바로 진행 |
| `-h, --help` | 도움말 출력 |

기본 동작은 kind 클러스터 삭제 + colima VM 정지(VM은 남겨서 재사용 가능)입니다.
버전 옵션은 없습니다 — 클러스터/VM/도구를 통째로 지우는 동작이라 어떤 kubernetes
버전이었는지는 상관없습니다.

예시:
```bash
# 클러스터 삭제 + colima는 정지만
./uninstall-kubelab-mac.sh

# 클러스터 + colima VM까지 완전 삭제
./uninstall-kubelab-mac.sh --purge -y

# 전부 삭제하고 다음에 install-kubelab-mac.sh로 처음부터 재설치할 계획일 때
./uninstall-kubelab-mac.sh --remove-tools -y
```

## 트러블슈팅

### colima start 시 "error getting qcow image" 에러

```
error starting vm: error at 'creating and starting': error getting qcow image: error during image download:
error resolving download URL 'https://github.com/abiosoft/colima-core/releases/download/...': resolve redirect for ~
```

**원인**: colima는 VM을 처음 띄울 때 기본 OS 디스크 이미지를 GitHub 릴리스에서 받아옵니다.
GitHub 릴리스 다운로드 링크는 실제 파일이 아니라 CDN(`objects.githubusercontent.com`)으로
가는 리다이렉트인데, 그 순간 네트워크/DNS가 불안정하면 리다이렉트 대상을 못 찾아 위 에러가
납니다. 스크립트나 colima 설정 문제가 아니라 그 시점의 네트워크 문제였습니다.

**해결**: 스크립트를 그냥 다시 실행하면 됩니다 (`./install-kubelab-mac.sh`). 재시도만으로
해결됐고, 원인이 명확한 DNS/네트워크 문제였는지는 특정하지 못했습니다. 계속 반복되면:

```bash
# 다운로드 캐시가 깨진 채로 남아있을 수 있음 — 지우고 재시도
rm -rf ~/.cache/lima

# 실제 원인을 자세히 보고 싶으면
curl -v -L "https://github.com/abiosoft/colima-core/releases/download/v0.10.4/ubuntu-24.04-minimal-cloudimg-arm64-docker.raw.gz" -o /dev/null
```

### 재설치했는데 "failed to get cluster internal kubeconfig: ... is not running" 에러

`kind get clusters`는 노드 컨테이너가 존재하기만 하면 "클러스터 있음"으로 판단하는데,
colima를 `stop`했다가 다시 `start`하면 VM은 다시 뜨지만 그 안의 kind 노드 컨테이너는
자동으로 재시작되지 않아 꺼진 채로 남아있을 수 있습니다. 이 상태에서 `kubectl` 연결을
시도하면 위 에러가 납니다.

`install-kubelab-mac.sh`는 이 상태를 감지해서 노드 컨테이너를 자동으로 재시작 시도하고,
그래도 안 되면 클러스터를 삭제하고 새로 만들도록 되어 있습니다. 수동으로 정리하고 싶으면:

```bash
kind delete cluster --name kubelab
./install-kubelab-mac.sh
```

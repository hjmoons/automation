# kubelab

Mac에 colima + kind 기반 kubernetes 학습/실습 환경을 설치/삭제하는 스크립트.

- `install-kubelab-mac.sh` — colima, kind, kubectl, kubens, istioctl, k9s 설치 → colima 기동 →
  kind 클러스터 생성 → kubectl 연결 → metrics-server 설치 → Istio ingress gateway 설치까지 한 번에 진행
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
| `-p, --port <port>` | Istio Gateway에 추가로 열어줄 포트 (여러 번 지정 가능) | - |
| `-n, --name <name>` | kind 클러스터 이름 | `kubelab` |
| `-k, --k8s-version <x.y.z>` | kind 클러스터의 kubernetes 버전 직접 지정 | 아래 "고정된 버전" 참고 |
| `-h, --help` | 도움말 출력 | - |

80, 443 포트는 옵션 없이도 항상 Istio Gateway에 열립니다.

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
| istioctl / Istio | ingress gateway (Envoy) | brew (없을 때만) |
| k9s | 클러스터 TUI 대시보드 | brew (없을 때만) |
| metrics-server | `kubectl top`, k9s 리소스 뷰용 메트릭 | 클러스터 내부에 매니페스트 적용 |

nginx ingress controller는 EOL이라 Istio ingress gateway(Envoy)를 대신 설치하고, `istio-system`
네임스페이스에 `kubelab-gateway` Gateway 리소스로 80/443(+추가 포트)를 노출합니다.

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

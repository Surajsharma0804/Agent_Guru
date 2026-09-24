# Platform Integration Deployment Guide

## Prerequisites

- Python 3.11+
- pip 23+
- (Optional) NVIDIA GPU with CUDA 11.8+ for GPU monitoring
- (Optional) Docker 24+ for containerized deployment

---

## Installation

### 1. Clone and set up virtual environment

```bash
git clone https://github.com/your-org/agent-guru.git
cd agent-guru

python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate
```

### 2. Install dependencies

**GPU (recommended)**:
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install -r requirements.txt
```

**CPU only**:
```bash
pip install -r requirements-cpu.txt
```

### 3. Platform-specific dependencies

**Windows**:
```bash
pip install pywin32>=306
```

**macOS**:
```bash
pip install pyobjc
```

**Linux**:
```bash
pip install dbus-python>=1.3.2
sudo apt-get install -y libdbus-1-dev  # Ubuntu/Debian
```

### 4. Verify installation

```bash
python -c "from Agent_Guru.platform.platform_detector import PlatformDetector; print(PlatformDetector.detect())"
python verify_setup.py
```

---

## Configuration Setup

### 1. Create permissions config

```bash
cp Agent_Guru/platform/permissions/example_permissions.yaml \
   Agent_Guru/platform/permissions/config.yaml
```

Edit `config.yaml` for your environment. See [Configuration Guide](configuration_guide.md).

### 2. Set environment variables

```bash
# Linux/macOS
export AGENT_GURU_ENV=production
export AGENT_GURU_PERMISSIONS_CONFIG=/etc/agent_guru/permissions.yaml
export AGENT_GURU_LOG_DIR=/var/log/agent_guru
export AGENT_GURU_MAX_MEMORY_GB=2
export AGENT_GURU_MAX_CPU_PCT=80

# Windows (PowerShell)
$env:AGENT_GURU_ENV = "production"
$env:AGENT_GURU_LOG_DIR = "C:\ProgramData\AgentGuru\logs"
```

### 3. Create log directory

```bash
# Linux/macOS
sudo mkdir -p /var/log/agent_guru
sudo chown $USER:$USER /var/log/agent_guru

# Windows (PowerShell as Admin)
New-Item -ItemType Directory -Path "C:\ProgramData\AgentGuru\logs" -Force
```

---

## Service Deployment

### Systemd (Linux)

Create `/etc/systemd/system/agent-guru-platform.service`:

```ini
[Unit]
Description=Agent Guru Platform Integration Service
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=agent_guru
Group=agent_guru
WorkingDirectory=/opt/agent-guru
Environment=AGENT_GURU_ENV=production
Environment=AGENT_GURU_LOG_DIR=/var/log/agent_guru
ExecStart=/opt/agent-guru/venv/bin/python -m Agent_Guru.platform.service
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=agent-guru-platform

# Resource limits
MemoryMax=2G
CPUQuota=80%

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable agent-guru-platform
sudo systemctl start agent-guru-platform
sudo systemctl status agent-guru-platform
```

### Windows Service

```powershell
# Install as Windows service using NSSM
nssm install AgentGuruPlatform "C:\opt\agent-guru\venv\Scripts\python.exe"
nssm set AgentGuruPlatform AppParameters "-m Agent_Guru.platform.service"
nssm set AgentGuruPlatform AppDirectory "C:\opt\agent-guru"
nssm set AgentGuruPlatform AppEnvironmentExtra "AGENT_GURU_ENV=production"
nssm start AgentGuruPlatform
```

### Docker

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements-cpu.txt .
RUN pip install --no-cache-dir -r requirements-cpu.txt

COPY . .
RUN pip install -e .

ENV AGENT_GURU_ENV=production
ENV AGENT_GURU_LOG_DIR=/var/log/agent_guru

RUN mkdir -p /var/log/agent_guru

CMD ["python", "-m", "Agent_Guru.platform.service"]
```

```bash
docker build -t agent-guru-platform:latest .
docker run -d \
  --name agent-guru-platform \
  -e AGENT_GURU_ENV=production \
  -v /var/log/agent_guru:/var/log/agent_guru \
  -v /etc/agent_guru:/etc/agent_guru:ro \
  --memory=2g \
  --cpus=0.8 \
  agent-guru-platform:latest
```

### Kubernetes

```yaml
# k8s/platform-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-guru-platform
  namespace: agent-guru
spec:
  replicas: 2
  selector:
    matchLabels:
      app: agent-guru-platform
  template:
    metadata:
      labels:
        app: agent-guru-platform
    spec:
      containers:
        - name: platform
          image: agent-guru-platform:latest
          env:
            - name: AGENT_GURU_ENV
              value: "production"
            - name: AGENT_GURU_LOG_DIR
              value: "/var/log/agent_guru"
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "2Gi"
              cpu: "800m"
          volumeMounts:
            - name: logs
              mountPath: /var/log/agent_guru
            - name: config
              mountPath: /etc/agent_guru
              readOnly: true
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
      volumes:
        - name: logs
          emptyDir: {}
        - name: config
          configMap:
            name: agent-guru-platform-config
```

```bash
kubectl apply -f k8s/platform-deployment.yaml
kubectl rollout status deployment/agent-guru-platform -n agent-guru
```

---

## Monitoring Setup

### Prometheus

The platform exposes metrics at `:8080/metrics`. Configure Prometheus to scrape it:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'agent-guru-platform'
    static_configs:
      - targets: ['localhost:8080']
    scrape_interval: 15s
```

Key metrics exported:
- `agent_guru_cpu_percent` - current CPU usage
- `agent_guru_memory_bytes` - current memory usage
- `agent_guru_operations_total` - total operations by type
- `agent_guru_operation_errors_total` - errors by type
- `agent_guru_cache_hit_rate` - duplicate detector cache hit rate
- `agent_guru_throttle_events_total` - throttle activations

### Grafana

Import the pre-built dashboard from `grafana/dashboards/platform.json`:

```bash
curl -X POST http://admin:admin@localhost:3000/api/dashboards/import \
  -H "Content-Type: application/json" \
  -d @grafana/dashboards/platform.json
```

### Log Aggregation

Logs are written in structured JSON format to `$AGENT_GURU_LOG_DIR/platform.log`.

**Filebeat config** for ELK stack:
```yaml
filebeat.inputs:
  - type: log
    paths:
      - /var/log/agent_guru/*.log
    json.keys_under_root: true
    json.add_error_key: true

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
  index: "agent-guru-platform-%{+yyyy.MM.dd}"
```

---

## Health Checks

The platform exposes health endpoints:

```bash
# Liveness (is the process alive?)
curl http://localhost:8080/health

# Readiness (is it ready to serve?)
curl http://localhost:8080/ready

# Detailed component status
curl http://localhost:8080/health/detailed
```

Example response:
```json
{
  "status": "healthy",
  "components": {
    "resource_monitor": "healthy",
    "security_auditor": "healthy",
    "permission_manager": "healthy",
    "network_manager": "healthy",
    "duplicate_detector": "healthy"
  },
  "uptime_seconds": 3600,
  "version": "1.0.0"
}
```

---

## Running Tests

```bash
# All tests
pytest Agent_Guru/platform/tests/ -v

# With coverage
pytest Agent_Guru/platform/tests/ --cov=Agent_Guru.platform --cov-report=html

# Performance benchmarks only
pytest Agent_Guru/platform/tests/ -m performance -v

# Unit tests only (fast)
pytest Agent_Guru/platform/tests/ -m unit -v
```

---

## Upgrading

```bash
git pull origin main
pip install -r requirements.txt --upgrade

# Reload service (zero downtime with systemd)
sudo systemctl reload agent-guru-platform

# Or restart if reload not supported
sudo systemctl restart agent-guru-platform
```

#!/bin/bash
# Google Cloud GPU Startup Script
# Run this on a Google Cloud VM with GPU attached

set -e

echo "=== Agentic AI Workbench - Google Cloud GPU Setup ==="

# 1. Install NVIDIA Container Toolkit (if not already installed)
if ! command -v nvidia-container-toolkit &> /dev/null; then
    echo "Installing NVIDIA Container Toolkit..."
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
        sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
    sudo apt-get update
    sudo apt-get install -y nvidia-container-toolkit
    sudo nvidia-ctk runtime configure --runtime=docker
    sudo systemctl restart docker
fi

# 2. Verify GPU access
echo "Verifying GPU access..."
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi

# 3. Build the GPU-enabled Docker image
echo "Building GPU Docker image..."
docker build -f Dockerfile -t agentic-ai-workbench:gpu .

# 4. Run with GPU support
echo "Starting Agentic AI Workbench on GPU..."
docker run -d \
    --name agentic-ai-workbench \
    --gpus all \
    --shm-size=8g \
    -p 8000:8000 \
    -v $(pwd)/data:/app/data \
    -v $(pwd)/configs:/app/configs \
    --restart unless-stopped \
    agentic-ai-workbench:gpu

echo "=== Deployment Complete ==="
echo "API available at: http://$(curl -s ifconfig.me):8000"
echo "Health check: curl http://localhost:8000/health"
echo ""
echo "To view logs: docker logs -f agentic-ai-workbench"
echo "To stop: docker stop agentic-ai-workbench"
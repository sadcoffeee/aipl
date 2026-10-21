
FROM nvcr.io/nvidia/vllm:26.01-py3

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git curl ffmpeg tmux sqlite3 python3-venv ca-certificates gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

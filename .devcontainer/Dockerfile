
FROM nvcr.io/nvidia/vllm:26.01-py3

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git curl ffmpeg tmux sqlite3 python3-venv ca-certificates gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# The Docker command-line tool (only the client, no Docker engine). The backend uses it to start a throwaway  container for every graded submission, through the Spark's own Docker, whose socket devcontainer.json mounts in.
RUN install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends docker-ce-cli docker-buildx-plugin && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

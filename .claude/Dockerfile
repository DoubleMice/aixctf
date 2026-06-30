FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV AIXCTF_AGENT_ROOT=/aixctf-agent
ENV AIXCTF_WORKSPACE_BASE=/aixctf-agent/workspace
ENV CHALLENGE_DIR=/challenge
ENV OUTPUT_DIR=/output
ENV VIRTUAL_ENV=/opt/aixctf-venv
ENV NODE_MAJOR=20
ENV RADARE2_VERSION=6.1.8
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/ubuntu.sources ] \
      && ! grep -q '^Components:.*universe' /etc/apt/sources.list.d/ubuntu.sources; then \
      sed -i -E '/^Components:/ s/$/ universe/' /etc/apt/sources.list.d/ubuntu.sources; \
    fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    && install -d -m 0755 /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
      | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" \
      > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    python3 python3-venv \
    netcat-openbsd socat \
    iproute2 iputils-ping dnsutils \
    gdb gdbserver \
    file binutils checksec strace ltrace patchelf \
    ruby jq ripgrep unzip xxd nmap nodejs \
    && apt-get purge -y --auto-remove gnupg \
    && rm -rf /var/lib/apt/lists/*

RUN arch="$(dpkg --print-architecture)" \
    && case "${arch}" in amd64|arm64|i386) ;; *) echo "unsupported radare2 arch: ${arch}" >&2; exit 1 ;; esac \
    && curl -fsSL -o /tmp/radare2.deb \
      "https://github.com/radareorg/radare2/releases/download/${RADARE2_VERSION}/radare2_${RADARE2_VERSION}_${arch}.deb" \
    && apt-get update \
    && apt-get install -y --no-install-recommends /tmp/radare2.deb \
    && rm -f /tmp/radare2.deb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /aixctf-agent
COPY requirements.txt package.json /aixctf-agent/

RUN python3 -m venv "${VIRTUAL_ENV}" \
    && pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r /aixctf-agent/requirements.txt
RUN gem install one_gadget
RUN npm install -g @anthropic-ai/claude-code

COPY . /aixctf-agent

RUN chmod +x /aixctf-agent/entrypoint.py \
    /aixctf-agent/tools/pwn_triage.py \
    /aixctf-agent/tools/web_triage.py || true

ENTRYPOINT ["python3", "/aixctf-agent/entrypoint.py"]

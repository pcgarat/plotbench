FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Dependencias de sistema estables: Python 3.12 + venv (ensurepip) y utilidades base.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        sudo \
        python3.12 \
        python3.12-venv \
    && rm -rf /var/lib/apt/lists/*

# Usuario 'ubuntu' con sudo sin contraseña (convención de Cloud Agents).
# La imagen ubuntu:24.04 ya trae el usuario 'ubuntu' (uid 1000); el guard lo cubre por si cambia.
RUN if ! id ubuntu >/dev/null 2>&1; then useradd -m -s /bin/bash -u 1000 ubuntu; fi \
    && echo 'ubuntu ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/ubuntu \
    && chmod 0440 /etc/sudoers.d/ubuntu

USER ubuntu

FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       git \
       curl \
       ca-certificates \
       gcc \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID
RUN groupadd --gid $USER_GID $USERNAME || true \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME || true

WORKDIR /workspace
USER $USERNAME

ENV PATH="/home/$USERNAME/.local/bin:${PATH}"

CMD ["bash"]

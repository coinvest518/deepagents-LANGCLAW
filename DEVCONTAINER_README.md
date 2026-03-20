This repository includes a minimal VS Code devcontainer configuration so you can develop without installing heavy dependencies on your host machine.

Files added
- `.devcontainer/Dockerfile` — lightweight Python 3.11 image and non-root user.
- `.devcontainer/devcontainer.json` — VS Code devcontainer config; runs `pip install -e libs/deepagents` and `pip install -e libs/cli` after creation.

If you have Docker available locally
1. Install Docker (Docker Desktop) and the VS Code Remote - Containers extension.
2. Open this folder in VS Code and select **Reopen in Container**.

If you DO NOT want to run Docker locally (slow laptop)
- Use GitHub Codespaces or Gitpod: they run the container in the cloud and give you a browser/VS Code interface without installing Docker locally.
- Use VS Code Remote - SSH to connect to a cloud VM (small cost) and run the devcontainer there, or install dependencies on that remote host.

Quick alternatives (no Docker):
- GitHub Codespaces: open repo in Codespaces and it will use the devcontainer files.
- Gitpod: add a Gitpod config or open the repo via gitpod and it will use the same Dockerfile.
- Remote VM: provision a small cloud VM (AWS/GCP/Azure) and SSH from VS Code.

If you want, I can prepare a short `codespaces` / `gitpod` config or an example cloud VM script.

# ALMOND Docker Image Delivery

The DeepWuKong runtime is distributed separately because the Docker archive is
too large for Git and the Moodle source-code ZIP.

## Download

Download the delivery folder from
[UNSW OneDrive](https://unsw-my.sharepoint.com/:f:/g/personal/z5462057_ad_unsw_edu_au/IgCDusTbCoy4TIvZjFGzW6nFAUVNNinwLIUlanldfyHryZs?e=zckK4M).

Required archive:

```text
deepwukong-rtx5060-cu128-experimental.tar
```

Archive metadata:

| Property | Value |
|---|---|
| Size | 4,766,494,208 bytes (4.439 GiB) |
| SHA-256 | `0482EA09F89569072427344B1DADA5E72878DF2E7BC99F878F5895B17DAF6B1D` |
| Docker tag | `deepwukong-rtx5060-cu128:experimental` |
| Docker image ID | `sha256:4735e489150a248ff4dc2040d366c5c09721263db9f6d8f7b116d39c0d035aea` |
| Platform | `linux/amd64` |

## Verify and load

Open PowerShell in the folder containing the downloaded archive:

```powershell
Get-FileHash .\deepwukong-rtx5060-cu128-experimental.tar -Algorithm SHA256
docker load -i .\deepwukong-rtx5060-cu128-experimental.tar
docker image inspect deepwukong-rtx5060-cu128:experimental
```

Do not load or run the archive if the calculated SHA-256 differs from the value
above. A verified test import of this archive restored the expected image tag.

## Build ALMOND

Extract the source-code submission and open PowerShell in its repository root:

```powershell
docker compose -f scripts/docker/compose.yaml build almond
```

The build creates `t17a-almond:latest`. The project Dockerfile installs
Graphviz; an internet connection is required while that package is downloaded
if the build layer is not already cached.

## Test and run

Run the complete container test suite:

```powershell
docker compose -f scripts/docker/compose.yaml run --rm almond tests
```

Expected result:

```text
Ran 66 tests
OK
```

Verify GPU access through the built project image:

```powershell
docker run --rm --gpus all --entrypoint python t17a-almond:latest `
  -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

The first output line must be `True`. Start the application from the repository
root using either:

```powershell
.\Start.exe
```

or:

```powershell
.\robustness_experiments\Start.ps1
```

## Troubleshooting

- If Docker cannot connect to the daemon, start Docker Desktop and wait for the
  Linux engine to report that it is running.
- If the base image is not found during the build, repeat `docker load` and
  confirm that `docker image inspect` shows the exact expected tag.
- If the GPU is unavailable, confirm that `nvidia-smi` works on the host and
  that Docker Desktop has NVIDIA GPU access.
- If PowerShell blocks the launcher script, run
  `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and retry.
- If the checksum differs, download the archive again from the OneDrive folder.

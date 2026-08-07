# The existing runtime image contains the pinned DeepWuKong, PyTorch Geometric,
# and Joern toolchain required for full inference.  The project repository only
# contains the wrapper and checkpoint, so extending this image keeps the Docker
# package reproducible without silently changing the model runtime.
ARG BASE_IMAGE=deepwukong-rtx5060-cu128:experimental
FROM ${BASE_IMAGE}

WORKDIR /repo

# Graphviz renders the PDG Atlas and is required by four rendering tests. The
# base runtime does not provide `dot`, so install it in the project image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends graphviz \
    && rm -rf /var/lib/apt/lists/*

# NetworkX is the sole Python-side project dependency. It is installed here so
# graph perturbations and their tests work in the packaged environment too.
COPY requirements.txt /tmp/almond-requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/almond-requirements.txt

COPY . /repo

# Keep the full DeepWuKong source tree in /workspace ahead of the lightweight
# host-side compatibility package under baselines/deepwukong.
ENV PYTHONPATH=/repo:/workspace
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

ENTRYPOINT ["python", "scripts/docker/docker_entrypoint.py"]
CMD ["console"]

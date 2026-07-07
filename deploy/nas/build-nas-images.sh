#!/usr/bin/env bash
#
# Build the Jellyfish backend and frontend images locally and export them as
# tar archives, for deployment on a NAS (or any host) that cannot
# build images from source.
#
# Workflow:
#   1. Run this script on a host that can build Docker images (e.g. your dev machine).
#   2. Copy the produced .tar archives to the NAS.
#   3. On the NAS: `docker load -i <file>.tar` for each image.
#   4. On the NAS: `docker compose -f docker-compose-nas.yml --env-file .env up -d`.
#
# Usage:
#   ./build-nas-images.sh                            # PLATFORM=linux/amd64, IMAGE_TAG=latest
#   PLATFORM=linux/arm64 ./build-nas-images.sh       # for an ARM-based NAS
#   IMAGE_TAG=v1.2.3 ./build-nas-images.sh           # custom tag (must match IMAGE_TAG in .env)
#   OUTPUT_DIR=/tmp/imgs ./build-nas-images.sh
#
# Cross-architecture builds (e.g. linux/arm64 on an x86 host) require QEMU:
#   - Docker Desktop: bundled, no extra setup.
#   - Linux: docker run --privileged --rm tonistiigi/binfmt --install all

set -euo pipefail

# --- configuration (overridable via env) ---
PLATFORM="${PLATFORM:-linux/amd64}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
BACKEND_IMAGE="jellyfish-backend:${IMAGE_TAG}"
FRONT_IMAGE="jellyfish-front:${IMAGE_TAG}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OUTPUT_DIR="${OUTPUT_DIR:-${SCRIPT_DIR}/dist}"
ARCH="${PLATFORM##*/}"  # amd64, arm64, ...

BACKEND_TAR="${OUTPUT_DIR}/jellyfish-backend-${IMAGE_TAG}-${ARCH}.tar"
FRONT_TAR="${OUTPUT_DIR}/jellyfish-front-${IMAGE_TAG}-${ARCH}.tar"

# --- preflight ---
command -v docker >/dev/null 2>&1 || { echo "ERROR: docker not found in PATH" >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "ERROR: docker daemon is not reachable" >&2; exit 1; }
export DOCKER_BUILDKIT=1

mkdir -p "${OUTPUT_DIR}"
cd "${REPO_ROOT}"

build_image() {
  local image="$1" dockerfile="$2" name="$3"
  echo "==> Building ${name}: ${image} (${PLATFORM})"
  docker build --platform "${PLATFORM}" -t "${image}" -f "${dockerfile}" .
  echo "==> Built ${image}"
  echo
}

save_image() {
  local image="$1" tar="$2" name="$3"
  echo "==> Saving ${name} -> ${tar}"
  docker save -o "${tar}" "${image}"
  echo "==> Saved ${tar} ($(du -h "${tar}" | cut -f1))"
  echo
}

build_image "${BACKEND_IMAGE}" "deploy/docker/backend.Dockerfile" "backend"
build_image "${FRONT_IMAGE}"  "deploy/docker/front.Dockerfile"  "front"

save_image "${BACKEND_IMAGE}" "${BACKEND_TAR}" "backend"
save_image "${FRONT_IMAGE}"   "${FRONT_TAR}"   "front"

echo "========================================================="
echo "Done. Built images:"
echo "  ${BACKEND_IMAGE}"
echo "  ${FRONT_IMAGE}"
echo
echo "Archives (copy these to the NAS):"
echo "  ${BACKEND_TAR}"
echo "  ${FRONT_TAR}"
echo
echo "On the NAS:"
echo "  docker load -i jellyfish-backend-${IMAGE_TAG}-${ARCH}.tar"
echo "  docker load -i jellyfish-front-${IMAGE_TAG}-${ARCH}.tar"
echo "  docker compose -f docker-compose-nas.yml --env-file .env up -d"
echo "========================================================="

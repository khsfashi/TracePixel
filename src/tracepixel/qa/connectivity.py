from __future__ import annotations

from array import array
from typing import Literal, TypedDict

from tracepixel.raster import Canvas

CONNECTIVITY_QA_SCHEMA_V1 = "tracepixel.connectivity-qa.v1"
CONNECTIVITY_NEIGHBORS_V1 = 4


class ConnectedComponentFactsV1(TypedDict):
    count: int
    largest_pixels: int


class IsolatedPixelFactsV1(TypedDict):
    count: int
    has_isolated_pixels: bool


class ConnectivityQaV1(TypedDict):
    schema: Literal["tracepixel.connectivity-qa.v1"]
    connectivity: Literal[4]
    visible_pixels: int
    components: ConnectedComponentFactsV1
    isolated_pixels: IsolatedPixelFactsV1


def analyze_connectivity(canvas: Canvas) -> ConnectivityQaV1:
    """Return exact 4-neighbor connectivity facts over structurally visible pixels.

    Visibility follows the existing Q0/Q1 contract: a stored alpha byte other than zero is
    visible. Components use edge adjacency only; diagonal corner contact does not connect
    pixels. A pixel is isolated exactly when its 4-neighbor connected component has size 1.

    Traversal is iterative and borrows Canvas' package-internal read-only RGBA view. The
    visited state is one bit per raster position and the pending stack stores packed unsigned
    pixel indices rather than Python coordinate objects or a recursive call stack.
    """

    if not isinstance(canvas, Canvas):
        raise TypeError("canvas must be a tracepixel.raster.Canvas")

    width = canvas.width
    pixel_count = width * canvas.height
    rgba = canvas._rgba_view()

    visited = bytearray((pixel_count + 7) // 8)
    stack = array("I")
    if stack.itemsize < 4:
        # The raster contract allows up to 24-bit pixel indices. C unsigned long is at
        # least 32 bits, so retain packed storage on uncommon narrow-unsigned-int hosts.
        stack = array("L")

    visible_pixels = 0
    component_count = 0
    largest_component_pixels = 0
    isolated_pixel_count = 0

    for seed in range(pixel_count):
        if rgba[(seed << 2) + 3] == 0:
            continue

        seed_byte = seed >> 3
        seed_mask = 1 << (seed & 7)
        if visited[seed_byte] & seed_mask:
            continue

        visited[seed_byte] |= seed_mask
        stack.append(seed)
        component_pixels = 0

        while stack:
            current = stack.pop()
            component_pixels += 1
            x = current % width

            if x > 0:
                neighbor = current - 1
                byte_index = neighbor >> 3
                mask = 1 << (neighbor & 7)
                if not visited[byte_index] & mask and rgba[(neighbor << 2) + 3] != 0:
                    visited[byte_index] |= mask
                    stack.append(neighbor)

            if x + 1 < width:
                neighbor = current + 1
                byte_index = neighbor >> 3
                mask = 1 << (neighbor & 7)
                if not visited[byte_index] & mask and rgba[(neighbor << 2) + 3] != 0:
                    visited[byte_index] |= mask
                    stack.append(neighbor)

            if current >= width:
                neighbor = current - width
                byte_index = neighbor >> 3
                mask = 1 << (neighbor & 7)
                if not visited[byte_index] & mask and rgba[(neighbor << 2) + 3] != 0:
                    visited[byte_index] |= mask
                    stack.append(neighbor)

            neighbor = current + width
            if neighbor < pixel_count:
                byte_index = neighbor >> 3
                mask = 1 << (neighbor & 7)
                if not visited[byte_index] & mask and rgba[(neighbor << 2) + 3] != 0:
                    visited[byte_index] |= mask
                    stack.append(neighbor)

        component_count += 1
        visible_pixels += component_pixels
        if component_pixels > largest_component_pixels:
            largest_component_pixels = component_pixels
        if component_pixels == 1:
            isolated_pixel_count += 1

    return {
        "schema": CONNECTIVITY_QA_SCHEMA_V1,
        "connectivity": CONNECTIVITY_NEIGHBORS_V1,
        "visible_pixels": visible_pixels,
        "components": {
            "count": component_count,
            "largest_pixels": largest_component_pixels,
        },
        "isolated_pixels": {
            "count": isolated_pixel_count,
            "has_isolated_pixels": isolated_pixel_count > 0,
        },
    }

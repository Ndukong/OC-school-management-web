"""Preload WeasyPrint's native libraries by absolute path.

Railway/Nixpacks images ship a Nix-built Python whose RUNPATH loses to any
LD_LIBRARY_PATH entry, so we cannot point the loader at Ubuntu's multiarch
dir without crashing the interpreter. Preloading the dependency chain with
absolute paths sidesteps search paths entirely: once a library is in the
process image, later dlopen(soname) calls reuse it.

No-op when the libraries are absent (local Windows dev uses the GTK bundle).
"""

from ctypes import CDLL
from pathlib import Path

_CANDIDATES = [
    "libpcre2-8.so.0",
    "libffi.so.8",
    "libglib-2.0.so.0",
    "libgobject-2.0.so.0",
    "libgmodule-2.0.so.0",
    "libintl.so.8",
    "libiconv.so.2",
    "libz.so.1",
    "libharfbuzz.so.0",
    "libfontconfig.so.1",
    "libfreetype.so.6",
    "libpng16.so.16",
    "libbrotlidec.so.1",
    "libbrotlicommon.so.1",
    "libexpat.so.1",
    "libuuid.so.1",
    "libpixman-1.so.0",
    "libxcb.so.1",
    "libxcb-render.so.0",
    "libxcb-shm.so.0",
    "libX11.so.6",
    "libXext.so.6",
    "libXrender.so.1",
    "libthai.so.0",
    "libdatrie.so.1",
    "libgraphite2.so.3",
    "libbz2.so.1.0",
    "liblzma.so.5",
    "libjpeg.so.8",
    "libtiff.so.6",
    "libwebp.so.7",
    "libdeflate.so.0",
    "libjbig.so.0",
    "liblerc.so.4",
    "libsharpyuv.so.0",
    "libgdk_pixbuf-2.0.so.0",
    "libcairo.so.2",
    "libpango-1.0.so.0",
    "libpangoft2-1.0.so.0",
    "libpangocairo-1.0.so.0",
]

_SEARCH_DIRS = [
    "/usr/lib/x86_64-linux-gnu",
    "/usr/lib/aarch64-linux-gnu",
    "/usr/lib",
    "/lib/x86_64-linux-gnu",
]

_loaded = False


def preload_native_libs() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    for name in _CANDIDATES:
        for directory in _SEARCH_DIRS:
            candidate = Path(directory) / name
            if candidate.exists():
                try:
                    CDLL(str(candidate))
                except OSError:
                    pass
                break

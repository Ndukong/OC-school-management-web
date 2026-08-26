"""Preload WeasyPrint's native libraries by absolute path.

Railway/Nixpacks images run a Nix-built interpreter whose loader never sees
system library dirs (apt libs) nor the hashed /nix/store lib dirs (not on
any search path), so WeasyPrint's dlopen("libgobject-2.0-0") always fails.

Loading the top-level Nix packages' libraries by absolute path works because
each Nix library embeds the store paths of its own dependencies as RUNPATH —
the whole closure loads automatically and registers under its real sonames
(e.g. libgobject-2.0.so.0), which WeasyPrint's fallback name list then hits.

Silent no-op outside Nix images (local Windows dev uses the GTK bundle).
"""

import glob
from ctypes import CDLL

_NIX_GLOBS = [
    "/nix/store/*-glib-*/lib/libgobject-2.0.so*",
    "/nix/store/*-glib-*/lib/libgmodule-2.0.so*",
    "/nix/store/*-glib-*/lib/libglib-2.0.so*",
    "/nix/store/*-pango-*/lib/libpango*.so*",
    "/nix/store/*-cairo-*/lib/libcairo*.so*",
    "/nix/store/*-gdk-pixbuf-*/lib/libgdk_pixbuf*.so*",
    "/nix/store/*-fontconfig-*/lib/libfontconfig*.so*",
    "/nix/store/*-freetype-*/lib/libfreetype*.so*",
    "/nix/store/*-harfbuzz-*/lib/libharfbuzz*.so*",
    "/nix/store/*-fribidi-*/lib/libfribidi*.so*",
]

_loaded = False


def preload_native_libs() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    for pattern in _NIX_GLOBS:
        for path in sorted(glob.glob(pattern)):
            try:
                CDLL(path)
            except OSError:
                pass

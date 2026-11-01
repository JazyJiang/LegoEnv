# Source identities

SOURCE_MANIFEST.json records the verified source files before local API and
layout updates. LAYOUT_MAP.json maps the original component paths to the
current functional directories. CODE_MANIFEST.json records the final source
hashes in this code-only tree. Data and binaries are supplied separately.

The recorded original copy used a temporary `release/` prefix in its source
paths. Remove that prefix before applying LAYOUT_MAP.json. Final paths and
hashes are always those in CODE_MANIFEST.json.

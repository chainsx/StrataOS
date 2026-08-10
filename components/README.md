# Component sources

Every directory below this one is one component source. The required files are:

```text
components/<name>/
  component.conf       declarative package and storage metadata
  packages.list        package recipe names included in the component
  rootfs/              optional project-authored overlay
  hooks/               optional lifecycle hooks
```

The assembler combines package DESTDIRs and `rootfs/`, normalizes ownership,
generates file hashes, then writes the uniform on-disk format described in
`FORMAT.md`. Missing optional directories are treated as empty.

`component.conf` is data and is never sourced as shell. Unknown ordinary keys
are rejected. Extension keys must begin with `x.` so future producers can add
namespaced metadata without weakening validation of the base format.

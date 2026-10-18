# xterm.js (vendored)

The web console's terminal, served gzipped from the node's flash (no CDN).
Files are byte-for-byte the npm releases, checked against the registry's
sha512 integrity:

| File | Package | npm integrity of the tarball |
|---|---|---|
| `xterm.mjs` (`lib/xterm.mjs`), `xterm.css` (`css/xterm.css`) | `@xterm/xterm` 6.0.0 | `sha512-TQwDdQGtwwDt+2cgKDLn0IRaSxYu1tSUjgKarSDkUM0ZNiSRXFpjxEsvc/Zgc5kq5omJ+V0a8/kIM2WD3sMOYg==` |
| `addon-fit.mjs` (`lib/addon-fit.mjs`) | `@xterm/addon-fit` 0.11.0 | `sha512-jYcgT6xtVYhnhgxh3QgYDnnNMYTcf8ElbxxFzX0IZo+vabQqSPAjC3c1wJrKB5E19VwQei89QCiZZP86DCPF7g==` |

MIT licensed, see [`LICENSE.txt`](LICENSE.txt) (served at `/xterm-LICENSE.txt`).
`.gitattributes` keeps git from touching their line endings.

To update: `npm pack @xterm/xterm @xterm/addon-fit`, copy the same files,
update the versions above, and check the console page.

## Hosting & Distribution Strategy

> Addresses: [Issue #186](https://github.com/petertzy/markdown-reader/issues/186) · [Issue #189](https://github.com/petertzy/markdown-reader/issues/189)

### Recommended Stack

**GitHub Releases + Cloudflare Pages** — fully free, production-grade, zero maintenance overhead.

```
Cloudflare Pages  ← static landing/download website
    └── Download buttons
            ├── GitHub Releases → markdown-reader-windows.exe
            ├── GitHub Releases → markdown-reader-macos.dmg
            └── GitHub Releases → markdown-reader-linux.AppImage
```

---

### GitHub Releases — Binary Hosting

Upload app binaries directly to a GitHub Release.

| Property        | Detail                                               |
| --------------- | ---------------------------------------------------- |
| File size limit | 2 GB per file (current 81.5 MB is well within range) |
| Bandwidth       | Unlimited, served via GitHub's CDN                   |
| Versioning      | Each release is tagged (e.g.`v1.0.0`)                |
| Cost            | Free                                                 |

**Creating a release:**

```bash
git tag v1.0.0
git push origin v1.0.0
```

Then on GitHub: **Releases → Draft a new release → attach binaries → Publish** .

Download URLs follow a stable, predictable pattern:

```
https://github.com/petertzy/markdown-reader/releases/download/v1.0.0/markdown-reader-windows.exe
https://github.com/petertzy/markdown-reader/releases/download/v1.0.0/markdown-reader-macos.dmg
https://github.com/petertzy/markdown-reader/releases/download/v1.0.0/markdown-reader-linux.AppImage
```

---

### Cloudflare Pages — Website Hosting

Host the distribution website on Cloudflare Pages.

| Property  | Detail                                                 |
| --------- | ------------------------------------------------------ |
| Bandwidth | Unlimited on the free tier                             |
| CDN       | Global edge network, automatic HTTPS                   |
| Deploys   | Connected to GitHub — every push to `main`auto-deploys |
| Cost      | Free                                                   |

**Setup:**

1. Push the website source to a `/website` folder or a separate repo
2. Go to [Cloudflare Pages](https://pages.cloudflare.com/) → Connect GitHub repo
3. Set build output directory to `/website`
4. Deploy — Cloudflare assigns a `*.pages.dev` domain instantly

A custom domain can be attached at any time at no extra cost through Cloudflare.

---

### Why Not Vercel for File Hosting

Vercel's free tier caps total deployment size at **100 MB** and is designed for code and serverless functions, not binary distribution. Use Cloudflare Pages for the static site and GitHub Releases for the binaries.

---

### When a Paid VPS Makes Sense

A VPS is only worth considering once the project requires:

- Server-side rendering or user authentication
- A custom backend API for the website
- Self-hosted analytics or download tracking

At current scale, the free stack above handles everything with zero maintenance overhead.

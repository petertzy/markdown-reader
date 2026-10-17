# Code Signing & Distribution Trust

> Addresses: [Issue #326](https://github.com/petertzy/markdown-reader/issues/326)

Packaged desktop apps that are unsigned trigger operating-system trust warnings —
macOS Gatekeeper ("unidentified developer" / "damaged") and Windows Defender
SmartScreen. For non-technical users these warnings often mean abandoning the
install. This document surveys the practical options, costs, and free/open-source
routes, with an emphasis on what works well in an automated GitHub Actions release.

## TL;DR

| Approach | macOS | Windows | Linux | ≈ Cost / year |
| --- | --- | --- | --- | --- |
| **Minimal** (ad-hoc macOS + free OSS signing) | $0* | $0 (SignPath) | $0 | **$0** |
| **Balanced** (notarized macOS + Azure Artifact Signing Basic) | $99 | $119.88 | $0 | **~$219** |
| **Maximum trust** (notarized macOS + OV/EV cert) | $99 | $150–400+ | $0 | **~$250–500** |

\* Ad-hoc signing lets the app launch on Apple Silicon but does **not** remove the
Gatekeeper warning; the user still has to allow it once in **System Settings →
Privacy & Security**.

**Recommendation:** adopt **SignPath Foundation** (free for open source) for Windows,
ship **ad-hoc signed** macOS with clear first-run instructions (or pay the $99 for a
frictionless experience), and publish **checksums + a GPG-signed** Linux release.

## macOS

macOS is the one platform where a paid membership is effectively required for a
*warning-free* install.

- **Signing + notarization** requires the **Apple Developer Program ($99/year)**.
  You sign with a **Developer ID Application** certificate and then submit the
  bundle for **notarization**.
- The **free** Apple Developer plan can only be used for local testing/development
  and **cannot notarize**.
- **Ad-hoc signing** is *required* for apps to launch at all on Apple Silicon when
  downloaded from the internet, but it does **not** clear the Gatekeeper prompt.
  Tauri already ad-hoc signs by default when no `bundle.macOS.signingIdentity` is
  set, and this repo's `tauri.conf.json` has no `macOS` block at all — so current
  builds are already ad-hoc signed. Setting `"signingIdentity": "-"` explicitly
  documents the intent but changes nothing functionally.
- There is no reputable free notarization path.

## Windows

Signing reduces (but does not instantly eliminate) SmartScreen warnings — publisher
reputation still has to accrue over time.

- **Azure Artifact Signing** (formerly *Trusted Signing*) — HSM-backed (FIPS 140-2
  Level 3), CI-friendly, aimed at small projects and individual developers.
  Consumption-based pricing, unchanged from the Trusted Signing days:

  | Tier | Monthly | Signatures included | After quota |
  | --- | --- | --- | --- |
  | **Basic** | **USD $9.99 / month** | 5,000 / month | $0.005 per signature |
  | **Premium** | **USD $99.99 / month** | 100,000 / month | $0.005 per signature |

  Basic is the realistic choice for this project. Premium becomes cheaper above
  roughly **23,000 signatures/month**: at 100,000 signatures, Basic costs about
  **$485/month** versus Premium's $99.99. A desktop reader is nowhere near that
  volume, so Basic is the sensible starting tier.

  Three billing details worth knowing before committing:

  - **A paid Azure subscription is required.** Free, trial, and sponsored
    subscriptions are rejected at account creation.
  - **Billing is not pro-rated.** You are charged the full monthly amount for the
    SKU from the moment the Artifact Signing account is created, even if you never
    sign a file.
  - **Availability is regional.** Organizations: USA, Canada, EU, UK. Individuals
    (solo maintainers): **USA and Canada only**.

- **Traditional OV/EV code-signing certificates** — OV roughly **$150–$300/year**
  (DigiCert, Sectigo, etc.); EV **$400+/year**. Since 2023 the CA/Browser Forum
  requires OV private keys to live in an HSM or hardware token, which is awkward in
  CI. EV no longer buys an instant SmartScreen bypass — it builds reputation like
  OV does, so the premium is rarely justified.
- **Microsoft Store / MSIX** — Microsoft signs the package as part of publishing,
  so there is no certificate cost. (MSI/EXE installers submitted to the Store must
  still be signed by you.)

## Linux

No platform-wide certificate requirement; trust depends on the distribution method.

- Currently `"targets": "all"` in `tauri.conf.json` produces **deb**, **rpm**, and
  **AppImage** on Linux. The repo also ships an AUR `PKGBUILD`. There is no Flatpak
  or Snap manifest today; adding one would be new work.
- Publish **SHA-256 checksums** and a **GPG-signed** release manifest. The release
  workflow currently does neither.
- This is free and is the community-standard baseline.

## Free / open-source options

**[SignPath Foundation](https://signpath.org/)** is the standout: it provides
**free code signing for open-source projects**. They issue the certificate, keep the
private key on their **HSM**, verify that the binary was built from your public
repository, and integrate with CI (GitHub Actions). No personal-identity certificate
purchase required.

Eligibility is **application-based** and reviewed by SignPath — it is not automatic
for any repository with a public license, so treat it as a request rather than a
guarantee. Allow time for approval before planning a release around it.

Other zero-cost routes:

- **Microsoft Store / MSIX** — Microsoft signs the package.
- **Linux packaging** (Flatpak / AppImage / Snap) — no recurring certificate fee.
- **Ad-hoc macOS signing** — free, but still shows the Gatekeeper prompt.

## Recommended next steps

1. **Windows:** apply to **[SignPath Foundation](https://signpath.org/)** (free,
   OSS-eligible, application-based) and wire it into the release workflow.
2. **macOS:** decide between paying **$99/year** for a clean, notarized install, or
   shipping **ad-hoc signed** with clear first-run guidance
   (see `docs/PrepareForMacUser.md`).
3. **Linux:** add **SHA-256 checksums + a GPG-signed** manifest to the release.
4. Add an **opt-in signing step** to `.github/workflows/release.yml` (currently it
   builds all three platforms with **no signing configured**).

### Budget options compared

| Route | Annual cost | Notes |
| --- | --- | --- |
| SignPath Foundation (OSS) | **$0** | Best Windows route if the project qualifies |
| Self-signed / unsigned | **$0** | SmartScreen blocks end users |
| Azure Artifact Signing Basic | **$119.88** | $9.99/mo, 5,000 signatures/mo; needs a paid Azure subscription |
| Traditional OV certificate | **$150–$300** | HSM/token required in CI |
| Azure Artifact Signing Premium | **$1,199.88** | $99.99/mo, 100,000 signatures/mo — overkill here |
| EV certificate | **$400+** | No SmartScreen advantage over OV since 2024 |
| Apple Developer Program | **$99** | Required for notarization |

> **Pricing sources:** Azure Artifact Signing figures come from the
> [Azure product page FAQ](https://azure.microsoft.com/products/artifact-signing) and
> the [Artifact Signing FAQ](https://learn.microsoft.com/azure/artifact-signing/faq);
> certificate and SmartScreen comparisons come from
> [Code signing options for Windows app developers](https://learn.microsoft.com/windows/apps/package-and-deploy/code-signing-options).
> All figures are USD and were verified on **2026-10-03** — re-check before quoting
> them in a funding request, since vendor pricing changes without notice.

> **Publishing note:** this file is registered in `mkdocs.yml`, but **no workflow
> currently builds or deploys the docs site** — `mkdocs` appears only in the optional
> `docs` dependency group in `pyproject.toml`. Until a docs-deploy workflow exists,
> this document is only reachable from the repository itself. See also
> `docs/HostingStrategy.md` for the download-channel plan, and the user-facing
> install note in `distribution/index.html`, which already tells macOS users how to
> work around the Gatekeeper prompt while builds remain unnotarized.

## Appendix: Tauri signing environment variables

Tauri's bundler reads these from the environment (e.g. GitHub Actions secrets):

**macOS** (Developer ID + notarization):

| Variable | Purpose |
| --- | --- |
| `APPLE_CERTIFICATE` | Base64 of the exported `.p12` signing certificate |
| `APPLE_CERTIFICATE_PASSWORD` | Password for the `.p12` |
| `APPLE_SIGNING_IDENTITY` | e.g. `Developer ID Application: Name (TEAMID)` |
| `APPLE_ID` | Apple account email (or use the App Store Connect API key below) |
| `APPLE_PASSWORD` | App-specific password for the Apple ID |
| `APPLE_TEAM_ID` | Apple Developer Team ID |

App Store Connect API alternative: `APPLE_API_ISSUER`, `APPLE_API_KEY`,
`APPLE_API_KEY_PATH`.

**Windows (Azure Artifact Signing):** Tauri does **not** use a separate "signing
action" for this. It invokes the `artifact-signing-cli` tool through the
`bundle.windows.signCommand` config option, which signs the built installers
(`.msi` / `.exe`) as part of `tauri build`.

Prerequisites on the build machine: an Artifact Signing account with a certificate
profile, `.NET` (8+ recommended), the Azure CLI, and `signtool` (Windows 11 SDK
10.0.26100.0 or later recommended).

Install the CLI:

```bash
cargo install artifact-signing-cli
```

Configure the endpoint and profile in `tauri.conf.json` (replace the values with
your own):

```json
{
  "bundle": {
    "windows": {
      "signCommand": "artifact-signing-cli -e https://wus2.codesigning.azure.net -a MyAccount -c MyProfile -d MarkdownReader %1"
    }
  }
}
```

| Flag | Meaning |
| --- | --- |
| `-e` | Endpoint of your Azure Artifact Signing account |
| `-a` | Name of the Artifact Signing account |
| `-c` | Name of the certificate profile inside that account |
| `-d` | Description of the signed content (optional; for `.msi` it becomes the installer name in the UAC prompt) |
| `%1` | The file to sign (injected by Tauri) |

The CLI authenticates using an Entra app registration, passed as GitHub Actions
secrets:

| Variable | Purpose |
| --- | --- |
| `AZURE_CLIENT_ID` | Client ID of the app registration |
| `AZURE_CLIENT_SECRET` | Client secret of the app registration |
| `AZURE_TENANT_ID` | Tenant ID of the Azure directory |

> `signCommand` is also **required** when cross-compiling Windows installers from
> Linux or macOS, because Tauri's default signing implementation only runs on
> Windows machines. The private key never leaves the HSM.

Example opt-in macOS step (only runs when the secret is present):

```yaml
- name: Import Apple certificate
  if: ${{ secrets.APPLE_CERTIFICATE != '' }}
  env:
    KEYCHAIN_PASSWORD: ${{ secrets.KEYCHAIN_PASSWORD }}
    APPLE_CERTIFICATE: ${{ secrets.APPLE_CERTIFICATE }}
    APPLE_CERTIFICATE_PASSWORD: ${{ secrets.APPLE_CERTIFICATE_PASSWORD }}
  run: |
    echo "$APPLE_CERTIFICATE" | base64 --decode > certificate.p12
    security create-keychain -p "$KEYCHAIN_PASSWORD" build.keychain
    security default-keychain -s build.keychain
    security unlock-keychain -p "$KEYCHAIN_PASSWORD" build.keychain
    security import certificate.p12 -k build.keychain \
      -P "$APPLE_CERTIFICATE_PASSWORD" -T /usr/bin/codesign
    security set-key-partition-list -S apple-tool:,apple:,codesign: \
      -s -k "$KEYCHAIN_PASSWORD" build.keychain

- name: Resolve signing identity
  id: cert
  if: ${{ secrets.APPLE_CERTIFICATE != '' }}
  run: |
    CERT_INFO=$(security find-identity -v -p codesigning build.keychain)
    CERT_ID=$(echo "$CERT_INFO" | grep "Developer ID Application" | awk -F'"' '{print $2}')
    echo "cert_id=$CERT_ID" >> "$GITHUB_OUTPUT"

- uses: tauri-apps/tauri-action@v0
  if: ${{ secrets.APPLE_CERTIFICATE != '' }}
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    APPLE_CERTIFICATE: ${{ secrets.APPLE_CERTIFICATE }}
    APPLE_CERTIFICATE_PASSWORD: ${{ secrets.APPLE_CERTIFICATE_PASSWORD }}
    APPLE_SIGNING_IDENTITY: ${{ steps.cert.outputs.cert_id }}
```

> `APPLE_SIGNING_IDENTITY` must be the certificate's SHA-1 fingerprint, not a
> friendly name. The "Resolve signing identity" step reads it out of the keychain and
> exports it as a step output — without that step the identity resolves to an empty
> string and the build fails at signing time. `KEYCHAIN_PASSWORD` must also be
> provided as a secret; it is used to create and unlock the temporary keychain.
>
> Notarization additionally requires `APPLE_API_ISSUER` / `APPLE_API_KEY` /
> `APPLE_API_KEY_PATH` (or the Apple ID trio) to be passed to `tauri-action`.

> Note: this appendix documents the wiring only. Enabling it requires repository
> secrets and (for macOS) a paid Apple Developer account; the release workflow is
> intentionally left unsigned until those are provisioned.

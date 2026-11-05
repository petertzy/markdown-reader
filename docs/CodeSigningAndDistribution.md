# Code Signing & Distribution Trust

> Addresses: [Issue #326](https://github.com/petertzy/markdown-reader/issues/326)

Packaged desktop apps without an appropriate platform signature can trigger operating-system trust warnings —
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

**Research recommendation (not current release configuration):** consider a Windows signing provider, use the optional macOS signing/notarization path when the required credentials are provisioned, and add a GPG signature for the existing Linux checksum files.

## Current repository release status

The statements below were checked against `.github/workflows/release.yml` and `frontend/src-tauri/tauri.conf.json` on **2026-11-04**. They describe repository configuration, not whether a particular release run has valid secrets or completed notarization.

| Area | Current configuration |
| --- | --- |
| Release build matrix | macOS Apple Silicon, Windows x64, and Linux x86_64 |
| macOS | The workflow contains a conditional Apple certificate import and Developer ID identity-resolution step. It runs only when `APPLE_CERTIFICATE` is configured. Apple notarization credentials are passed to the Tauri release action when configured. Verify an individual release run and artifact before calling a build Developer ID signed or notarized. |
| Windows | No Windows signing command or Azure Artifact Signing step is currently configured in the release workflow. |
| Linux | The workflow builds Linux x86_64 bundles and generates/uploads a per-target SHA-256 checksum file. No GPG-signed manifest is currently generated. |
| Tauri bundle settings | The Tauri config includes macOS entitlements. A Windows `bundle.windows.signCommand` is not configured. |

The release workflow and its secrets can change independently of this research document. Check the current workflow and the specific release run before describing an artifact as signed, notarized, or verified.

## macOS

macOS is the one platform where a paid membership is effectively required for a
*warning-free* install.

- **Signing + notarization** requires the **Apple Developer Program ($99/year)**.
  You sign with a **Developer ID Application** certificate and then submit the
  bundle for **notarization**.
- The **free** Apple Developer plan can only be used for local testing/development
  and **cannot notarize**.
- **Ad-hoc signing** is commonly used when no Developer ID signing identity is supplied. It does not remove Gatekeeper warnings. The repository's Tauri configuration includes a macOS entitlements file but does not pin a Developer ID identity. The release workflow has an optional certificate-import and identity-resolution path; see the current repository status below.
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

- The Tauri configuration targets all supported bundle formats. The release workflow currently builds Linux x86_64 artifacts. The repository also ships an AUR `PKGBUILD`; it does not currently include Flatpak or Snap manifests.
- The release workflow generates and uploads a per-target **SHA-256 checksum file**. It does not currently create a GPG-signed release manifest.
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

1. **Windows:** evaluate a signing provider such as [SignPath Foundation](https://signpath.org/) and implement it only after eligibility, secrets, and CI configuration are confirmed.
2. **macOS:** keep the optional certificate/notarization path aligned with the secrets configured for the release workflow, and verify the output of each release run.
3. **Linux:** consider adding a GPG signature for the existing SHA-256 checksum artifacts.
4. Re-check this document whenever `.github/workflows/release.yml` or `frontend/src-tauri/tauri.conf.json` changes.

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
> All figures are USD and were checked on **2026-10-03** — re-check before quoting
> them in a funding request, since vendor pricing changes without notice.

**Documentation publishing note:** the current GitHub Pages workflow deploys the `distribution/` directory, not an MkDocs documentation site. This Markdown reference remains available in the repository; do not infer that a separate documentation website is being built or deployed.

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

> The repository's release workflow resolves the installed **Developer ID Application** identity from the temporary keychain and passes that value to the Tauri release action. Keep the identity-resolution step and the Tauri action's expected identity format aligned when changing this workflow. `KEYCHAIN_PASSWORD` is used to create and unlock the temporary keychain.
>
> Notarization additionally requires `APPLE_API_ISSUER` / `APPLE_API_KEY` /
> `APPLE_API_KEY_PATH` (or the Apple ID trio) to be passed to `tauri-action`.

> The Windows Azure Artifact Signing configuration above is an implementation option, not a currently configured signing step. The current release workflow does not define a Windows `bundle.windows.signCommand`. The optional macOS certificate import and identity-resolution steps are present; the signing/notarization outcome depends on the required repository secrets and Apple credentials.

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
| **Balanced** (notarized macOS + Azure Artifact Signing) | $99 | ~$120 | $0 | **~$220** |
| **Maximum trust** (notarized macOS + OV/EV cert) | $99 | $200–400+ | $0 | **~$300–500** |

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
- **Ad-hoc signing** (`"signingIdentity": "-"` in `tauri.conf.json`) is *required*
  for apps to launch at all on Apple Silicon when downloaded from the internet, but
  it does **not** clear the Gatekeeper prompt.
- There is no reputable free notarization path.

## Windows

Signing reduces (but does not instantly eliminate) SmartScreen warnings — publisher
reputation still has to accrue over time.

- **Azure Artifact Signing** (formerly *Trusted Signing*) — HSM-backed, CI-friendly,
  aimed at small projects and individual developers. Two tiers:
  **Basic = 5,000 signatures/month**, **Premium = 100,000 signatures/month**
  (see the Azure pricing page for the current monthly fee per tier).
- **Traditional OV/EV code-signing certificates** — typically **$200–$400+/year**;
  EV certificates also require a hardware token/HSM, which is awkward in CI.
- **Microsoft Store / MSIX** — Microsoft signs the package as part of publishing,
  so there is no certificate cost.

## Linux

No platform-wide certificate requirement; trust depends on the distribution method.

- Distribute via **Flatpak**, **AppImage**, or **Snap**.
- Publish **SHA-256 checksums** and a **GPG-signed** release manifest.
- This is free and is the community-standard baseline.

## Free / open-source options

**SignPath Foundation** is the standout: it provides **free code signing for open-source
projects**. They issue the certificate, keep the private key on their **HSM**, verify
that the binary was built from your public repository, and integrate with CI
(GitHub Actions). No personal-identity certificate purchase required.

Other zero-cost routes:

- **Microsoft Store / MSIX** — Microsoft signs the package.
- **Linux packaging** (Flatpak / AppImage / Snap) — no recurring certificate fee.
- **Ad-hoc macOS signing** — free, but still shows the Gatekeeper prompt.

## Recommended next steps

1. **Windows:** apply to **SignPath Foundation** (free, OSS-eligible) and wire it into
   the release workflow.
2. **macOS:** decide between paying **$99/year** for a clean, notarized install, or
   shipping **ad-hoc signed** with clear first-run guidance
   (see `docs/PrepareForMacUser.md`).
3. **Linux:** add **SHA-256 checksums + a GPG-signed** manifest to the release.
4. Add an **opt-in signing step** to `.github/workflows/release.yml` (currently it
   builds all three platforms with **no signing configured**).

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

**Windows (Azure Artifact Signing):** configure the signing account/endpoint and
certificate profile via the Azure signing action; the private key never leaves the
HSM.

Example opt-in macOS step (only runs when the secret is present):

```yaml
- name: Import Apple certificate
  if: ${{ env.APPLE_CERTIFICATE != '' }}
  env:
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

- uses: tauri-apps/tauri-action@v0
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    APPLE_CERTIFICATE: ${{ secrets.APPLE_CERTIFICATE }}
    APPLE_CERTIFICATE_PASSWORD: ${{ secrets.APPLE_CERTIFICATE_PASSWORD }}
    APPLE_SIGNING_IDENTITY: ${{ env.CERT_ID }}
```

> Note: this appendix documents the wiring only. Enabling it requires repository
> secrets and (for macOS) a paid Apple Developer account; the release workflow is
> intentionally left unsigned until those are provisioned.

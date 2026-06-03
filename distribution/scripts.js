document.addEventListener('DOMContentLoaded', () => {
    const repo = 'petertzy/markdown-reader';
    const releasesUrl = `https://github.com/${repo}/releases/latest`;
    const apiUrl = `https://api.github.com/repos/${repo}/releases/latest`;

    const platformMatchers = {
        'mac-arm': [
            {
                label: 'Download DMG',
                test: name => isMac(name) && isArm(name) && name.endsWith('.dmg')
            },
            {
                label: 'Download App',
                test: name => isMac(name) && isArm(name) && (name.endsWith('.zip') || name.endsWith('.tar.gz'))
            }
        ],
        'mac-intel': [
            {
                label: 'Download DMG',
                test: name => isMac(name) && isIntel(name) && name.endsWith('.dmg')
            },
            {
                label: 'Download App',
                test: name => isMac(name) && isIntel(name) && (name.endsWith('.zip') || name.endsWith('.tar.gz'))
            }
        ],
        windows: [
            {
                label: 'Download MSI',
                test: name => isWindows(name) && name.endsWith('.msi')
            },
            {
                label: 'Download EXE',
                test: name => isWindows(name) && name.endsWith('.exe')
            }
        ],
        linux: [
            {
                label: 'Download AppImage',
                test: name => isLinux(name) && name.endsWith('.appimage')
            },
            {
                label: 'Download DEB',
                test: name => isLinux(name) && name.endsWith('.deb')
            },
            {
                label: 'Download RPM',
                test: name => isLinux(name) && name.endsWith('.rpm')
            }
        ]
    };

    updateDownloadCards(apiUrl, releasesUrl, platformMatchers);

    // Reveal animations on scroll
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const revealObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('active');
                revealObserver.unobserve(entry.target);
            }
        });
    }, observerOptions);

    document.querySelectorAll('.reveal').forEach(el => {
        revealObserver.observe(el);
    });

    // Smooth scroll for navigation links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                window.scrollTo({
                    top: target.offsetTop - 80,
                    behavior: 'smooth'
                });
            }
        });
    });

    // Add scroll class to navbar
    const nav = document.querySelector('nav');
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            nav.style.padding = '1rem 10%';
            nav.style.background = 'rgba(10, 10, 12, 0.95)';
        } else {
            nav.style.padding = '2rem 10%';
            nav.style.background = 'rgba(10, 10, 12, 0.8)';
        }
    });
});

function isMac(name) {
    return /mac|darwin|apple|\.dmg$|\.app\.tar\.gz$/.test(name);
}

function isArm(name) {
    return /aarch64|arm64|apple-silicon/.test(name);
}

function isIntel(name) {
    return /x86_64|x64|amd64|intel/.test(name);
}

function isWindows(name) {
    return /windows|win32|win64|msvc|pc-windows|\.msi$|\.exe$/.test(name);
}

function isLinux(name) {
    return /linux|unknown-linux|appimage|\.deb$|\.rpm$/.test(name);
}

async function updateDownloadCards(apiUrl, releasesUrl, platformMatchers) {
    try {
        const response = await fetch(apiUrl, {
            headers: {
                Accept: 'application/vnd.github+json'
            }
        });

        if (!response.ok) {
            throw new Error(`GitHub Releases returned ${response.status}`);
        }

        const release = await response.json();
        const assets = Array.isArray(release.assets) ? release.assets : [];
        const releaseLink = document.getElementById('release-link');
        const releaseVersion = document.getElementById('release-version');

        if (releaseVersion) {
            releaseVersion.textContent = release.name || release.tag_name || 'Latest release';
        }

        if (releaseLink && release.html_url) {
            releaseLink.href = release.html_url;
        }

        Object.entries(platformMatchers).forEach(([platform, matchers]) => {
            const matchedAssets = selectAssets(assets, matchers);
            const card = document.querySelector(`[data-platform-card="${platform}"]`);
            updateCard(card, matchedAssets, release.html_url || releasesUrl);
        });
    } catch (error) {
        document.querySelectorAll('[data-platform-card]').forEach(card => {
            updateCard(card, [], releasesUrl);
        });
    }
}

function selectAssets(assets, matchers) {
    return matchers
        .map(matcher => {
            const asset = assets.find(candidate => matcher.test(candidate.name.toLowerCase()));
            return asset ? { label: matcher.label, asset } : null;
        })
        .filter(Boolean);
}

function updateCard(card, matchedAssets, fallbackUrl) {
    if (!card) {
        return;
    }

    const badge = card.querySelector('.badge');
    const actions = card.querySelector('[data-download-actions]');

    if (!badge || !actions) {
        return;
    }

    actions.innerHTML = '';

    if (matchedAssets.length > 0) {
        badge.className = 'badge badge-available';
        badge.textContent = 'Available Now';

        matchedAssets.forEach(({ label, asset }) => {
            const link = document.createElement('a');
            link.className = 'btn btn-secondary';
            link.href = asset.browser_download_url;
            link.textContent = label;
            actions.appendChild(link);
        });
        return;
    }

    badge.className = 'badge badge-manual';
    badge.textContent = 'Check Release';

    const link = document.createElement('a');
    link.className = 'btn btn-secondary';
    link.href = fallbackUrl;
    link.textContent = 'View Downloads';
    actions.appendChild(link);
}

// CSS for reveal animation (injected if not in styles.css)
const style = document.createElement('style');
style.textContent = `
    .reveal {
        opacity: 0;
        transform: translateY(30px);
        transition: all 0.8s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .reveal.active {
        opacity: 1;
        transform: translateY(0);
    }
    .hero h1.reveal { transition-delay: 0.1s; }
    .hero p.reveal { transition-delay: 0.2s; }
    .cta-group.reveal { transition-delay: 0.3s; }
    .hero-mockup.reveal { transition-delay: 0.4s; }
`;
document.head.appendChild(style);

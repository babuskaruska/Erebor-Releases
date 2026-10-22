"""Make an Erebor client release for the launcher (decision 500).

usage: python tools/release/make_release.py 1.0.1 [--update-jre]
  1. In IntelliJ: Gradle runelite > runelite-client > Tasks > shadow > shadowJar, and erebor-launcher > Tasks > build > jar.
  2. Run this script with the new version number. It copies the two jars into tools/release/out/v<version>/ and writes the
     manifest erebor.properties (the client's SHA-256 and size, the server host, the Java runtimes).
  3. Upload the three files as a new release v<version> of github.com/babuskaruska/Erebor-Releases (public), marked latest.
     Every launcher updates on its next start. Erebor.jar only changes when the launcher itself changes.
Settings: release.properties next to this file (host, jvm.args, client.args, java.local). The Java runtimes (Temurin 11 JRE,
from Adoptium's GitHub releases) are pinned in jre.properties; --update-jre fetches the newest 11 from the Adoptium API.
"""
import hashlib, json, os, shutil, sys, urllib.request

REPO = "babuskaruska/Erebor-Releases"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RUNELITE = os.path.join(ROOT, "Kronos-master", "runelite")
CLIENT_LIBS = os.path.join(RUNELITE, "runelite-client", "build", "libs")
LAUNCHER_JAR = os.path.join(RUNELITE, "erebor-launcher", "build", "libs", "Erebor.jar")
# launcher platform key -> Adoptium os, architecture (no Mac: the client ships no Mac OpenGL natives)
PLATFORMS = {"windows-x64": ("windows", "x64"), "windows-x86": ("windows", "x32"), "linux-x64": ("linux", "x64")}


def read_props(path):
    props = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    props[k.strip()] = v.strip()
    return props


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def update_jre(path):
    lines = ["# Temurin 11 JRE per launcher platform, from api.adoptium.net (make_release.py --update-jre)"]
    for key, (os_name, arch) in PLATFORMS.items():
        url = ("https://api.adoptium.net/v3/assets/latest/11/hotspot?image_type=jre&vendor=eclipse"
               f"&os={os_name}&architecture={arch}")
        req = urllib.request.Request(url, headers={"User-Agent": "Erebor-Release/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            assets = json.loads(r.read().decode("utf-8"))
        if not assets:
            sys.exit(f"Adoptium has no JRE 11 for {key}")
        pkg = assets[0]["binary"]["package"]
        lines += [f"# {assets[0]['release_name']} {pkg['name']}", f"jre.{key}.url={pkg['link']}",
                  f"jre.{key}.sha256={pkg['checksum']}", f"jre.{key}.size={pkg['size']}"]
        print(f"{key}: {pkg['name']}")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        sys.exit(__doc__)
    version = args[0].lstrip("v")
    jre_path = os.path.join(HERE, "jre.properties")
    if "--update-jre" in sys.argv or not os.path.isfile(jre_path):
        update_jre(jre_path)
    settings = read_props(os.path.join(HERE, "release.properties"))
    if not settings.get("host"):
        sys.exit("release.properties has no host: set the live server's address first (players would connect to 127.0.0.1)")

    shaded = [f for f in os.listdir(CLIENT_LIBS) if f.endswith("-shaded.jar")] if os.path.isdir(CLIENT_LIBS) else []
    if len(shaded) != 1:
        sys.exit(f"Expected one *-shaded.jar in {CLIENT_LIBS} (run shadowJar), found {shaded}")
    if not os.path.isfile(LAUNCHER_JAR):
        sys.exit(f"Missing {LAUNCHER_JAR} (run erebor-launcher's jar task)")

    out = os.path.join(HERE, "out", "v" + version)
    os.makedirs(out, exist_ok=True)
    client = os.path.join(out, "erebor-client.jar")
    shutil.copyfile(os.path.join(CLIENT_LIBS, shaded[0]), client)
    shutil.copyfile(LAUNCHER_JAR, os.path.join(out, "Erebor.jar"))

    manifest = [
        f"# Erebor {version}: read by the launcher (net.erebor.launcher.Launcher)",
        f"version={version}",
        f"client.url=https://github.com/{REPO}/releases/download/v{version}/erebor-client.jar",
        f"client.sha256={sha256(client)}",
        f"client.size={os.path.getsize(client)}",
        f"host={settings['host']}",
        f"jvm.args={settings.get('jvm.args', '')}",
        f"client.args={settings.get('client.args', '')}",
        f"java.local={settings.get('java.local', '11')}",
    ]
    with open(jre_path, encoding="utf-8") as f:
        manifest += [line.rstrip("\n") for line in f if line.startswith("jre.")]
    with open(os.path.join(out, "erebor.properties"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(manifest) + "\n")

    print(f"\nRelease files in {out}:")
    for name in ("erebor-client.jar", "Erebor.jar", "erebor.properties"):
        print(f"  {name}  {os.path.getsize(os.path.join(out, name)):,} bytes")
    print(f"\nNext: https://github.com/{REPO}/releases/new  tag v{version}, attach the three files, 'Set as the latest release', Publish.")


if __name__ == "__main__":
    main()

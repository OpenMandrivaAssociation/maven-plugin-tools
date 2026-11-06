Name:		maven-plugin-tools
Version:	3.15.2
Release:	1
Summary:	Maven plugin descriptor generator
Group:		Development/Java
License:	ASL 2.0
URL:		https://maven.apache.org/plugin-tools/
Source0:	https://github.com/apache/maven-plugin-tools/archive/refs/tags/maven-plugin-tools-%{version}.tar.gz#/maven-plugin-tools-%{version}.tar.gz
Source1:	stage0-maven-plugin-plugin.xml
BuildArch:	noarch

# Packaging maven-plugin runs maven-plugin-plugin:descriptor. This package
# is that plugin, so the goal comes from the stage-0 jar and is told to
# keep the descriptor already in the sources. The metadata lists only that
# jar and the modules it loads.
%define sysjar_bootstrap_root %{builddir}/maven-plugin-tools-maven-plugin-tools-%{version}/plugin-bootstrap

BuildRequires:	python
BuildRequires:	maven
BuildRequires:	java-current-devel
BuildRequires:	javapackages-bootstrap
# Provided scope still has to be on the compile classpath.
BuildRequires:	mvn(org.apache.maven:maven-core)
BuildRequires:	mvn(com.google.inject:guice-parent:pom::)
BuildRequires:	mvn(org.slf4j:slf4j-parent:pom::)
BuildRequires:	mvn(org.codehaus.plexus:plexus-containers:pom::)
# The installed jars still point at these parents. sysjar rewrites the
# requested version once the parent POM is installed.
BuildRequires:	mvn(org.codehaus.plexus:plexus:pom::)
BuildRequires:	mvn(org.apache.maven:maven-parent:pom::)
BuildRequires:	mvn(org.apache.commons:commons-parent:pom::)
BuildRequires:	mvn(org.apache.maven.shared:maven-shared-components:pom::)
BuildRequires:	mvn(org.apache.httpcomponents:httpcomponents-parent:pom::)
BuildRequires:	mvn(org.apache.maven:maven-model)
BuildRequires:	mvn(org.apache.maven:maven-plugin-api)
BuildRequires:	mvn(org.apache.maven:maven-artifact)
BuildRequires:	mvn(org.apache.maven:maven-settings)
BuildRequires:	mvn(org.apache.maven:maven-repository-metadata)
BuildRequires:	mvn(org.apache.maven.resolver:maven-resolver-api)
BuildRequires:	mvn(org.apache.maven.resolver:maven-resolver-util)
BuildRequires:	mvn(org.apache.maven.plugin-tools:maven-plugin-annotations)
BuildRequires:	mvn(org.apache.maven.reporting:maven-reporting-api)
BuildRequires:	mvn(org.slf4j:slf4j-api)
BuildRequires:	mvn(javax.inject:javax.inject)
BuildRequires:	mvn(org.codehaus.plexus:plexus-classworlds)
BuildRequires:	mvn(org.codehaus.plexus:plexus-utils)
BuildRequires:	mvn(org.codehaus.plexus:plexus-java)
BuildRequires:	mvn(org.codehaus.plexus:plexus-archiver)
BuildRequires:	mvn(org.codehaus.plexus:plexus-velocity)
BuildRequires:	mvn(org.apache.velocity:velocity-engine-core)
BuildRequires:	mvn(org.apache.httpcomponents:httpclient)
BuildRequires:	mvn(org.apache.httpcomponents:httpcore)
BuildRequires:	mvn(org.apache.maven.wagon:wagon-provider-api)
BuildRequires:	mvn(org.jsoup:jsoup)
BuildRequires:	mvn(com.thoughtworks.qdox:qdox)
BuildRequires:	mvn(org.ow2.asm:asm) >= 9
BuildRequires:	mvn(org.ow2.asm:asm-util) >= 9
BuildRequires:	mvn(org.eclipse.sisu:org.eclipse.sisu.plexus)
BuildRequires:	mvn(org.sonatype.plexus:plexus-build-api)
BuildSystem:	maven

%description
Extracts Maven plugin descriptors from Mojo annotations and writes
plugin.xml. This package ships the api, the generators, the annotations
extractor and the plugin. The java, ant and beanshell extractors are
not built. Javadoc HTML is cleaned with jsoup.

%prep
%autosetup -n maven-plugin-tools-maven-plugin-tools-%{version}
mkdir -p plugin-bootstrap/usr/share/javapackages-bootstrap/maven-metadata
cp -f %{SOURCE1} plugin-bootstrap/usr/share/javapackages-bootstrap/maven-metadata/maven-plugin-plugin.xml
python - <<'PY'
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

NS = "http://maven.apache.org/POM/4.0.0"
ET.register_namespace("", NS)
KEEP_MODULES = (
    "maven-plugin-tools-api",
    "maven-plugin-tools-generators",
    "maven-plugin-tools-annotations",
    "maven-plugin-plugin",
)
DROP_ARTIFACTS = {
    "plexus-xml",
    "maven-plugin-tools-java",
    "maven-plugin-tools-ant",
    "maven-plugin-tools-beanshell",
    "maven-script-ant",
    "maven-script-beanshell",
    "jtidy",
}


def q(name):
    return "{" + NS + "}" + name


def local(tag):
    return tag.rsplit("}", 1)[-1]


def kids(node, name):
    if node is None:
        return []
    return [child for child in list(node) if local(child.tag) == name]


def one(node, name):
    found = kids(node, name)
    return found[0] if found else None


def text_of(node, name):
    child = one(node, name)
    return (child.text or "").strip() if child is not None else ""


def set_text(node, name, value):
    child = one(node, name)
    if child is None:
        child = ET.SubElement(node, q(name))
    child.text = value
    return child


def parse(path):
    tree = ET.parse(path)
    return tree, tree.getroot()


def write(tree, path):
    tree.write(path, encoding="utf-8", xml_declaration=True)


def drop_deps(root):
    for deps in root.iter(q("dependencies")):
        for dep in list(deps):
            if local(dep.tag) != "dependency":
                continue
            if text_of(dep, "artifactId") in DROP_ARTIFACTS:
                deps.remove(dep)
            elif text_of(dep, "artifactId") == "plexus-build-api":
                set_text(dep, "version", "1.2.0")


def retarget_managed(root):
    versions = {
        "plexus-archiver": "4.4.0",
        "plexus-velocity": "2.2.0",
        "qdox": "2.1.0",
    }
    for dep in root.iter(q("dependency")):
        artifact = text_of(dep, "artifactId")
        if artifact in versions and one(dep, "version") is not None:
            set_text(dep, "version", versions[artifact])


def rewrite_root(path):
    tree, root = parse(path)
    for child in list(root):
        if local(child.tag) == "parent":
            root.remove(child)
    props = one(root, "properties")
    if props is None:
        props = ET.SubElement(root, q("properties"))
    values = {
        "maven3Version": "3.10.0",
        "resolverVersion": "2.0.24",
        "plexusUtilsVersion": "3.6.0",
        "asmVersion": "9.11.1",
        "maven.compiler.release": "8",
        "project.build.sourceEncoding": "UTF-8",
    }
    for name, value in values.items():
        set_text(props, name, value)
    modules = one(root, "modules")
    for child in list(modules):
        modules.remove(child)
    for name in KEEP_MODULES:
        node = ET.SubElement(modules, q("module"))
        node.text = name
    build = one(root, "build")
    if build is not None:
        root.remove(build)
    profiles = one(root, "profiles")
    if profiles is not None:
        root.remove(profiles)
    drop_deps(root)
    retarget_managed(root)
    write(tree, path)


def strip_extra(root):
    # Rat, enforcer, sisu-indexer, source jars and the site report are not
    # part of this build. The default lifecycle still runs compiler, resources
    # and jar. A filtered components.xml would ship unresolved properties.
    for name in ("build", "profiles", "reporting"):
        node = one(root, name)
        if node is not None:
            root.remove(node)


def add_skip_descriptor(root):
    build = ET.SubElement(root, q("build"))
    plugins = ET.SubElement(build, q("plugins"))
    plugin = ET.SubElement(plugins, q("plugin"))
    set_text(plugin, "groupId", "org.apache.maven.plugins")
    set_text(plugin, "artifactId", "maven-plugin-plugin")
    configuration = ET.SubElement(plugin, q("configuration"))
    set_text(configuration, "skipDescriptor", "true")


def skip_descriptor(path):
    tree, root = parse(path)
    strip_extra(root)
    add_skip_descriptor(root)
    filtered = path.parent / "src" / "main" / "filtered-resources"
    if filtered.is_dir():
        shutil.rmtree(filtered)
    drop_deps(root)
    write(tree, path)


def rewrite_module(path):
    tree, root = parse(path)
    strip_extra(root)
    drop_deps(root)
    retarget_managed(root)
    write(tree, path)


def patch_generator_utils(path):
    text = path.read_text(encoding="utf-8")
    drop_imports = (
        "import javax.swing.text.MutableAttributeSet;\n",
        "import javax.swing.text.html.HTML;\n",
        "import javax.swing.text.html.HTMLEditorKit;\n",
        "import javax.swing.text.html.parser.ParserDelegator;\n",
        "import java.io.ByteArrayInputStream;\n",
        "import java.io.ByteArrayOutputStream;\n",
        "import java.io.StringReader;\n",
        "import java.nio.charset.StandardCharsets;\n",
        "import java.util.Stack;\n",
        "import org.w3c.tidy.Tidy;\n",
    )
    for line in drop_imports:
        text = text.replace(line, "")
    if "import org.jsoup.Jsoup;" not in text:
        text = text.replace(
            "import org.apache.maven.artifact.Artifact;\n",
            "import org.apache.maven.artifact.Artifact;\nimport org.jsoup.Jsoup;\nimport org.jsoup.nodes.Document;\n",
        )
    start = text.find("    public static String makeHtmlValid(")
    to_text = text.find("    /**\n     * Converts a HTML fragment")
    discover = text.find("    /**\n     * Find the best package name")
    if start < 0 or to_text < 0 or discover < 0:
        raise SystemExit("GeneratorUtils markers were not found")
    replacement = """    public static String makeHtmlValid(String description) {
        if (description == null || description.isEmpty()) {
            return "";
        }
        Document document = Jsoup.parseBodyFragment(decodeJavadocTags(description));
        document.outputSettings().syntax(Document.OutputSettings.Syntax.xml);
        return document.body().html();
    }

"""
    text = text[:start] + replacement + text[discover:]
    if "IOException" not in text.split("import java.io.IOException;", 1)[-1]:
        text = text.replace("import java.io.IOException;\n", "")
    path.write_text(text, encoding="utf-8")


def sisu_index(module):
    root = module / "src" / "main" / "java"
    if not root.is_dir():
        return
    names = []
    for path in sorted(root.rglob("*.java")):
        source = path.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"\b(?:class|interface|enum)\s+([A-Za-z0-9_]+)", source)
        if not match or "@Named" not in source[: match.start()]:
            continue
        package = re.search(r"(?m)^package\s+([A-Za-z0-9_.]+)\s*;", source)
        if package:
            names.append(package.group(1) + "." + match.group(1))
    if not names:
        return
    dest = module / "src" / "main" / "resources" / "META-INF" / "sisu"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "javax.inject.Named").write_text("\n".join(names) + "\n", encoding="utf-8")


def ann_args(block):
    found = {}
    for key in ("name", "defaultPhase", "requiresDependencyResolution", "threadSafe", "defaultValue", "property", "alias", "readonly"):
        match = re.search(key + r'\s*=\s*("(?:[^"\\]|\\.)*"|[^,\s)]+)', block)
        if not match:
            continue
        value = match.group(1).strip()
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            value = value[1:-1]
        if value == "VALUE_AUTO":
            value = "auto"
        found[key] = value
    return found


def parameters_of(path):
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    params = []
    for match in re.finditer(r"@Parameter\b(\([^)]*\))?", text):
        block = match.group(1) or ""
        rest = text[match.end() : match.end() + 400]
        field = re.search(
            r"(?:(?:private|protected|public)\s+)?(?:static\s+)?(?:final\s+)?([A-Za-z0-9_.<>,?]+)\s+([A-Za-z0-9_]+)\s*[=;]",
            rest,
        )
        if not field:
            continue
        java_type, name = field.group(1).strip(), field.group(2)
        if "<" in java_type:
            outer = java_type.split("<", 1)[0]
        else:
            outer = java_type
        boxed = {
            "String": "java.lang.String",
            "boolean": "boolean",
            "Boolean": "java.lang.Boolean",
            "File": "java.io.File",
            "List": "java.util.List",
            "Set": "java.util.Set",
            "URI": "java.net.URI",
            "int": "int",
        }.get(outer, outer)
        args = ann_args(block)
        params.append(
            {
                "name": name,
                "type": boxed,
                "default": args.get("defaultValue"),
                "property": args.get("property"),
                "alias": args.get("alias"),
                "editable": "false" if args.get("readonly") == "true" else "true",
            }
        )
    return params


def mojos(directory):
    abstract = next(directory.rglob("AbstractGeneratorMojo.java"))
    abstract_params = parameters_of(abstract)
    found = []
    for path in sorted(directory.rglob("*.java")):
        text = path.read_text(encoding="utf-8")
        match = re.search(r"@Mojo\s*\((.*?)\)\s*(?:public\s+)?class\s+(\S+)", text, re.S)
        if not match:
            continue
        args = ann_args(match.group(1))
        phase = args.get("defaultPhase", "")
        if "." in phase:
            phase = phase.split(".")[-1]
        phase = phase.lower().replace("_", "-")
        scope = args.get("requiresDependencyResolution", "")
        scope = {
            "ResolutionScope.COMPILE": "compile",
            "ResolutionScope.COMPILE_PLUS_RUNTIME": "compile+runtime",
            "ResolutionScope.RUNTIME": "runtime",
            "ResolutionScope.TEST": "test",
        }.get(scope, "")
        package = re.search(r"(?m)^package\s+([A-Za-z0-9_.]+)\s*;", text).group(1)
        own = parameters_of(path)
        names = {item["name"] for item in own}
        inherited = []
        if "extends AbstractGeneratorMojo" in text:
            inherited = [item for item in abstract_params if item["name"] not in names]
        found.append(
            {
                "goal": args["name"],
                "phase": phase,
                "resolution": scope,
                "thread": args.get("threadSafe", "false"),
                "implementation": package + "." + match.group(2),
                "parameters": inherited + own,
            }
        )
    return found


def xml_attr(value):
    return escape(value, {'"': "&quot;"})


def write_plugin_xml(plugin_dir, version):
    items = mojos(plugin_dir / "src" / "main" / "java")
    if len(items) != 3:
        raise SystemExit("expected 3 mojos, found " + str(len(items)))
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<plugin>",
        "  <name>Maven Plugin Plugin</name>",
        "  <description>Generates Maven plugin descriptors.</description>",
        "  <groupId>org.apache.maven.plugins</groupId>",
        "  <artifactId>maven-plugin-plugin</artifactId>",
        "  <version>" + version + "</version>",
        "  <goalPrefix>plugin</goalPrefix>",
        "  <isolatedRealm>false</isolatedRealm>",
        "  <inheritedByDefault>true</inheritedByDefault>",
        "  <mojos>",
    ]
    for mojo in items:
        lines.append("    <mojo>")
        lines.append("      <goal>" + xml_attr(mojo["goal"]) + "</goal>")
        if mojo["resolution"]:
            lines.append("      <requiresDependencyResolution>" + mojo["resolution"] + "</requiresDependencyResolution>")
        lines.append("      <requiresDirectInvocation>false</requiresDirectInvocation>")
        lines.append("      <requiresProject>true</requiresProject>")
        lines.append("      <requiresReports>false</requiresReports>")
        lines.append("      <aggregator>false</aggregator>")
        lines.append("      <requiresOnline>false</requiresOnline>")
        lines.append("      <inheritedByDefault>true</inheritedByDefault>")
        if mojo["phase"]:
            lines.append("      <phase>" + mojo["phase"] + "</phase>")
        lines.append("      <implementation>" + mojo["implementation"] + "</implementation>")
        lines.append("      <language>java</language>")
        lines.append("      <instantiationStrategy>per-lookup</instantiationStrategy>")
        lines.append("      <executionStrategy>once-per-session</executionStrategy>")
        lines.append("      <threadSafe>" + mojo["thread"] + "</threadSafe>")
        lines.append("      <parameters>")
        for param in mojo["parameters"]:
            lines.append("        <parameter>")
            lines.append("          <name>" + param["name"] + "</name>")
            if param["alias"]:
                lines.append("          <alias>" + param["alias"] + "</alias>")
            lines.append("          <type>" + param["type"] + "</type>")
            lines.append("          <required>false</required>")
            lines.append("          <editable>" + param["editable"] + "</editable>")
            lines.append("          <description></description>")
            lines.append("        </parameter>")
        lines.append("      </parameters>")
        lines.append("      <configuration>")
        for param in mojo["parameters"]:
            if not param["default"] and not param["property"]:
                continue
            attrs = ' implementation="' + param["type"] + '"'
            if param["default"]:
                attrs += ' default-value="' + xml_attr(param["default"]) + '"'
            body = "${" + param["property"] + "}" if param["property"] else ""
            if body:
                lines.append("        <" + param["name"] + attrs + ">" + body + "</" + param["name"] + ">")
            else:
                lines.append("        <" + param["name"] + attrs + "/>")
        lines.append("      </configuration>")
        lines.append("    </mojo>")
    lines.append("  </mojos>")
    lines.append("</plugin>")
    dest = plugin_dir / "src" / "main" / "resources" / "META-INF" / "maven"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "plugin.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    root = Path(".")
    for name in (
        "maven-plugin-annotations",
        "maven-plugin-report-plugin",
        "maven-plugin-tools-java",
        "maven-script",
    ):
        path = root / name
        if path.exists():
            shutil.rmtree(path)
    rewrite_root(root / "pom.xml")
    for name in KEEP_MODULES:
        module = root / name
        if name == "maven-plugin-plugin":
            skip_descriptor(module / "pom.xml")
            write_plugin_xml(module, "3.15.2")
        else:
            rewrite_module(module / "pom.xml")
        sisu_index(module)
    patch_generator_utils(
        root
        / "maven-plugin-tools-generators"
        / "src"
        / "main"
        / "java"
        / "org"
        / "apache"
        / "maven"
        / "tools"
        / "plugin"
        / "generator"
        / "GeneratorUtils.java"
    )


if __name__ == "__main__":
    main()
PY

%files -f .mfiles
%doc LICENSE NOTICE README.md

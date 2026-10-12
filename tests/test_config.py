import logging

from harbor.core.config import HarborConfig

CADDY = """
ingress: caddy
backends:
  caddy:
    kind: caddy
    url: unix:///run/caddy/admin.socket
"""

ENVOY = """
backends:
  envoy:
    kind: envoy
    url: /run/harbor
    options:
      listener-port: 10000
    features:
      - authz
      - transcoder
"""


def write_config(tmp_path, text=CADDY):
    path = tmp_path / "harbor.yaml"
    path.write_text(text)
    return str(path)


def test_from_file_without_backends_dir(tmp_path):
    config = HarborConfig.from_file(write_config(tmp_path))

    assert list(config.backends) == ["caddy"]


def test_from_file_adds_backends_from_backends_d(tmp_path):
    (tmp_path / "backends.d").mkdir()
    (tmp_path / "backends.d" / "envoy.yaml").write_text(ENVOY)

    config = HarborConfig.from_file(write_config(tmp_path))

    assert list(config.backends) == ["caddy", "envoy"]
    envoy = config.backends["envoy"]
    assert envoy.kind == "envoy"
    assert envoy.options == {"listener-port": 10000}
    assert envoy.features == ["authz", "transcoder"]
    assert config.ingress == "caddy"


def test_from_file_ignores_other_files_in_backends_d(tmp_path):
    (tmp_path / "backends.d").mkdir()
    (tmp_path / "backends.d" / "envoy.yaml.dpkg-new").write_text(ENVOY)
    (tmp_path / "backends.d" / "README").write_text("not a fragment")

    config = HarborConfig.from_file(write_config(tmp_path))

    assert list(config.backends) == ["caddy"]


def test_from_file_ignores_empty_fragment(tmp_path):
    (tmp_path / "backends.d").mkdir()
    (tmp_path / "backends.d" / "empty.yaml").write_text("")

    config = HarborConfig.from_file(write_config(tmp_path))

    assert list(config.backends) == ["caddy"]


def test_from_file_fragments_load_in_name_order(tmp_path, caplog):
    (tmp_path / "backends.d").mkdir()
    (tmp_path / "backends.d" / "20-envoy.yaml").write_text(
        ENVOY.replace("/run/harbor", "/run/second")
    )
    (tmp_path / "backends.d" / "10-envoy.yaml").write_text(ENVOY)

    with caplog.at_level(logging.WARNING):
        config = HarborConfig.from_file(write_config(tmp_path))

    assert config.backends["envoy"].url == "/run/second"
    assert "replaces an earlier definition" in caplog.text


def test_from_file_fragment_replaces_backend_from_main_file(tmp_path):
    (tmp_path / "backends.d").mkdir()
    (tmp_path / "backends.d" / "envoy.yaml").write_text(ENVOY)

    config = HarborConfig.from_file(
        write_config(
            tmp_path, CADDY + "  envoy:\n    kind: envoy\n    url: /run/envoy\n"
        )
    )

    assert config.backends["envoy"].url == "/run/harbor"


def test_from_file_custom_backends_dir(tmp_path):
    fragments = tmp_path / "elsewhere"
    fragments.mkdir()
    (fragments / "envoy.yaml").write_text(ENVOY)
    (tmp_path / "backends.d").mkdir()
    (tmp_path / "backends.d" / "other.yaml").write_text(
        ENVOY.replace("envoy:", "other:")
    )

    config = HarborConfig.from_file(
        write_config(tmp_path, CADDY + f"backends_dir: {fragments.as_posix()}\n")
    )

    assert list(config.backends) == ["caddy", "envoy"]

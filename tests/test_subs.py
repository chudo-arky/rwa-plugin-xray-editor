import base64
import json

import pytest

from rwa_xray_editor import subs


@pytest.mark.asyncio
async def test_list_sorted_by_position(ctx, panel):
    panel.templates = [
        {"uuid": "b", "name": "B", "templateType": "MIHOMO", "viewPosition": 2},
        {"uuid": "a", "name": "A", "templateType": "XRAY_JSON", "viewPosition": 1},
    ]
    r = await subs.list_templates(ctx)
    assert [i["uuid"] for i in r["items"]] == ["a", "b"]
    assert r["items"][0]["type"] == "XRAY_JSON"


@pytest.mark.asyncio
async def test_get_yaml_is_decoded_from_base64(ctx, panel):
    yaml = "proxies:\n  - name: x\n"
    panel.template = {"uuid": "u", "name": "n", "templateType": "MIHOMO",
                      "encodedTemplateYaml": base64.b64encode(yaml.encode()).decode()}
    r = await subs.get_template(ctx, "u")
    assert r["format"] == "yaml" and r["text"] == yaml


@pytest.mark.asyncio
async def test_get_json_is_pretty_printed(ctx, panel):
    panel.template = {"uuid": "u", "name": "n", "templateType": "XRAY_JSON", "templateJson": {"log": {}}}
    r = await subs.get_template(ctx, "u")
    assert r["format"] == "json" and json.loads(r["text"]) == {"log": {}}


@pytest.mark.asyncio
async def test_save_routes_to_the_right_field(ctx, panel):
    await subs.save_template(ctx, "u", "CLASH", "a: 1\n")
    uuid, kw = panel.updated[-1]
    assert uuid == "u" and base64.b64decode(kw["encoded_template_yaml"]) == b"a: 1\n"
    await subs.save_template(ctx, "u", "XRAY_JSON", '{"log": {}}')
    assert panel.updated[-1][1] == {"template_json": {"log": {}}}


@pytest.mark.asyncio
async def test_save_invalid_json_does_not_hit_panel(ctx, panel):
    r = await subs.save_template(ctx, "u", "XRAY_JSON", "{oops")
    assert "JSON" in r["error"] and panel.updated == []


@pytest.mark.asyncio
async def test_panel_errors_are_sanitized(ctx, panel):
    panel.fail = RuntimeError("502 from http://10.0.0.2:3005/api/templates")
    assert "10.0.0.2" not in (await subs.list_templates(ctx))["error"]
    assert "10.0.0.2" not in (await subs.get_template(ctx, "u"))["error"]
    assert "10.0.0.2" not in (await subs.create_template(ctx, "n", "MIHOMO"))["error"]


@pytest.mark.asyncio
async def test_create(ctx, panel):
    r = await subs.create_template(ctx, "New", "STASH")
    assert r == {"uuid": "new-uuid", "name": "New", "type": "STASH"}
    assert panel.created == [("New", "STASH")]

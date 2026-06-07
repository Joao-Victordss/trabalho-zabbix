#!/usr/bin/env python3
import json
import os
import sys
import time
import urllib.error
import urllib.request


ZABBIX_URL = os.getenv("ZABBIX_URL", "http://localhost:8080/api_jsonrpc.php")
ZABBIX_USER = os.getenv("ZABBIX_USER", "Admin")
ZABBIX_PASSWORD = os.getenv("ZABBIX_PASSWORD", "zabbix")

GROUP_NAME = "TP-Zabbix"
HOST_NAME = "linux-monitorado"
TEMPLATE_NAME = "TP - Monitoramento Personalizado"
ACTION_NAME = "TP - Iniciar Squid automaticamente"


class ZabbixAPI:
    def __init__(self, url):
        self.url = url
        self.auth = None
        self.request_id = 1

    def call(self, method, params=None, auth=True):
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": self.request_id,
        }
        self.request_id += 1
        if auth and self.auth:
            payload["auth"] = self.auth

        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.url,
            data=data,
            headers={"Content-Type": "application/json-rpc"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Falha ao acessar API em {self.url}: {exc}") from exc

        if "error" in result:
            error = result["error"]
            raise RuntimeError(f"{method}: {error.get('message')} - {error.get('data')}")
        return result["result"]

    def login(self, user, password):
        try:
            self.auth = self.call(
                "user.login",
                {"username": user, "password": password},
                auth=False,
            )
        except RuntimeError:
            self.auth = self.call(
                "user.login",
                {"user": user, "password": password},
                auth=False,
            )


def wait_for_api(api, attempts=60, delay=5):
    for attempt in range(1, attempts + 1):
        try:
            api.call("apiinfo.version", auth=False)
            return
        except RuntimeError as exc:
            if attempt == attempts:
                raise
            print(f"Aguardando API do Zabbix ({attempt}/{attempts}): {exc}")
            time.sleep(delay)


def get_or_create_group(api):
    groups = api.call("hostgroup.get", {"filter": {"name": [GROUP_NAME]}})
    if groups:
        return groups[0]["groupid"]
    return api.call("hostgroup.create", {"name": GROUP_NAME})["groupids"][0]


def get_or_create_template_group(api):
    try:
        groups = api.call("templategroup.get", {"filter": {"name": [GROUP_NAME]}})
        if groups:
            return groups[0]["groupid"]
        return api.call("templategroup.create", {"name": GROUP_NAME})["groupids"][0]
    except RuntimeError:
        return get_or_create_group(api)


def get_or_create_template(api, template_groupid):
    templates = api.call("template.get", {"filter": {"host": [TEMPLATE_NAME]}})
    if templates:
        return templates[0]["templateid"]
    return api.call(
        "template.create",
        {"host": TEMPLATE_NAME, "groups": [{"groupid": template_groupid}]},
    )["templateids"][0]


def get_or_create_host(api, groupid, templateid):
    hosts = api.call("host.get", {"filter": {"host": [HOST_NAME]}})
    host_payload = {
        "host": HOST_NAME,
        "name": HOST_NAME,
        "groups": [{"groupid": groupid}],
        "templates": [{"templateid": templateid}],
        "interfaces": [
            {
                "type": 1,
                "main": 1,
                "useip": 0,
                "ip": "",
                "dns": HOST_NAME,
                "port": "10050",
            }
        ],
    }
    if hosts:
        hostid = hosts[0]["hostid"]
        api.call(
            "host.update",
            {
                "hostid": hostid,
                "groups": host_payload["groups"],
                "templates": host_payload["templates"],
            },
        )
        return hostid
    return api.call("host.create", host_payload)["hostids"][0]


def get_items(api, templateid):
    items = api.call(
        "item.get",
        {
            "hostids": templateid,
            "output": ["itemid", "key_", "name"],
        },
    )
    return {item["key_"]: item for item in items}


def ensure_items(api, templateid):
    specs = [
        {
            "name": "Disco: espaco livre",
            "key_": "vfs.fs.size[/,free]",
            "units": "B",
            "value_type": 3,
            "tags": [{"tag": "component", "value": "Disco"}],
        },
        {
            "name": "Disco: espaco usado",
            "key_": "vfs.fs.size[/,used]",
            "units": "B",
            "value_type": 3,
            "tags": [{"tag": "component", "value": "Disco"}],
        },
        {
            "name": "Disco: espaco total",
            "key_": "vfs.fs.size[/,total]",
            "units": "B",
            "value_type": 3,
            "tags": [{"tag": "component", "value": "Disco"}],
        },
        {
            "name": "Disco: percentual usado",
            "key_": "vfs.fs.size[/,pused]",
            "units": "%",
            "value_type": 0,
            "tags": [{"tag": "component", "value": "Disco"}],
        },
        {
            "name": "CPU: ociosidade media 1min",
            "key_": "system.cpu.util[,idle,avg1]",
            "units": "%",
            "value_type": 0,
            "tags": [{"tag": "component", "value": "CPU"}],
        },
        {
            "name": "CPU: utilizacao",
            "key_": "custom.cpu.util.pused",
            "type": 15,
            "params": "100-last(//system.cpu.util[,idle,avg1])",
            "units": "%",
            "value_type": 0,
            "tags": [{"tag": "component", "value": "CPU"}],
        },
        {
            "name": "Memoria: utilizacao",
            "key_": "vm.memory.size[pused]",
            "units": "%",
            "value_type": 0,
            "tags": [{"tag": "component", "value": "Memoria"}],
        },
        {
            "name": "Memoria: total",
            "key_": "vm.memory.size[total]",
            "units": "B",
            "value_type": 3,
            "tags": [{"tag": "component", "value": "Memoria"}],
        },
        {
            "name": "Memoria: livre",
            "key_": "vm.memory.size[free]",
            "units": "B",
            "value_type": 3,
            "tags": [{"tag": "component", "value": "Memoria"}],
        },
        {
            "name": "Servico Squid: processos em execucao",
            "key_": "proc.num[squid]",
            "units": "processos",
            "value_type": 3,
            "tags": [{"tag": "component", "value": "Servico"}],
        },
    ]
    existing = get_items(api, templateid)
    for spec in specs:
        payload = {
            "hostid": templateid,
            "name": spec["name"],
            "key_": spec["key_"],
            "type": spec.get("type", 0),
            "value_type": spec["value_type"],
            "delay": spec.get("delay", "30s"),
            "units": spec.get("units", ""),
            "tags": spec.get("tags", []),
        }
        if "params" in spec:
            payload["params"] = spec["params"]
        if spec["key_"] in existing:
            update_payload = dict(payload)
            update_payload.pop("hostid", None)
            update_payload["itemid"] = existing[spec["key_"]]["itemid"]
            api.call("item.update", update_payload)
        else:
            api.call("item.create", payload)
    return get_items(api, templateid)


def ensure_triggers(api, templateid):
    specs = [
        {
            "description": "Disco: uso maior que 50% e menor que 60%",
            "priority": 4,
            "expression": f"min(/{TEMPLATE_NAME}/vfs.fs.size[/,pused],1m)>50 and max(/{TEMPLATE_NAME}/vfs.fs.size[/,pused],1m)<60",
        },
        {
            "description": "Disco: uso maior que 60%",
            "priority": 5,
            "expression": f"min(/{TEMPLATE_NAME}/vfs.fs.size[/,pused],1m)>60",
        },
        {
            "description": "CPU: utilizacao maior que 30% por 1 minuto",
            "priority": 4,
            "expression": f"min(/{TEMPLATE_NAME}/custom.cpu.util.pused,1m)>30",
        },
        {
            "description": "Memoria: utilizacao maior que 30% por 1 minuto",
            "priority": 4,
            "expression": f"min(/{TEMPLATE_NAME}/vm.memory.size[pused],1m)>30",
        },
        {
            "description": "Squid: servico parado",
            "priority": 5,
            "expression": f"max(/{TEMPLATE_NAME}/proc.num[squid],1m)=0",
        },
    ]
    trigger_ids = {}
    for spec in specs:
        found = api.call(
            "trigger.get",
            {
                "filter": {"description": [spec["description"]]},
                "templateids": [templateid],
                "output": ["triggerid", "description"],
            },
        )
        payload = {
            "description": spec["description"],
            "expression": spec["expression"],
            "priority": spec["priority"],
            "tags": [{"tag": "scope", "value": "tp-zabbix"}],
        }
        if found:
            payload["triggerid"] = found[0]["triggerid"]
            api.call("trigger.update", payload)
            trigger_ids[spec["description"]] = found[0]["triggerid"]
        else:
            trigger_ids[spec["description"]] = api.call("trigger.create", payload)["triggerids"][0]
    return trigger_ids


def ensure_graph(api, templateid, name, item_keys, item_by_key):
    graphs = api.call("graph.get", {"hostids": templateid, "filter": {"name": [name]}})
    gitems = []
    colors = ["00AA00", "CC0000", "2774A4", "F7941D"]
    for index, key in enumerate(item_keys):
        gitems.append(
            {
                "itemid": item_by_key[key]["itemid"],
                "color": colors[index % len(colors)],
                "drawtype": 0,
                "sortorder": index,
                "yaxisside": 0,
            }
        )
    payload = {"name": name, "width": 900, "height": 200, "gitems": gitems}
    if graphs:
        payload["graphid"] = graphs[0]["graphid"]
        api.call("graph.update", payload)
    else:
        api.call("graph.create", payload)


def ensure_graphs(api, templateid, items):
    ensure_graph(
        api,
        templateid,
        "Grafico Disco - Espaco",
        ["vfs.fs.size[/,free]", "vfs.fs.size[/,used]", "vfs.fs.size[/,total]"],
        items,
    )
    ensure_graph(api, templateid, "Grafico CPU - Utilizacao", ["custom.cpu.util.pused"], items)
    ensure_graph(
        api,
        templateid,
        "Grafico Memoria - Capacidade",
        ["vm.memory.size[total]", "vm.memory.size[free]"],
        items,
    )
    ensure_graph(api, templateid, "Grafico Memoria - Utilizacao", ["vm.memory.size[pused]"], items)


def ensure_remote_action(api, squid_triggerid):
    actions = api.call("action.get", {"filter": {"name": [ACTION_NAME]}, "output": ["actionid", "name"]})
    payload = {
        "name": ACTION_NAME,
        "eventsource": 0,
        "status": 0,
        "esc_period": "1m",
        "filter": {
            "evaltype": 0,
            "conditions": [
                {
                    "conditiontype": 2,
                    "operator": 0,
                    "value": squid_triggerid,
                }
            ],
        },
        "operations": [
            {
                "operationtype": 1,
                "esc_step_from": 1,
                "esc_step_to": 1,
                "esc_period": "0",
                "opcommand": {
                    "command": "/usr/local/bin/start-squid.sh",
                },
                "opcommand_hst": [{"hostid": "0"}],
            }
        ],
    }
    if actions:
        payload["actionid"] = actions[0]["actionid"]
        api.call("action.update", payload)
    else:
        api.call("action.create", payload)


def main():
    api = ZabbixAPI(ZABBIX_URL)
    wait_for_api(api)
    api.login(ZABBIX_USER, ZABBIX_PASSWORD)

    groupid = get_or_create_group(api)
    template_groupid = get_or_create_template_group(api)
    templateid = get_or_create_template(api, template_groupid)
    hostid = get_or_create_host(api, groupid, templateid)
    items = ensure_items(api, templateid)
    triggers = ensure_triggers(api, templateid)
    ensure_graphs(api, templateid, items)

    try:
        ensure_remote_action(api, triggers["Squid: servico parado"])
        action_status = "criada/atualizada"
    except RuntimeError as exc:
        action_status = f"nao criada automaticamente ({exc})"

    print("Provisionamento finalizado.")
    print(f"Grupo: {GROUP_NAME} ({groupid})")
    print(f"Template: {TEMPLATE_NAME} ({templateid})")
    print(f"Host: {HOST_NAME} ({hostid})")
    print(f"Acao remota: {action_status}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        sys.exit(1)

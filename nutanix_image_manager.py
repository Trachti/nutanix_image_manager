import http.client
import json
import ssl
import time

NTNX_PRISMCENTRAL_IP = "YOUR_IP:9440"
PC_TOKEN = "YOUR GENERATED TOKEN FROM nutanix_auth.py"


def get_conn(host=NTNX_PRISMCENTRAL_IP):
    context = ssl._create_unverified_context()
    return http.client.HTTPSConnection(host, context=context)


def api_request(method, url, payload=None, host=NTNX_PRISMCENTRAL_IP, token=PC_TOKEN, extra_headers=None):
    conn = get_conn(host)
    headers = {
        "Accept": "application/json",
        "Authorization": token,
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    body = None if payload is None else payload if isinstance(payload, str) else json.dumps(payload)
    conn.request(method, url, body=body, headers=headers)
    res = conn.getresponse()
    raw = res.read().decode("utf-8")
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        data = {"raw": raw}
    if res.status >= 400:
        raise RuntimeError(f"API error {res.status} on {host}{url}: {data}")
    return data, res.status


def task_uuid(response):
    return (response.get("status", {}).get("execution_context", {}).get("task_uuid")
            or response.get("task_uuid")
            or response.get("status", {}).get("task_uuid"))


def wait_for_task(task_id, timeout=300, interval=5):
    start = time.time()
    while time.time() - start < timeout:
        data, _ = api_request("GET", f"/api/nutanix/v3/tasks/{task_id}")
        status = str(data.get("status", "")).upper()
        if status in {"SUCCEEDED", "FAILED", "ABORTED"}:
            return data
        time.sleep(interval)
    raise TimeoutError(f"Task {task_id} reached timeout after {timeout}s.")


def list_vms(page_size=100):
    offset, results = 0, []
    while True:
        payload = {"kind": "vm", "length": page_size, "offset": offset}
        data, _ = api_request("POST", "/api/nutanix/v3/vms/list", payload)
        entities = data.get("entities", [])
        if not entities:
            break
        results.extend(entities)
        total = data.get("metadata", {}).get("total_matches")
        offset += page_size
        if total is not None and offset >= total:
            break
    return results


def get_vm_by_name(name):
    for vm in list_vms():
        if vm.get("spec", {}).get("name") == name:
            return vm
    return None


def get_vm(uuid_):
    data, _ = api_request("GET", f"/api/nutanix/v3/vms/{uuid_}")
    return data


def put_vm(uuid_, vm_data, timeout=300, interval=5):
    response, _ = api_request("PUT", f"/api/nutanix/v3/vms/{uuid_}", vm_data)
    tid = task_uuid(response)
    if tid:
        result = wait_for_task(tid, timeout=timeout, interval=interval)
        if str(result.get("status", "")).upper() != "SUCCEEDED":
            raise RuntimeError(f"Task failed: {result}")
    return get_vm(uuid_)

import argparse
from datetime import datetime, timezone

DEFAULT_CONTAINER_UUID = None


def list_images(page_size=100):
    offset, results = 0, []
    while True:
        payload = {"kind": "image", "length": page_size, "offset": offset}
        data, _ = api_request("POST", "/api/nutanix/v3/images/list", payload)
        entities = data.get("entities", [])
        if not entities:
            break
        results.extend(entities)
        total = data.get("metadata", {}).get("total_matches")
        offset += page_size
        if total is not None and offset >= total:
            break
    return results


def image_info(img):
    meta, spec, status = img.get("metadata", {}), img.get("spec", {}), img.get("status", {})
    res = status.get("resources") or spec.get("resources") or {}
    return {"name": spec.get("name") or status.get("name"), "uuid": meta.get("uuid"), "type": res.get("image_type"), "state": res.get("state"), "size_bytes": res.get("size_bytes"), "source_uri": res.get("source_uri")}


def find_by_name(name):
    for img in list_images():
        if image_info(img).get("name") == name:
            return img
    return None


def create_from_url(name, image_type, source_url, description="", container_uuid=None, dry_run=False):
    payload = {"metadata": {"kind": "image"}, "spec": {"name": name, "description": description, "resources": {"image_type": image_type, "source_uri": source_url}}}
    if container_uuid:
        payload["spec"]["resources"]["storage_container_reference"] = {"kind": "storage_container", "uuid": container_uuid}
    if dry_run:
        return {"success": True, "dry_run": True, "payload": payload}
    response, _ = api_request("POST", "/api/nutanix/v3/images", payload)
    return {"success": True, "response": response}


def main():
    parser = argparse.ArgumentParser(description="List, inspect, create from URL, or delete Nutanix images through Prism Central.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list"); p.add_argument("--json-file")
    p = sub.add_parser("show"); p.add_argument("--uuid"); p.add_argument("--name")
    p = sub.add_parser("create-url"); p.add_argument("--name", required=True); p.add_argument("--type", required=True, choices=["ISO_IMAGE", "DISK_IMAGE"]); p.add_argument("--source-url", required=True); p.add_argument("--description", default=""); p.add_argument("--container-uuid", default=DEFAULT_CONTAINER_UUID); p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("delete"); p.add_argument("--uuid", required=True); p.add_argument("--dry-run", action="store_true"); p.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.cmd == "list":
        data = {"generated_at": datetime.now(timezone.utc).isoformat(), "images": [image_info(i) for i in list_images()]}
        print(json.dumps(data, indent=2, ensure_ascii=False))
        if args.json_file:
            open(args.json_file, "w", encoding="utf-8").write(json.dumps(data, indent=2, ensure_ascii=False))
    elif args.cmd == "show":
        img = api_request("GET", f"/api/nutanix/v3/images/{args.uuid}")[0] if args.uuid else find_by_name(args.name)
        if not img:
            raise RuntimeError("Image was not found.")
        print(json.dumps(image_info(img), indent=2, ensure_ascii=False))
    elif args.cmd == "create-url":
        print(json.dumps(create_from_url(args.name, args.type, args.source_url, args.description, args.container_uuid, args.dry_run), indent=2, ensure_ascii=False))
    elif args.cmd == "delete":
        if not args.dry_run and not args.force:
            raise RuntimeError("Deleting an image requires --force.")
        if args.dry_run:
            print(json.dumps({"success": True, "dry_run": True, "uuid": args.uuid}, indent=2))
        else:
            response, _ = api_request("DELETE", f"/api/nutanix/v3/images/{args.uuid}")
            print(json.dumps({"success": True, "response": response}, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()

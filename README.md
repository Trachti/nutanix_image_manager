# Nutanix Image Manager

List, inspect, create from URL, or delete Nutanix images through Prism Central.

## Features

- List images
- Show image details
- Register image from HTTP/HTTPS source URL
- Delete images with explicit `--force`
- Supports dry-run for create and delete workflows

## Important Upload Note

For local files, place the file on an internal HTTP/HTTPS server first and use `--source-url`.

## Configuration

Edit `nutanix_image_manager.py`:

```python
NTNX_PRISMCENTRAL_IP = "YOUR_IP:9440"
PC_TOKEN = "YOUR GENERATED TOKEN FROM nutanix_auth.py"
```

## Usage

```bash
python nutanix_image_manager.py list
python nutanix_image_manager.py show --name ubuntu-iso
python nutanix_image_manager.py create-url --name ubuntu-iso --type ISO_IMAGE --source-url http://example.local/ubuntu.iso --dry-run
python nutanix_image_manager.py delete --uuid IMAGE_UUID --dry-run
python nutanix_image_manager.py delete --uuid IMAGE_UUID --force
```

## Safety Notes

Deleting requires `--force`. Do not commit real tokens, image URLs, UUIDs, IP addresses, or internal details.

## Disclaimer

Example script. Test in a safe environment before production use.

"""List the Fabric capacities you can use, with their ID, name, size, region and state.

Copy the ID you want into .env (FABRIC_CAPACITY_ID).
Run: uv run python scripts/list_capacities.py
"""

from lib.fabric import Client


def main():
    caps = list(Client().paged("/capacities"))
    print(f"{'id':<38} {'displayName':<40} {'sku':<6} {'region':<18} state")
    for x in caps:
        print(f"{x['id']:<38} {x['displayName']:<40} {x.get('sku', ''):<6} {x.get('region', ''):<18} {x.get('state', '')}")


if __name__ == "__main__":
    main()

import json
from pathlib import Path


MEMORY = Path("attack_memory.jsonl")
CLEAN_MEMORY = Path("attack_memory_clean.jsonl")


def load_memory():
    records = []

    with open(MEMORY, encoding="utf-8") as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return records


def clean_memory(records):
    attacks = {}

    for record in records:
        uuid = record.get("uuid")

        if uuid not in attacks:
            attacks[uuid] = {
                "uuid": uuid,
                "sequence": record.get("sequence"),
                "probe": record.get("probe"),
                "attack": record.get("attack"),
                "statuses": []
            }

        status = record.get("status")

        if status not in attacks[uuid]["statuses"]:
            attacks[uuid]["statuses"].append(status)

    return list(attacks.values())


def save_clean_memory(attacks):
    with open(CLEAN_MEMORY, "w", encoding="utf-8") as f:
        for attack in attacks:
            f.write(
                json.dumps(
                    attack,
                    ensure_ascii=False
                ) + "\n"
            )


def main():
    records = load_memory()

    print(f"Registros originales: {len(records)}")

    attacks = clean_memory(records)

    print(f"Ataques únicos: {len(attacks)}")

    save_clean_memory(attacks)

    print(f"Memoria limpia creada: {CLEAN_MEMORY.resolve()}")

    print("\nResumen:")

    for attack in attacks:
        print(
            f"  [{attack['sequence']}] "
            f"statuses={attack['statuses']}"
        )


if __name__ == "__main__":
    main()
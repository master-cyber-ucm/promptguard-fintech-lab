# -*- coding: utf-8 -*-
"""
ver_respuestas.py
==================
Muestra el prompt y la respuesta completa de Clara para uno o varios
fixture_id concretos, leyendo el log.jsonl de una ejecución de attack_loop.py.

USO:
    python ver_respuestas.py results/run_20260820_183901/log.jsonl atk_009 atk_003_dan_roleplay
    (en Windows también puedes usar barras invertidas en la terminal real, aunque
    dentro de este docstring se escriben con barra normal para evitar warnings)
"""

import json
import sys

def main():
    if len(sys.argv) < 3:
        print("Uso: python ver_respuestas.py <ruta_al_log.jsonl> <fixture_id_1> [fixture_id_2 ...]")
        sys.exit(1)

    log_path = sys.argv[1]
    wanted_ids = set(sys.argv[2:])

    with open(log_path, encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            if entry["fixture_id"] in wanted_ids:
                print("=" * 70)
                print(f"ID:        {entry['fixture_id']}")
                print(f"Vector:    {entry['attack_type']}")
                print(f"Resultado: {'CAYÓ' if entry['success'] is True else ('SIN RESPUESTA/INCONCLUSO' if entry['success']=='INCONCLUSIVE' else 'bloqueado')}  ({entry['eval_method']})")
                print("-" * 70)
                print("PROMPT ENVIADO:")
                print(entry["prompt"])
                print("-" * 70)
                print("RESPUESTA DE CLARA:")
                print(entry["response"])
                print()

if __name__ == "__main__":
    main()

"""Crea la memoria de AgentCore con estrategias de largo plazo.

Uso:  python scripts/create_memory.py [--region us-east-1]
Imprime el MEMORY_ID que debes configurar como variable de entorno del runtime.
"""
import argparse

from bedrock_agentcore.memory import MemoryClient

parser = argparse.ArgumentParser()
parser.add_argument("--region", default="us-east-1")
parser.add_argument("--name", default="TripPlannerMemory")
args = parser.parse_args()

client = MemoryClient(region_name=args.region)
memory = client.create_memory_and_wait(
    name=args.name,
    description="Memoria de TripPlanner AI: corto plazo (eventos) + largo plazo (preferencias, hechos, resúmenes)",
    event_expiry_days=90,
    strategies=[
        {"userPreferenceMemoryStrategy": {"name": "TravelPreferences",
                                          "namespaces": ["/users/{actorId}/preferences"]}},
        {"semanticMemoryStrategy": {"name": "TravelFacts", "namespaces": ["/users/{actorId}/facts"]}},
        {"summaryMemoryStrategy": {"name": "SessionSummaries",
                                   "namespaces": ["/summaries/{actorId}/{sessionId}"]}},
    ],
)
print("MEMORY_ID =", memory.get("id") or memory.get("memoryId"))

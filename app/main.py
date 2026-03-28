from __future__ import annotations

from app.agent import BartlettInfoAgent
from app.models import AgentRequest


def main() -> None:
    agent = BartlettInfoAgent()

    print("UCL Bartlett Info Agent")
    print("Ask about staff, programmes, contact details, or opening hours. Type 'exit' to quit.")

    while True:
        query = input("\n> ").strip()
        if not query:
            continue
        if query.lower() in {"exit", "quit"}:
            print("Bye.")
            break

        response = agent.handle(AgentRequest(query=query))
        print(f"Intent: {response.intent}")
        print(f"Entity: {response.entity or 'N/A'}")
        print(f"Answer: {response.answer}")
        print(f"Confidence: {response.confidence}")
        print(f"Routing: {response.routing_reason}")
        if response.sources:
            print("Sources:")
            for source in response.sources:
                print(f"- {source}")


if __name__ == "__main__":
    main()
